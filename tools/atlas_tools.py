#!/usr/bin/env python3
"""Tools the Atlas agent can call, and the citation table they feed.

Every tool that returns evidence registers each passage in a per-turn
``Cites`` table and hands the model a bracketed marker for it — ``[S4]``. The
model is told to cite with those markers and nothing else, so a citation in
the answer is always resolvable back to a book, a page and (for a scan) the
bounding box of the block the embedding actually matched. The same table goes
to the browser, which is what makes a citation clickable: it opens the reader
at that page with the passage highlighted.

Tools, and why each exists:

  search_corpus        the main retrieval route, with a mode argument so the
                       agent can pick hybrid / pure-semantic / BM25 / keyword
                       rather than being locked to one ranking
  read_source          a page range verbatim, for when a snippet is not enough
  find_concept         semantic lookup over the 202 concept embeddings, so a
                       question with no literal overlap still lands
  concept_detail       one concept with its map relations expanded 1 or 2 hops
  concept_passages     the verbatim quotes attesting a concept
  query_network        the concept+document network for a query — the same
                       thing the Graph tab draws
  list_authors         the 37-creator registry, with sex and life dates
  web_search           the open web, when the corpus plainly cannot answer
  web_fetch            one web page as text

The web tools are gated: the caller passes ``allow_web``, which the UI drives
from a toggle, so a reader can keep an answer strictly inside the corpus.
"""

from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
JASPER = "http://127.0.0.1:8790"
ATLAS = "http://127.0.0.1:8788"

# DuckDuckGo's HTML endpoint answers a sparse request with a challenge page
# (14KB, no results) and a browser-shaped one with the real thing (30KB, ten
# results). The headers are the difference, not the user agent alone.
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
BROWSER_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


# ------------------------------------------------------------------ plumbing
def _post(url: str, body: dict, timeout: int = 90):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _get(url: str, timeout: int = 30, headers: dict | None = None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _form_post(url: str, fields: dict, timeout: int = 25) -> str:
    h = dict(BROWSER_HEADERS)
    h["Content-Type"] = "application/x-www-form-urlencoded"
    h["Origin"] = "https://html.duckduckgo.com"
    h["Referer"] = "https://html.duckduckgo.com/"
    req = urllib.request.Request(
        url, data=urllib.parse.urlencode(fields).encode(), headers=h, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


class Cites:
    """The turn's citation table: marker -> the passage it points at."""

    def __init__(self):
        self.rows: list[dict] = []
        self._seen: dict[tuple, str] = {}

    def add(self, *, book_id, page=None, cite=None, snippet="", bbox_pts=None,
            source=None, kind="passage", extra=None) -> str:
        key = (book_id, page, (snippet or "")[:60])
        if key in self._seen:
            return self._seen[key]
        marker = f"S{len(self.rows) + 1}"
        row = {
            "id": marker, "kind": kind, "book_id": book_id, "page": page,
            "cite": cite or book_id, "snippet": (snippet or "")[:400],
            "bbox_pts": bbox_pts, "source": source,
        }
        if extra:
            row.update(extra)
        self.rows.append(row)
        self._seen[key] = marker
        return marker

    def as_list(self):
        return self.rows


HOW_TO_CITE = (
    "Cite any passage you use by its cite_as value, verbatim, e.g. [S3]. Do not write the book "
    "and page out instead of the marker — the reader clicks the marker to open that exact page."
)
HOW_TO_CITE_WEB = (
    "This is from outside the corpus. Cite it by its cite_as value, e.g. [S7], and say in the "
    "text that it comes from the open web rather than from these 197 sources."
)


def _loc(page, source):
    if page is None or source == "txt":
        return "text edition"
    return f"p. {page}"


# ------------------------------------------------------------- corpus search
def search_corpus(cites: Cites, query: str, mode: str = "hybrid",
                  top_k: int = 8, author: str = "", period: str = "", **_):
    """Retrieve passages. `mode` picks the ranking the agent wants."""
    mode = (mode or "hybrid").lower()
    top_k = max(1, min(int(top_k or 8), 25))
    want = top_k * 3 if (author or period) else top_k
    try:
        if mode == "bm25":
            d = _post(f"{JASPER}/bm25", {"query": query, "top_k": want})
        elif mode == "keyword":
            url = f"{ATLAS}/book/api/gsearch?q={urllib.parse.quote(query)}&limit={want}"
            d = json.loads(_get(url, timeout=60))
        else:
            d = _post(f"{JASPER}/semantic", {
                "query": query, "top_k": want,
                "mode": "semantic" if mode == "semantic" else "hybrid",
            })
    except Exception as e:
        return {"error": f"the search engine did not answer ({e})", "results": []}

    rows, out = d.get("results", []), []
    for r in rows:
        cit = r.get("cite") or r.get("book_id", "")
        if author and author.lower() not in (r.get("author") or cit).lower():
            continue
        if period:
            y = str(r.get("year") or "")
            if not y or not _in_period(y, period):
                continue
        m = cites.add(
            book_id=r.get("book_id"), page=r.get("page"), cite=cit,
            snippet=r.get("text") or r.get("snippet") or "",
            bbox_pts=r.get("bbox_pts"), source=r.get("source"),
        )
        out.append({
            "cite_as": f"[{m}]",
            # read_source needs the raw id, not the display citation — without
            # it the model reached for the marker ("S1") as a book_id
            "book_id": r.get("book_id"),
            "page": r.get("page"),
            "cite": cit, "where": _loc(r.get("page"), r.get("source")),
            "score": r.get("score"),
            "text": (r.get("text") or r.get("snippet") or "")[:700],
        })
        if len(out) >= top_k:
            break
    return {"mode": mode, "n": len(out), "how_to_cite": HOW_TO_CITE, "results": out}


def _in_period(year: str, period: str) -> bool:
    """'1690s', '1700-1740' or '1688' all work as a period filter."""
    try:
        y = int(year)
    except ValueError:
        return False
    p = period.strip().lower()
    m = re.fullmatch(r"(\d{4})s", p)
    if m:
        lo = int(m.group(1))
        return lo <= y < lo + 10
    m = re.fullmatch(r"(\d{4})\s*[-–]\s*(\d{4})", p)
    if m:
        return int(m.group(1)) <= y <= int(m.group(2))
    m = re.fullmatch(r"(\d{4})", p)
    return int(m.group(1)) == y if m else True


def read_source(cites: Cites, book_id: str, page_from=None, page_to=None,
                max_chars: int = 14000, **_):
    """A page (or paragraph) range verbatim."""
    from atlas_chat_server import book_text, find_book_files  # same package

    # A marker is what the model just read, so accept one and resolve it
    # rather than failing on an understandable confusion.
    if re.fullmatch(r"S\d+", str(book_id or "").strip()):
        row = next((r for r in cites.rows if r["id"] == book_id.strip()), None)
        if row is None:
            return {"error": f"no citation {book_id!r} in this turn"}
        if page_from in (None, "") and row.get("page"):
            page_from = row["page"]
        book_id = row["book_id"]
    kind, path = find_book_files(book_id)
    if not path:
        return {"error": f"no source found for {book_id!r}; "
                         "pass the book_id from a search result, or a marker like S3"}
    try:
        pf = int(page_from) if page_from not in (None, "") else None
        pt = int(page_to) if page_to not in (None, "") else None
    except (TypeError, ValueError):
        pf = pt = None
    if pf and pt is None:
        pt = pf + 4          # a bare page number means a small window
    text, n = book_text(book_id, pf, pt, max_chars=max_chars)
    if not text:
        return {"error": f"nothing readable in {book_id!r} for that range"}
    m = cites.add(book_id=book_id, page=pf, cite=_cite_of(book_id),
                  snippet=text[:300], kind="range", source=kind,
                  extra={"page_from": pf, "page_to": pt})
    return {"cite_as": f"[{m}]", "book": _cite_of(book_id), "units": n,
            "how_to_cite": HOW_TO_CITE, "range": [pf, pt], "text": text[:max_chars]}


def _cite_of(book_id: str) -> str:
    try:
        from jasper_search_server_v2 import parse_book_id
        return parse_book_id(book_id)["cite"]
    except Exception:
        return book_id


# ------------------------------------------------------------- concept tools
_GRAPH_CACHE: dict = {}


def _graph():
    if _GRAPH_CACHE:
        return _GRAPH_CACHE
    nodes, edges = {}, []
    gp = REPO / "Concept Maps" / "final" / "concept_graph.jsonl"
    if gp.exists():
        for line in open(gp, encoding="utf-8"):
            d = json.loads(line)
            if d.get("type") == "node":
                nodes[d["id"]] = d
            else:
                edges.append(d)
    inv: dict[str, list] = {}
    ip = REPO / "Concept Maps" / "final" / "inverted_index.jsonl"
    if ip.exists():
        for line in open(ip, encoding="utf-8"):
            d = json.loads(line)
            inv.setdefault(d["concept_id"], []).append(d)
    _GRAPH_CACHE.update(nodes=nodes, edges=edges, inv=inv)
    return _GRAPH_CACHE


def find_concept(cites: Cites, query: str, top_k: int = 6, **_):
    """Semantic lookup over the concept embeddings."""
    try:
        d = _post(f"{JASPER}/concepts", {"query": query, "top_k": max(1, min(int(top_k or 6), 20))})
    except Exception as e:
        return {"error": f"concept search unavailable ({e})", "results": []}
    out = []
    for c in d.get("results", []):
        out.append({
            "concept_id": c["id"], "label": c["label"],
            "category": " > ".join(c.get("category") or []),
            "books": c.get("books"), "score": c.get("score"),
            "definition": (c.get("definition") or "")[:400],
            "relations": [
                f"{r['relation']} {r['label']}" for r in (c.get("relations") or [])[:8]
            ],
        })
    return {"n": len(out), "results": out}


def concept_detail(cites: Cites, concept_id: str, hops: int = 1, **_):
    """One concept, with the map around it expanded 1 or 2 hops.

    Two hops is what answers "how does this connect to that?" — the reason the
    agent has a hop count rather than a flat neighbour list.
    """
    g = _graph()
    nodes, edges = g["nodes"], g["edges"]
    if concept_id not in nodes:
        hit = find_concept(cites, concept_id, top_k=1)
        if hit.get("results"):
            concept_id = hit["results"][0]["concept_id"]
        else:
            return {"error": f"no concept {concept_id!r}"}
    hops = 2 if str(hops) in ("2", "two") else 1
    n = nodes[concept_id]

    def neighbours(cid):
        out = []
        for e in edges:
            if e.get("source") == cid and e.get("target") in nodes:
                out.append((e["target"], e["relation"], "out", e.get("strength", 0.5)))
            elif e.get("target") == cid and e.get("source") in nodes:
                out.append((e["source"], e["relation"], "in", e.get("strength", 0.5)))
        best = {}
        for cid2, rel, d, w in out:
            k = (cid2, rel)
            if k not in best or w > best[k][3]:
                best[k] = (cid2, rel, d, w)
        return sorted(best.values(), key=lambda x: -x[3])

    ring1 = neighbours(concept_id)
    hop1 = [
        {"concept_id": c, "label": nodes[c]["label"], "relation": rel,
         "direction": d, "strength": round(float(w), 3)}
        for c, rel, d, w in ring1[:20]
    ]
    hop2 = []
    if hops == 2:
        seen = {concept_id} | {h["concept_id"] for h in hop1}
        for h in hop1[:8]:
            for c, rel, d, w in neighbours(h["concept_id"])[:6]:
                if c in seen:
                    continue
                seen.add(c)
                hop2.append({
                    "via": h["label"], "concept_id": c, "label": nodes[c]["label"],
                    "relation": rel, "strength": round(float(w), 3),
                })
    return {
        "concept_id": concept_id, "label": n.get("label"),
        "category": " > ".join(n.get("category") or []),
        "aliases": n.get("aliases") or [],
        "definition": n.get("definition") or "",
        "n_attesting_books": len({d["book_id"] for d in g["inv"].get(concept_id, [])}),
        "hop1": hop1, "hop2": hop2,
    }


def concept_passages(cites: Cites, concept_id: str, top_k: int = 8, **_):
    """The verbatim quotes the concept map records for a concept."""
    g = _graph()
    if concept_id not in g["nodes"]:
        hit = find_concept(cites, concept_id, top_k=1)
        if hit.get("results"):
            concept_id = hit["results"][0]["concept_id"]
        else:
            return {"error": f"no concept {concept_id!r}"}
    rows = g["inv"].get(concept_id, [])[: max(1, min(int(top_k or 8), 20))]
    label = g["nodes"][concept_id].get("label") or concept_id
    out = []
    for d in rows:
        m = cites.add(
            book_id=d.get("book_id"), page=d.get("page"),
            cite=_cite_of(d.get("book_id", "")), snippet=d.get("text") or "",
            bbox_pts=d.get("bbox_pts"), kind="evidence",
            # which concept this quote attests, so a reader following the
            # citation can open the concept as well as the page
            extra={"concept_id": concept_id, "concept": label},
        )
        out.append({
            "cite_as": f"[{m}]", "book_id": d.get("book_id"), "page": d.get("page"),
            "cite": _cite_of(d.get("book_id", "")),
            "where": _loc(d.get("page"), None), "quote": (d.get("text") or "")[:500],
        })
    return {"concept": g["nodes"][concept_id].get("label"), "n": len(out),
            "how_to_cite": HOW_TO_CITE, "results": out}


def query_network(cites: Cites, query: str, n_concepts: int = 8, n_docs: int = 10, **_):
    """The concept+document network for a query — what the Graph tab draws."""
    try:
        d = _post(f"{JASPER}/query_graph", {
            "query": query, "n_concepts": int(n_concepts or 8), "n_docs": int(n_docs or 10),
        })
    except Exception as e:
        return {"error": f"graph unavailable ({e})"}
    docs = []
    for x in d.get("docs", []):
        m = cites.add(book_id=x.get("book_id"), page=x.get("page"),
                      cite=_cite_of(x.get("book_id", "")), snippet=x.get("snippet") or "",
                      bbox_pts=x.get("bbox_pts"))
        docs.append({"cite_as": f"[{m}]", "book_id": x.get("book_id"), "page": x.get("page"),
                     "cite": _cite_of(x.get("book_id", "")),
                     "where": _loc(x.get("page"), None), "score": x.get("score")})
    return {
        "concepts": [
            {"concept_id": c["id"], "label": c["label"], "score": c.get("score"),
             "bridge": c.get("match") == "bridge"}
            for c in d.get("concepts", [])
        ],
        "relations": [
            f"{e['s']} --{e['r']}--> {e['t']}" for e in (d.get("c2c") or [])[:20]
        ],
        "how_to_cite": HOW_TO_CITE,
        "documents": docs,
    }


def list_authors(cites: Cites, sex: str = "", name: str = "", **_):
    """The author registry — sex, life dates, output, top concepts."""
    f = REPO / "Concept Maps" / "graph-ui" / "data" / "authors.json"
    if not f.exists():
        return {"error": "the author registry has not been built"}
    d = json.loads(f.read_text(encoding="utf-8"))
    rows = d.get("authors", [])
    if name:
        rows = [a for a in rows if name.lower() in a["name"].lower()]
    if sex:
        s = sex.strip().lower()[0]
        rows = [a for a in rows if (a.get("sex") or "u").lower().startswith(s)]
    return {
        "n": len(rows),
        "groups": d.get("groups"),
        "authors": [
            {"name": a["name"], "sex": a["sex"], "born": a.get("born"),
             "died": a.get("died"), "books": a["books"], "passages": a["passages"],
             "in_corpus": [a.get("first_year"), a.get("last_year")],
             "top_concepts": [c["label"] for c in (a.get("concepts") or [])[:6]]}
            for a in rows[:40]
        ],
    }


# ------------------------------------------------------- checking your work
def _page_text(book_id: str, page) -> str:
    """The printed text of one page, for confirming a quotation verbatim."""
    if not book_id or page is None:
        return ""
    try:
        raw = _get(f"{ATLAS}/book/api/page_text?book={urllib.parse.quote(book_id)}&page={int(page)}",
                   timeout=20)          # _get hands back raw bytes
        d = json.loads(raw.decode("utf-8", "replace")) if raw else {}
    except Exception:
        return ""
    return " ".join((b.get("text") or "") for b in (d.get("blocks") or []))


def _norm_quote(x: str) -> str:
    """Fold the differences that are the scan's, not the author's: long s,
    ligatures, curly quotes, hyphenation across a line break, and case."""
    x = (x or "").lower()
    x = x.replace("\u017f", "s").replace("\u2014", " ").replace("\u2013", " ")
    x = x.replace("\u2019", "'").replace("\u2018", "'")
    x = x.replace("\u201c", '"').replace("\u201d", '"')
    x = re.sub(r"-\s+", "", x)
    return re.sub(r"[^a-z0-9' ]+", " ", x)


def _loose_contains(needle: str, haystack: str) -> bool:
    a = re.sub(r"\s+", " ", _norm_quote(needle)).strip()
    b = re.sub(r"\s+", " ", _norm_quote(haystack)).strip()
    return bool(a) and a in b


def _excerpt(text: str, want: list[str], width: int = 420) -> str:
    """Show the part of the page the words actually landed in."""
    low = text.lower()
    pos = next((low.find(w) for w in want if low.find(w) >= 0), -1)
    if pos < 0:
        return text[:width]
    start = max(0, pos - width // 3)
    return ("\u2026" if start else "") + text[start:start + width]



def verify_quote(cites: Cites, quote: str, book_id: str = "", **_):
    """Does this wording actually occur in the corpus, and where?

    The point of this tool is to be able to say no. A paraphrase the model has
    drifted into, or a quotation it half-remembers, will not match, and that is
    the useful answer — better than an assertion nobody checked.
    """
    q = re.sub(r"\s+", " ", (quote or "")).strip().strip('"\u201c\u201d')
    if len(q) < 12:
        return {"error": "give at least a dozen characters of the quotation to look for"}
    # Long-s and modernised spelling mean an exact match often fails on a true
    # quotation, so search on the distinctive words and then check overlap.
    want = [w for w in re.findall(r"[a-z']{4,}", q.lower())][:12]
    hits = []
    try:
        r = _post(f"{JASPER}/bm25", {"query": q, "top_k": 30}) or {}
        cand = r.get("results") or []
    except Exception as e:
        return {"error": f"could not reach the index: {e}"}
    for row in cand:
        if book_id and row.get("book_id") != book_id:
            continue
        # the index returns a snippet, not the passage, so score on the snippet
        # and confirm verbatim against the real page below
        text = re.sub(r"\s+", " ", row.get("snippet") or row.get("text") or "")
        low = text.lower()
        found = sum(1 for w in want if w in low)
        overlap = found / max(1, len(want))
        if overlap >= 0.5:
            hits.append((overlap, row, text))
    hits.sort(key=lambda h: -h[0])
    out = []
    for overlap, row, text in hits[:4]:
        # A snippet is elided, so "not in the snippet" is not evidence of
        # anything. Pull the page it came from and test the wording there.
        page_text = _page_text(row.get("book_id", ""), row.get("page"))
        haystack = re.sub(r"\s+", " ", page_text or text)
        exact = _loose_contains(q, haystack)
        if page_text:
            low2 = haystack.lower()
            overlap = max(overlap, sum(1 for w in want if w in low2) / max(1, len(want)))
        marker = cites.add(
            book_id=row.get("book_id"), page=row.get("page"),
            cite=_cite_of(row.get("book_id", "")), snippet=text[:400],
            bbox_pts=row.get("bbox_pts"), source=row.get("source"),
        )
        out.append({
            "cite_as": f"[{marker}]",
            "book_id": row.get("book_id"),
            "where": _loc(row.get("page"), row.get("source")),
            "exact": exact,
            "word_overlap": round(overlap, 2),
            "text_as_printed": (_excerpt(haystack, want) if page_text else text)[:600],
        })
    # A handful of common words in common ("soul", "sense") is not a match. An
    # invented sentence will always share *something* with a 90,975-passage
    # corpus, so anything short of near-total overlap counts as not found.
    exact = [h for h in out if h["exact"]]
    close = [h for h in out if not h["exact"] and h["word_overlap"] >= 0.8]
    keep = exact + close
    return {
        "quote": q[:200],
        "found": bool(keep),
        "verdict": (
            "VERBATIM. These words are in the corpus as printed; quote them and cite the marker."
            if exact else
            "CLOSE BUT NOT VERBATIM. The passage exists but the wording differs — copy it from "
            "text_as_printed rather than from memory, and do not modernise it."
            if close else
            "NOT FOUND. Do not present this as a quotation. Either drop it, or make the point in "
            "your own words and cite a passage that does support it."
        ),
        "matches": keep,
        "best_rejected_overlap": (round(out[0]["word_overlap"], 2) if out and not keep else None),
        "how_to_cite": HOW_TO_CITE,
    }


def compare_ideas(cites: Cites, items: list | None = None, top_k: int = 6, **_):
    """Two to four ideas held side by side across the whole corpus."""
    items = [str(i).strip() for i in (items or []) if str(i).strip()][:4]
    if len(items) < 2:
        return {"error": "give two to four concepts or phrases to compare"}
    try:
        d = _post(f"{JASPER}/compare",
                  {"items": items, "top_k": int(top_k or 6), "n_shared": 5}) or {}
    except Exception as e:
        return {"error": f"compare failed: {e}"}
    if d.get("error"):
        return d

    def pack(rows, limit):
        out = []
        for row in (rows or [])[:limit]:
            marker = cites.add(
                book_id=row.get("book_id"), page=row.get("page"),
                cite=_cite_of(row.get("book_id", "")), snippet=row.get("text") or row.get("snippet") or "",
                bbox_pts=row.get("bbox_pts"), source=row.get("source"),
            )
            out.append({
                "cite_as": f"[{marker}]",
                "where": f"{_cite_of(row.get('book_id',''))}, {_loc(row.get('page'), row.get('source'))}",
                "text": (row.get("text") or row.get("snippet") or "")[:400],
            })
        return out

    per = []
    for it in (d.get("items") or []):
        per.append({
            "item": it.get("label") or it.get("item"),
            "definition": it.get("definition"),
            "own_passages": pack(it.get("passages"), 4),
        })
    return {
        "items": items,
        "similarity": d.get("similarity"),
        "similarity_note": (
            "Cosine similarity between the items in the corpus's own embedding space. "
            "High means these texts talk about them in similar language, NOT that the "
            "authors agreed."
        ),
        "map_relations": d.get("relations"),
        "each": per,
        "shared_ground": pack(d.get("shared"), 6),
        "shared_note": (
            "Passages ranked by their WEAKEST score across the items, so these are places "
            "where the ideas are argued together rather than separately."
        ),
        "how_to_cite": HOW_TO_CITE,
    }


def list_books(cites: Cites, author: str = "", sex: str = "",
               year_from: int = 0, year_to: int = 0, **_):
    """What the corpus actually contains — the shelf, not the passages."""
    f = REPO / "Concept Maps" / "graph-ui" / "data" / "authors.json"
    if not f.exists():
        return {"error": "the author registry has not been built"}
    d = json.loads(f.read_text(encoding="utf-8"))
    rows = []
    for a in d.get("authors", []):
        if author and author.lower() not in a["name"].lower():
            continue
        if sex:
            s = sex.strip().lower()[0]
            if not (a.get("sex") or "u").lower().startswith(s):
                continue
        for bid in a.get("book_ids", []):
            c = _cite_of(bid)
            # "\b" does not match between "_" and "1", both being word
            # characters, so ASTELL_1697_... yielded no year at all
            yr = None
            m = re.search(r"(?<!\d)(1[5-9]\d\d)(?!\d)", bid) or re.search(r"\((1[5-9]\d\d)\)", c)
            if m:
                yr = int(m.group(1))
            if year_from and (yr or 0) < int(year_from):
                continue
            if year_to and (yr or 9999) > int(year_to):
                continue
            rows.append({"book_id": bid, "cite": c, "author": a["name"],
                         "sex": a.get("sex"), "year": yr})
    rows.sort(key=lambda r: (r["author"], r["year"] or 0))
    return {
        "n": len(rows),
        "books": rows[:80],
        "note": ("Pass a book_id to read_source to read any of these. Not every book is a "
                 "scan: some are clean-text editions with no page numbers."),
    }


# ----------------------------------------------------------------- web tools
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")


def _strip_html(raw: bytes) -> str:
    s = raw.decode("utf-8", "replace")
    s = re.sub(r"(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)</(p|div|li|h[1-6]|tr|br)\s*>", "\n", s)
    s = _TAG.sub(" ", s)
    s = html.unescape(s)
    s = _WS.sub(" ", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


# Web search runs through the ddgs package, which drives real search engines
# rather than scraping a results page.
#
# DuckDuckGo itself is not usable from this host: html.duckduckgo.com answers
# 202 with a challenge page and no results (which is why the old regex parser
# silently returned nothing), and ddgs ships its DuckDuckGo engine with
# disabled = True, "until ratelimit is fixed". It is listed first anyway, so
# the day it works again it is simply used.
#
# The backends are pinned rather than left on "auto" because auto includes
# engines that answer with results for a different query altogether — a
# Mandeville search came back with Baidu pages and a Phoenix pizza guide.
# Measured on this host: yahoo and yandex answer 5/5 relevant and both honour
# a site: restriction; brave returns a single result with an empty href; bing
# answers a Mandeville query with grocery listings; google, mojeek and the
# mullvad proxies fail outright.
try:
    from ddgs import DDGS as _DDGS
except Exception:  # pragma: no cover - environment without the package
    _DDGS = None

TEXT_BACKENDS = "duckduckgo,yahoo,yandex"
NEWS_BACKENDS = "duckduckgo,yahoo"
SEARCH_KINDS = ("text", "news", "books")
RECENCY = {"day": "d", "week": "w", "month": "m", "year": "y"}


def web_search(cites: Cites, query: str, n: int = 8, page: int = 1, site: str = "",
               kind: str = "text", recency: str = "", region: str = "us-en", **_):
    """A real search engine, not a scrape.

    `page` walks further down the results, `site` restricts to one domain,
    `recency` limits how old a result may be, and `kind` switches between the
    web, news and book verticals. All of it is there so the agent can keep
    refining instead of accepting the first ten links it saw.
    """
    query = (query or "").strip()
    if not query:
        return {"error": "give something to search for"}
    n = max(1, min(int(n or 8), 25))
    page = max(1, min(int(page or 1), 10))
    kind = (kind or "text").lower()
    if kind not in SEARCH_KINDS:
        return {"error": f"kind must be one of {', '.join(SEARCH_KINDS)}"}
    if site:
        host = re.sub(r"^https?://", "", str(site)).strip("/ ")
        if host and f"site:{host}" not in query:
            query = f"site:{host} {query}"

    # editions and dates are a catalogue question, and ddgs answers its books
    # category from a shadow library, so that one goes to Open Library
    if kind == "books":
        got = _openlibrary_search(cites, query, n)
        if got.get("results"):
            got["next_step"] = ("Catalogue records only. web_fetch the Open Library page, or "
                                "search the web for the text itself.")
            return got
        kind = "text"   # nothing catalogued; fall through to a web search

    rows, engine, err = [], "", ""
    if _DDGS is not None:
        kw = {"max_results": n, "page": page, "region": region or "us-en",
              "safesearch": "moderate",
              "backend": NEWS_BACKENDS if kind == "news" else TEXT_BACKENDS}
        tl = RECENCY.get((recency or "").lower())
        if tl:
            kw["timelimit"] = tl
        try:
            with _DDGS() as d:
                rows = getattr(d, kind)(query, **kw) or []
            engine = f"web/{kind}"
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
    else:
        err = "the ddgs package is not installed"

    want_host = ""
    if site:
        want_host = re.sub(r"^https?://", "", str(site)).strip("/ ").lower()

    out = []
    seen = set()
    for r in rows:
        link = r.get("href") or r.get("url") or ""
        title = (r.get("title") or "").strip()
        body = (r.get("body") or r.get("excerpt") or r.get("description") or "").strip()
        if not link.startswith("http") or not (title or body):
            continue
        # an engine that ignores site: would otherwise smuggle in whatever it felt like
        if want_host and want_host not in urllib.parse.urlparse(link).netloc.lower():
            continue
        if link in seen:
            continue
        seen.add(link)
        if len(out) >= n:
            break
        extra = {"url": link, "title": title or link}
        for k in ("date", "source", "publisher", "author"):
            if r.get(k):
                extra[k] = r[k]
        marker = cites.add(book_id=link, page=None, cite=title or link,
                           snippet=body, kind="web", extra=extra)
        row = {"cite_as": f"[{marker}]", "title": title or link, "url": link,
               "snippet": body[:400], "outside_corpus": True}
        for k in ("date", "source", "publisher"):
            if r.get(k):
                row[k] = r[k]
        out.append(row)

    if out:
        if want_host:
            out = [x for x in out if want_host in urllib.parse.urlparse(x["url"]).netloc.lower()]
        return {"n": len(out), "page": page, "query": query, "engine": engine,
                "results": out,
                "more": ("Ask again with page=%d for the next set." % (page + 1)),
                "next_step": ("These are titles and snippets, not the pages. web_fetch any "
                              "result whose wording you intend to rely on."),
                "how_to_cite": HOW_TO_CITE_WEB}

    # Nothing from the engine: try the open APIs rather than reporting silence.
    for fb in (_wiki_search, _openlibrary_search):
        alt = fb(cites, query, n)
        if alt.get("results"):
            alt["note"] = f"the search engine returned nothing ({err or 'no results'}); this is {alt['engine']}"
            return alt
    return {"error": f"web search found nothing ({err or 'no results'})", "results": []}


def _wiki_search(cites: Cites, query: str, n: int = 6):
    url = ("https://en.wikipedia.org/w/api.php?action=query&list=search&format=json"
           f"&srlimit={n}&srsearch={urllib.parse.quote(query)}")
    try:
        d = json.loads(_get(url, timeout=20, headers=BROWSER_HEADERS))
    except Exception as e:
        return {"error": f"wikipedia search failed ({e})", "results": []}
    out = []
    for r in (d.get("query", {}).get("search") or [])[:n]:
        title = r.get("title", "")
        link = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
        snip = _strip_html((r.get("snippet") or "").encode())
        marker = cites.add(book_id=link, page=None, cite=title, snippet=snip,
                           kind="web", extra={"url": link, "title": title})
        out.append({"cite_as": f"[{marker}]", "title": title, "url": link,
                    "snippet": snip[:300], "outside_corpus": True})
    return {"n": len(out), "results": out, "engine": "wikipedia",
            "how_to_cite": HOW_TO_CITE_WEB}


def _openlibrary_search(cites: Cites, query: str, n: int = 6):
    """Editions and dates, which is often what a question about an old book wants."""
    url = ("https://openlibrary.org/search.json?limit=%d&fields=title,author_name,"
           "first_publish_year,key&q=%s" % (n, urllib.parse.quote(query)))
    try:
        d = json.loads(_get(url, timeout=20, headers=BROWSER_HEADERS))
    except Exception as e:
        return {"error": f"openlibrary search failed ({e})", "results": []}
    out = []
    for r in (d.get("docs") or [])[:n]:
        title = r.get("title") or ""
        who = ", ".join(r.get("author_name") or [])
        yr = r.get("first_publish_year")
        link = "https://openlibrary.org" + (r.get("key") or "")
        snip = " · ".join(x for x in [who, str(yr) if yr else ""] if x)
        marker = cites.add(book_id=link, page=None, cite=f"{title} ({yr})" if yr else title,
                           snippet=snip, kind="web",
                           extra={"url": link, "title": title})
        out.append({"cite_as": f"[{marker}]", "title": title, "url": link,
                    "snippet": snip, "first_published": yr, "outside_corpus": True})
    return {"n": len(out), "results": out, "engine": "openlibrary",
            "how_to_cite": HOW_TO_CITE_WEB}


_FETCH_CACHE: dict[str, tuple[str, str, str]] = {}   # url -> (title, ctype, text)


def _page_title(raw: bytes) -> str:
    m = re.search(rb"(?is)<title[^>]*>(.*?)</title>", raw)
    return _strip_html(m.group(1)) if m else ""


def web_fetch(cites: Cites, url: str, max_chars: int = 9000, start: int = 0,
              find: str = "", **_):
    """Read one page.

    A search snippet is not evidence; this is how the agent actually reads the
    source. `find` jumps to the part of the page containing a phrase, and
    `start` pages through a document too long for one call — a 200,000-word
    book chapter can be read in pieces rather than truncated once and given up
    on. Pages fetched earlier in the turn are served from memory.
    """
    url = str(url or "").strip()
    if not url.startswith(("http://", "https://")):
        return {"error": "url must be http(s)"}
    max_chars = max(500, min(int(max_chars or 9000), 40000))
    start = max(0, int(start or 0))

    if url in _FETCH_CACHE:
        title, ctype, text = _FETCH_CACHE[url]
        cached = True
    else:
        cached = False
        try:
            req = urllib.request.Request(url, headers=BROWSER_HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                raw = r.read(4_000_000)     # enough for a long article, not a disk image
                final = r.geturl()
        except urllib.error.HTTPError as e:
            return {"error": f"the page answered {e.code} {e.reason}", "url": url}
        except Exception as e:
            return {"error": f"could not fetch that page ({type(e).__name__}: {e})", "url": url}
        if ctype and not (ctype.startswith("text/") or "xml" in ctype or "json" in ctype):
            return {"error": f"that is {ctype}, not a readable page", "url": url,
                    "hint": "web_fetch reads html and text; a PDF or image cannot be read here"}
        title = _page_title(raw)
        text = _strip_html(raw) if "json" not in ctype else raw.decode("utf-8", "replace")
        if final and final != url:
            url = final
        _FETCH_CACHE[url] = (title, ctype, text)

    if not text.strip():
        return {"error": "that page had no readable text", "url": url}

    # `find` wins over `start`: the agent asked for a place, not an offset
    where = start
    if find:
        i = text.lower().find(str(find).lower())
        if i < 0:
            return {"cite_as": None, "url": url, "title": title, "chars": len(text),
                    "found": False,
                    "error": f"{find!r} does not appear on that page",
                    "hint": "call again without `find` to read from the top"}
        where = max(0, i - max_chars // 4)

    chunk = text[where:where + max_chars]
    marker = cites.add(book_id=url, page=None, cite=title or url,
                       snippet=chunk[:300], kind="web",
                       extra={"url": url, "title": title or url})
    more = where + len(chunk) < len(text)
    return {
        "cite_as": f"[{marker}]",
        "url": url, "title": title, "content_type": ctype,
        "chars_total": len(text), "showing": [where, where + len(chunk)],
        "from_cache": cached,
        "text": chunk,
        "more": (f"{len(text) - (where + len(chunk))} characters left; call again with "
                 f"start={where + len(chunk)}" if more else False),
        "outside_corpus": True,
        "how_to_cite": HOW_TO_CITE_WEB,
    }


# ------------------------------------------------------------------ registry
CORPUS_TOOLS = {
    "search_corpus": search_corpus,
    "read_source": read_source,
    "find_concept": find_concept,
    "concept_detail": concept_detail,
    "concept_passages": concept_passages,
    "query_network": query_network,
    "list_authors": list_authors,
    "list_books": list_books,
    "compare_ideas": compare_ideas,
    "verify_quote": verify_quote,
}
WEB_TOOLS = {"web_search": web_search, "web_fetch": web_fetch}
ALL_TOOLS = {**CORPUS_TOOLS, **WEB_TOOLS}


def schemas(allow_web: bool = False):
    """OpenAI-style tool schemas. Descriptions are the agent's instructions:
    the model chooses from these alone, so each says when to reach for it."""
    t = [
        {
            "type": "function",
            "function": {
                "name": "search_corpus",
                "description": (
                    "Search the 90,975 indexed passages. START HERE for almost any "
                    "question about what the texts say. mode='hybrid' (default) blends "
                    "meaning and wording and is the best general choice; 'semantic' is "
                    "pure meaning, for when the corpus would phrase an idea differently "
                    "from the question; 'bm25' or 'keyword' when you need a literal "
                    "word or a rare name. If hybrid returns nothing useful, TRY ANOTHER "
                    "MODE and try rewording in period vocabulary before concluding the "
                    "corpus is silent."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "what to look for"},
                        "mode": {"type": "string", "enum": ["hybrid", "semantic", "bm25", "keyword"]},
                        "top_k": {"type": "integer", "description": "1-25, default 8"},
                        "author": {"type": "string", "description": "restrict to a surname, e.g. Hutcheson"},
                        "period": {"type": "string", "description": "e.g. '1690s' or '1700-1740'"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_source",
                "description": (
                    "Read a page range of one source verbatim. Use when a search snippet "
                    "is not enough to settle what an author actually claims, or to quote "
                    "accurately. Give page_from alone for a small window around it."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "book_id": {"type": "string", "description":
                            "the book_id from a search result, or a citation marker like 'S3'"},
                        "page_from": {"type": "integer"},
                        "page_to": {"type": "integer"},
                    },
                    "required": ["book_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "find_concept",
                "description": (
                    "Find concepts in the curated map by meaning, not spelling — a "
                    "question with no shared words ('what makes an action right?') still "
                    "lands on Moral Obligation and Moral Fitness. Use to get concept_ids "
                    "for concept_detail or concept_passages."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer", "description": "1-20, default 6"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "concept_detail",
                "description": (
                    "One concept with its definition, aliases and the map around it. "
                    "hops=1 gives its direct relations; hops=2 also gives what those "
                    "connect to, which is how you answer 'how does X bear on Y?' or "
                    "trace an argument through the map."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "concept_id": {"type": "string", "description": "id or name; a name is resolved"},
                        "hops": {"type": "integer", "enum": [1, 2]},
                    },
                    "required": ["concept_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "concept_passages",
                "description": (
                    "The verbatim quotes the editors recorded as attesting a concept. "
                    "These are the strongest evidence for what a concept means in this "
                    "corpus; prefer them when the question is about the concept itself."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "concept_id": {"type": "string"},
                        "top_k": {"type": "integer", "description": "1-20, default 8"},
                    },
                    "required": ["concept_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_network",
                "description": (
                    "The concept-and-document network for a query: which concepts it "
                    "touches, which of them merely bridge others, the relations among "
                    "them, and the documents attesting them. Use for a broad or vague "
                    "question, to see the shape of the territory before drilling in."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "n_concepts": {"type": "integer"},
                        "n_docs": {"type": "integer"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_authors",
                "description": (
                    "The 37 creators with sex, life dates, output and the concepts each "
                    "writes about most. Use for questions about who wrote what, or about "
                    "the shape of the corpus rather than its arguments."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "sex": {"type": "string", "enum": ["M", "F"]},
                    },
                },
            },
        },
    ]
    t += [
        {
            "type": "function",
            "function": {
                "name": "verify_quote",
                "description": (
                    "CHECK A QUOTATION BEFORE YOU PRINT IT. Give it the wording you are about "
                    "to put in quotation marks; it says whether those words actually occur in "
                    "the corpus and, if so, exactly as printed. Use it whenever you are quoting "
                    "from memory, whenever you have modernised or tidied a phrase, and whenever "
                    "a claim rests on the precise words. A 'NOT FOUND' verdict means do not "
                    "print it as a quotation."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "quote": {"type": "string", "description": "the wording to check"},
                        "book_id": {"type": "string",
                                    "description": "optional: restrict the check to one book"},
                    },
                    "required": ["quote"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "compare_ideas",
                "description": (
                    "Hold two to four ideas side by side across the whole corpus. Returns how "
                    "close they sit in the embedding space, what the concept map records "
                    "between them, the passages each one owns, and — most usefully — the "
                    "SHARED GROUND: passages where the ideas are argued together rather than "
                    "separately. Reach for this on 'how does X differ from Y', 'did they agree', "
                    "and any question that names two ideas. Items may be concepts from the map "
                    "or free phrases."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "items": {"type": "array", "items": {"type": "string"},
                                  "description": "two to four concepts or phrases"},
                        "top_k": {"type": "integer"},
                    },
                    "required": ["items"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_books",
                "description": (
                    "What is actually on the shelf: the books themselves, filterable by author, "
                    "by the author's sex, and by year. Use it for 'what does this corpus "
                    "contain', 'which women are represented', 'what is here from before 1700', "
                    "and to find the exact book_id to hand to read_source. This lists BOOKS, "
                    "not passages — use search_corpus for what they say."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "author": {"type": "string"},
                        "sex": {"type": "string", "description": "M, F, or leave empty"},
                        "year_from": {"type": "integer"},
                        "year_to": {"type": "integer"},
                    },
                },
            },
        },
    ]
    if allow_web:
        t += [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": (
                        "Search the open web through DuckDuckGo. Only for what the corpus "
                        "cannot supply: a date, a modern scholarly view, an edition history, a "
                        "person or work outside the 197 sources. Never use it in place of the "
                        "corpus for what these texts say, and mark anything it yields as coming "
                        "from outside.\n"
                        "USE IT REPEATEDLY AND NARROW AS YOU GO. The first ten links are rarely "
                        "the answer. page=2, 3 walks further down the same query; site= pins one "
                        "domain (plato.stanford.edu, gutenberg.org, archive.org) once you know "
                        "where the answer lives; kind='books' finds editions and kind='news' "
                        "recent coverage; recency limits how old a result may be. Reword and "
                        "search again rather than settling for a near-miss.\n"
                        "Results are titles and snippets ONLY. A snippet is not evidence: "
                        "web_fetch anything you intend to rely on."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "n": {"type": "integer", "description": "results to return, up to 25"},
                            "page": {"type": "integer",
                                     "description": "1 = the first page; 2, 3 … go deeper"},
                            "site": {"type": "string",
                                     "description": "restrict to one domain, e.g. plato.stanford.edu"},
                            "kind": {"type": "string", "enum": ["text", "news", "books"]},
                            "recency": {"type": "string", "enum": ["day", "week", "month", "year"]},
                            "region": {"type": "string", "description": "e.g. us-en, uk-en"},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "web_fetch",
                    "description": (
                        "Read a web page — the actual text, not a snippet. Call this on any "
                        "search result you are going to quote or rely on.\n"
                        "For a long page: `find` jumps to the passage containing a phrase, and "
                        "`start` continues from a character offset, so a document too long for "
                        "one call can be read in pieces instead of being truncated and "
                        "abandoned. The result tells you how much is left and what offset to "
                        "ask for next. A page already fetched this turn is free to re-read."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "find": {"type": "string",
                                     "description": "jump to the part of the page containing this phrase"},
                            "start": {"type": "integer",
                                      "description": "character offset to read from, for a long page"},
                            "max_chars": {"type": "integer", "description": "up to 40000"},
                        },
                        "required": ["url"],
                    },
                },
            },
    ]
    return t


def run_tool(name: str, args: dict, cites: Cites, allow_web: bool = False):
    fn = ALL_TOOLS.get(name)
    if fn is None:
        return {"error": f"no tool named {name!r}"}
    if name in WEB_TOOLS and not allow_web:
        return {"error": "web access is switched off for this conversation"}
    t0 = time.time()
    try:
        out = fn(cites, **(args or {}))
    except TypeError as e:
        return {"error": f"bad arguments for {name}: {e}"}
    except Exception as e:
        return {"error": f"{name} failed: {e}"}
    if isinstance(out, dict):
        out["took_ms"] = round((time.time() - t0) * 1000)
    return out


def summarise(name: str, result: dict) -> str:
    """One line for the UI's trace, so a reader can see what the agent did."""
    if not isinstance(result, dict):
        return "done"
    if result.get("error"):
        return result["error"]
    if name == "search_corpus":
        return f"{result.get('n', 0)} passages ({result.get('mode')})"
    if name == "read_source":
        return f"{result.get('book', '')} — {result.get('units', 0)} units"
    if name == "find_concept":
        return ", ".join(r["label"] for r in result.get("results", [])[:5]) or "nothing"
    if name == "concept_detail":
        return (f"{result.get('label')} · {len(result.get('hop1') or [])} direct, "
                f"{len(result.get('hop2') or [])} at two hops")
    if name == "concept_passages":
        return f"{result.get('n', 0)} quotes for {result.get('concept')}"
    if name == "query_network":
        return (f"{len(result.get('concepts') or [])} concepts, "
                f"{len(result.get('documents') or [])} documents")
    if name == "list_authors":
        return f"{result.get('n', 0)} authors"
    if name == "list_books":
        return f"{result.get('n', 0)} books"
    if name == "compare_ideas":
        return f"{len(result.get('shared_ground') or [])} passages of shared ground"
    if name == "verify_quote":
        return result.get("verdict", "checked")[:70]
    if name == "web_search":
        return f"{result.get('n', 0)} web results"
    if name == "web_fetch":
        # the field was renamed when paging was added; the trace kept saying 0
        shown = result.get("showing") or [0, 0]
        got = shown[1] - shown[0] if len(shown) == 2 else 0
        total = result.get("chars_total", 0)
        return (f"{got} of {total} chars from {result.get('url', '')[:44]}"
                if total else f"read {result.get('url', '')[:48]}")
    return "done"
