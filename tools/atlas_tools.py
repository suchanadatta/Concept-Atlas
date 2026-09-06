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
    out = []
    for d in rows:
        m = cites.add(
            book_id=d.get("book_id"), page=d.get("page"),
            cite=_cite_of(d.get("book_id", "")), snippet=d.get("text") or "",
            bbox_pts=d.get("bbox_pts"), kind="evidence",
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


def web_search(cites: Cites, query: str, n: int = 6, **_):
    """DuckDuckGo's HTML endpoint — no key, and it answers plain GETs."""
    n = max(1, min(int(n or 6), 10))
    try:
        raw = _form_post("https://html.duckduckgo.com/html/",
                         {"q": query, "b": "", "kl": "us-en"})
    except Exception as e:
        raw = ""
        ddg_err = str(e)
    else:
        ddg_err = ""
    out = []
    # result blocks: an anchor with class result__a, then the snippet
    for m in re.finditer(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
        r'(.*?)(?:class="result__snippet"[^>]*>(.*?)</a>)?',
        raw, re.S,
    ):
        href, title, _mid, snip = m.group(1), m.group(2), m.group(3), m.group(4)
        # DDG wraps targets in a redirect; unwrap so the model sees the real host
        q = urllib.parse.urlparse(href).query
        real = urllib.parse.parse_qs(q).get("uddg", [None])[0]
        link = real or href
        if not link.startswith("http"):
            continue
        title_t = _strip_html(title.encode())
        snip_t = _strip_html((snip or "").encode())
        if not title_t:
            continue
        marker = cites.add(book_id=link, page=None, cite=title_t or link,
                           snippet=snip_t, kind="web",
                           extra={"url": link, "title": title_t})
        out.append({"cite_as": f"[{marker}]", "title": title_t, "url": link,
                    "snippet": snip_t[:300], "outside_corpus": True})
        if len(out) >= n:
            break
    if out:
        return {"n": len(out), "results": out, "engine": "duckduckgo",
                "how_to_cite": HOW_TO_CITE_WEB}
    # One search engine is a single point of failure for a tool the agent may
    # genuinely need, so fall back to Wikipedia's open API.
    wiki = _wiki_search(cites, query, n)
    if wiki.get("results"):
        return wiki
    return {"error": f"web search returned nothing ({ddg_err or 'no parseable results'})",
            "results": []}


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


def web_fetch(cites: Cites, url: str, max_chars: int = 8000, **_):
    """One page as text, so a search result can actually be read."""
    if not str(url).startswith(("http://", "https://")):
        return {"error": "url must be http(s)"}
    try:
        raw = _get(url, timeout=25, headers=BROWSER_HEADERS)
    except Exception as e:
        return {"error": f"could not fetch that page ({e})"}
    text = _strip_html(raw)
    if not text:
        return {"error": "that page had no readable text"}
    marker = cites.add(book_id=url, page=None, cite=url, snippet=text[:300],
                       kind="web", extra={"url": url, "title": url})
    return {"cite_as": f"[{marker}]", "url": url, "chars": len(text),
            "outside_corpus": True, "how_to_cite": HOW_TO_CITE_WEB,
            "text": text[:max_chars]}


# ------------------------------------------------------------------ registry
CORPUS_TOOLS = {
    "search_corpus": search_corpus,
    "read_source": read_source,
    "find_concept": find_concept,
    "concept_detail": concept_detail,
    "concept_passages": concept_passages,
    "query_network": query_network,
    "list_authors": list_authors,
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
    if allow_web:
        t += [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": (
                        "Search the open web. Only for what the corpus cannot supply: a "
                        "date, a modern scholarly view, a person or work outside the 197 "
                        "sources. Never use it in place of the corpus for what these "
                        "texts say, and mark anything it yields as coming from outside."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}, "n": {"type": "integer"}},
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "web_fetch",
                    "description": "Fetch one web page as text, to read a web_search result.",
                    "parameters": {
                        "type": "object",
                        "properties": {"url": {"type": "string"}},
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
    if name == "web_search":
        return f"{result.get('n', 0)} web results"
    if name == "web_fetch":
        return f"{result.get('chars', 0)} chars from {result.get('url', '')[:48]}"
    return "done"
