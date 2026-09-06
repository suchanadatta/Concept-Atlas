#!/usr/bin/env python3
"""Join the author registry to the corpus and the concept map.

Reads data/authors.csv (name, sex, life dates) and joins it to every book_id
in the v2 index, then to the concept map's inverted index, producing one
file the UI can load without any further computation:

    Concept Maps/graph-ui/data/authors.json

Beyond the roster this answers the question the registry makes askable:
*which concepts does each group of writers actually spend its pages on?*
Concept shares are computed per group so the answer is not just "men wrote
more books" — every count is normalised by that group's own total.

Usage:
    python tools/build_author_stats.py
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

REGISTRY = REPO / "data" / "authors.csv"
IDX_META = REPO / "models" / "jasper_index_v2" / "meta.jsonl"
INV_INDEX = REPO / "Concept Maps" / "final" / "inverted_index.jsonl"
GRAPH = REPO / "Concept Maps" / "final" / "concept_graph.jsonl"
OUT = REPO / "Concept Maps" / "graph-ui" / "data" / "authors.json"


def load_registry() -> dict[str, dict]:
    rows = {}
    with open(REGISTRY, encoding="utf-8-sig") as f:
        for row in csv.DictReader(l for l in f if not l.lstrip().startswith("#")):
            if not row.get("key"):
                continue
            rows[row["key"].strip().lower()] = {
                "key": row["key"].strip().lower(),
                "name": row["display_name"].strip(),
                "sex": (row["sex"] or "U").strip(),
                "born": int(row["born"]) if (row.get("born") or "").strip() else None,
                "died": int(row["died"]) if (row.get("died") or "").strip() else None,
                "note": (row.get("note") or "").strip(),
            }
    return rows


# Surnames the corpus files spell differently from the registry.
ALIASES = {
    "trotter": "cockburn",           # Cockburn, Catharine Trotter
    "anonymous": "anon",
    "gwinnett": "gwinnett-and-thomas",
    "copy": "turnbull",              # 'Copy of Turnbull …'
    "astell-norris": "astell-and-norris",
    "burnet-locke": "burnet-and-locke",
}


def author_key(book_id: str) -> str:
    """Registry key for a book_id.

    Both id shapes appear in the index — 'ASTELL-and-NORRIS_1695_…' and
    'Hutcheson An Inquiry into…' — so this reuses the citation parser rather
    than guessing at the delimiter; taking the first '_'-segment turned
    'Masham Discourse_concerning_…' into the key 'mashamdiscourse'.
    """
    from jasper_search_server_v2 import parse_book_id

    author = (parse_book_id(book_id) or {}).get("author") or ""
    if not author:
        author = (book_id or "").split(" ")[0]
    k = author.lower().replace(" & ", "-and-").replace(" ", "-")
    k = re.sub(r"[^a-z\-]", "", k).strip("-")
    return ALIASES.get(k, k)


def main() -> int:
    reg = load_registry()
    if not IDX_META.exists():
        print(f"missing {IDX_META}", file=sys.stderr)
        return 1

    # ---- books, passages and pages per author -------------------------------
    passages = Counter()
    books_by_author: dict[str, set[str]] = defaultdict(set)
    pages_by_author: dict[str, set[tuple[str, int]]] = defaultdict(set)
    years_by_author: dict[str, list[int]] = defaultdict(list)
    unmatched = Counter()

    from jasper_search_server_v2 import parse_book_id  # citation parser

    book_meta: dict[str, dict] = {}
    for line in open(IDX_META, encoding="utf-8"):
        d = json.loads(line)
        bid = d["book_id"]
        k = author_key(bid)
        if k not in reg:
            unmatched[k] += 1
            continue
        passages[k] += 1
        books_by_author[k].add(bid)
        if d.get("page") is not None:
            pages_by_author[k].add((bid, d["page"]))
        if bid not in book_meta:
            c = parse_book_id(bid)
            book_meta[bid] = c
            if c["year"]:
                years_by_author[k].append(int(c["year"]))

    # ---- concepts per author, via the concept map's inverted index ----------
    labels: dict[str, str] = {}
    if GRAPH.exists():
        for line in open(GRAPH, encoding="utf-8"):
            d = json.loads(line)
            if d.get("type") == "node":
                labels[d["id"]] = d.get("label", d["id"])

    concepts_by_author: dict[str, Counter] = defaultdict(Counter)
    if INV_INDEX.exists():
        for line in open(INV_INDEX, encoding="utf-8"):
            d = json.loads(line)
            k = author_key(d.get("book_id", ""))
            if k in reg:
                concepts_by_author[k][d["concept_id"]] += 1

    # ---- assemble ----------------------------------------------------------
    authors = []
    for k, info in sorted(reg.items(), key=lambda kv: kv[1]["name"]):
        bks = sorted(books_by_author.get(k, ()))
        if not bks:
            continue  # registry entry with nothing in the index
        yrs = years_by_author.get(k, [])
        authors.append(
            {
                **info,
                "books": len(bks),
                "book_ids": bks,
                "passages": passages[k],
                "pages": len(pages_by_author.get(k, ())),
                "first_year": min(yrs) if yrs else None,
                "last_year": max(yrs) if yrs else None,
                "concepts": [
                    {"id": c, "label": labels.get(c, c), "n": n}
                    for c, n in concepts_by_author.get(k, Counter()).most_common(12)
                ],
                "n_concepts": len(concepts_by_author.get(k, ())),
            }
        )

    # ---- group comparison ---------------------------------------------------
    def group_of(sex: str) -> str:
        s = (sex or "U").upper()
        if s.startswith("F"):
            return "women"
        if "&" in s:
            return "joint"
        if s.startswith("M"):
            return "men"
        return "unattributed"

    groups: dict[str, dict] = {}
    gconc: dict[str, Counter] = defaultdict(Counter)
    for a in authors:
        g = group_of(a["sex"])
        gr = groups.setdefault(
            g, {"group": g, "authors": 0, "books": 0, "passages": 0, "pages": 0}
        )
        gr["authors"] += 1
        gr["books"] += a["books"]
        gr["passages"] += a["passages"]
        gr["pages"] += a["pages"]
        for c in concepts_by_author.get(a["key"], Counter()):
            gconc[g][c] += concepts_by_author[a["key"]][c]

    # Concept emphasis: share of a group's own concept-attestations, so the
    # comparison is not simply a restatement of how many books each wrote.
    tot = {g: sum(c.values()) or 1 for g, c in gconc.items()}
    emphasis = []
    for cid in set(gconc.get("women", ())) | set(gconc.get("men", ())):
        w = gconc.get("women", Counter())[cid] / tot.get("women", 1)
        m = gconc.get("men", Counter())[cid] / tot.get("men", 1)
        n_w = gconc.get("women", Counter())[cid]
        n_m = gconc.get("men", Counter())[cid]
        if n_w + n_m < 3:
            continue  # too thin to say anything
        emphasis.append(
            {
                "id": cid,
                "label": labels.get(cid, cid),
                "women_share": round(w, 5),
                "men_share": round(m, 5),
                "n_women": n_w,
                "n_men": n_m,
                # log-ish ratio, positive = the women in the corpus dwell on it more
                "skew": round((w - m) / (w + m), 3) if (w + m) else 0.0,
            }
        )
    emphasis.sort(key=lambda x: -x["skew"])

    out = {
        "generated_from": "data/authors.csv + jasper_index_v2 + concept inverted index",
        "authors": authors,
        "groups": sorted(groups.values(), key=lambda g: -g["books"]),
        "concept_emphasis": {
            "women_lean": emphasis[:14],
            "men_lean": emphasis[-14:][::-1],
        },
        "unmatched_book_prefixes": unmatched.most_common(20),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"wrote {OUT.relative_to(REPO)}")
    print(f"  {len(authors)} authors matched, {sum(a['books'] for a in authors)} books")
    for g in out["groups"]:
        print(
            f"  {g['group']:14s} {g['authors']:3d} authors  {g['books']:4d} books  "
            f"{g['passages']:6d} passages  {g['pages']:6d} pages"
        )
    if unmatched:
        print(f"  unmatched book prefixes: {unmatched.most_common(8)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
