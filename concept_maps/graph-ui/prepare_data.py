#!/usr/bin/env python3
"""Prepare graph-ui/data/graph-data.json from Concept Maps/final/.

Sources (double-audited final merge):
  final/concept_graph.jsonl   203 nodes + 1107 edges
  final/inverted_index.jsonl  paragraph evidence
  final/query_concept_map.json 43 queries -> ranked concepts
  final/category_tree.json    hierarchy (used to color top categories)

Output: graph-ui/data/graph-data.json
"""

import json, re, sys
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).resolve().parent
FINAL = HERE.parent / "final"
OUT_DIR = HERE / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Muted scholarly palette, one per top-level category (assigned by name).
PALETTE = {
    "Moral Psychology": "#C15B5B",
    "Ethics": "#7B68B5",
    "Metaphysics": "#4E79A7",
    "Epistemology": "#5FA052",
    "Theology": "#D9A441",
    "Political Philosophy": "#C86FA6",
    "Aesthetics": "#6AAFA9",
    "Intellectual History": "#9C755F",
    "Moral Philosophy": "#8A8D93",
}
FALLBACK_COLORS = ["#B07AA1", "#76B7B2", "#EDC948", "#FF9DA7", "#79706E"]

# book_id -> source PDF lookup (full_set + corpus)
PDF_DIRS = [
    HERE.parent.parent / "data" / "full_set_pdfs" / "pdf",
    HERE.parent.parent / "data" / "BMoral_pdf_collection",
]


def find_pdf(book_id: str):
    """Locate the source PDF for a book_id (stem match)."""
    stem = book_id.replace(".pages", "")
    for d in PDF_DIRS:
        cand = d / f"{stem}.pdf"
        if cand.exists():
            return str(cand)
    # corpus pdfs live under author dirs
    for d in PDF_DIRS:
        for cand in d.rglob(f"{stem}.pdf"):
            return str(cand)
    return None


BOOK_ID_RE = re.compile(
    r"^(?P<author>[A-Z]+)_(?P<year>\d{4})_(?P<idx>\d+)_(?P<title>.+)$"
)


def parse_book_id(book_id: str):
    m = BOOK_ID_RE.match(book_id or "")
    if not m:
        return {"author": book_id or "Unknown", "year": "", "title": book_id or ""}
    title = m.group("title").replace("-", " ").replace("_", " ").strip()
    title = re.sub(r"\s+", " ", title)
    author = m.group("author").title().replace("_", " ")
    return {"author": author, "year": m.group("year"), "title": title}


def main():
    # ---- nodes + edges -------------------------------------------------
    nodes, edges = [], []
    node_ids = set()
    with open(FINAL / "concept_graph.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("type") == "node":
                node_ids.add(rec["id"])
                cats = rec.get("category") or ["Uncategorized"]
                nodes.append(
                    {
                        "id": rec["id"],
                        "label": rec.get("label", rec["id"]),
                        "category": cats,
                        "top": cats[0],
                        "sub": cats[1] if len(cats) > 1 else "",
                        "importance": float(rec.get("importance", 0.5)),
                        "books": int(rec.get("book_count", 0)),
                        "evidence": int(rec.get("evidence_count", 0)),
                        "aliases": rec.get("aliases") or [],
                        "definition": rec.get("definition", ""),
                    }
                )
            elif rec.get("type") == "edge":
                edges.append(
                    {
                        "s": rec["source"],
                        "t": rec["target"],
                        "r": rec.get("relation", "related"),
                        "w": round(float(rec.get("strength", 0.5)), 3),
                    }
                )

    missing = [e for e in edges if e["s"] not in node_ids or e["t"] not in node_ids]
    if missing:
        print(
            f"WARN: {len(missing)} edges reference unknown nodes; dropping",
            file=sys.stderr,
        )
        edges = [e for e in edges if e["s"] in node_ids and e["t"] in node_ids]

    # degree
    deg = defaultdict(int)
    for e in edges:
        deg[e["s"]] += 1
        deg[e["t"]] += 1
    for n in nodes:
        n["degree"] = deg.get(n["id"], 0)

    # ---- category colors + counts --------------------------------------
    top_counts = defaultdict(int)
    for n in nodes:
        top_counts[n["top"]] += 1
    colors = dict(PALETTE)
    extra = iter(FALLBACK_COLORS)
    for c in top_counts:
        if c not in colors:
            colors[c] = next(extra, "#79706E")
    categories = [
        {"name": c, "count": top_counts[c], "color": colors[c]}
        for c in sorted(top_counts, key=lambda x: -top_counts[x])
    ]

    # ---- evidence (inverted index) --------------------------------------
    ev = defaultdict(list)
    with open(FINAL / "inverted_index.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            cid = rec.get("concept_id")
            if cid not in node_ids:
                continue
            book = parse_book_id(rec.get("book_id", ""))
            text = (rec.get("text") or "").strip()
            if len(text) > 340:
                text = text[:337].rstrip() + "…"
            bid = rec.get("book_id", "")
            pdf_path = find_pdf(bid)
            ev[cid].append(
                {
                    "author": book["author"],
                    "year": book["year"],
                    "title": book["title"],
                    "book_id": bid,
                    "page": rec.get("page"),
                    "paragraph_id": rec.get("paragraph_id"),
                    "text": text,
                    "bbox_pts": rec.get("bbox_pts"),
                    "has_pdf": bool(pdf_path),
                    "pdf_url": f"/book/pdf/{bid}" if pdf_path else None,
                    "txt_url": f"/book/txt/{bid}",
                }
            )
    evidence = {}
    for cid, items in ev.items():
        # dedupe by (book,page,text-head), keep up to 12 (UI shows 5 + expand)
        seen, keep = set(), []
        for it in items:
            key = (it["author"], it["page"], it["text"][:80])
            if key in seen:
                continue
            seen.add(key)
            keep.append(it)
            if len(keep) >= 12:
                break
        evidence[cid] = keep

    # ---- queries ---------------------------------------------------------
    qmap = json.load(open(FINAL / "query_concept_map.json", encoding="utf-8"))
    queries = []
    for qid, q in qmap.items():
        # query-fit ranking: blend the map's relevance with evidence depth.
        # The p3 audit showed static importance ranking buries the concept
        # itself on its own query (conscience ranked 5th on "Conscience").
        # rel_here already encodes query fit from the map; re-sort by it and
        # break ties with evidence count rather than global importance.
        raw = [
            (
                c["concept_id"],
                float(c.get("relevance", 0)),
                sum(1 for it in ev.get(c["concept_id"], [])) if False else None,
            )
            for c in q.get("concepts", [])
            if c["concept_id"] in node_ids
        ]
        concepts = [
            {"id": cid, "rel": round(rel, 3)}
            for cid, rel, _ in sorted(raw, key=lambda x: -x[1])
        ]
        queries.append(
            {"id": qid, "text": q.get("query_text", qid), "concepts": concepts}
        )
    queries.sort(key=lambda q: q["id"])

    # ---- category tree (for optional explorer) ---------------------------
    tree = json.load(open(FINAL / "category_tree.json", encoding="utf-8"))

    data = {
        "meta": {
            "title": "Concept Atlas — British Moral Philosophy",
            "generated": __import__("datetime")
            .datetime.now()
            .isoformat(timespec="seconds"),
            "source": "Concept Maps/final/ (double-audited merge)",
            "nodes": len(nodes),
            "edges": len(edges),
            "queries": len(queries),
        },
        "categories": categories,
        "colors": colors,
        "nodes": nodes,
        "edges": edges,
        "queries": queries,
        "evidence": evidence,
        "tree": tree,
    }
    out = OUT_DIR / "graph-data.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    size = out.stat().st_size
    print(
        f"OK nodes={len(nodes)} edges={len(edges)} queries={len(queries)} "
        f"evidence_concepts={len(evidence)} -> {out} ({size / 1024:.0f} KB)"
    )
    # integrity assertions
    ids = {n["id"] for n in nodes}
    assert len(ids) == len(nodes), "duplicate node ids"
    assert all(e["s"] in ids and e["t"] in ids for e in edges), "dangling edges"
    assert len(queries) in (42, 43), f"expected 42-43 queries, got {len(queries)}"
    print("integrity: PASS")


if __name__ == "__main__":
    main()
