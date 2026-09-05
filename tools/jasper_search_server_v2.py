#!/usr/bin/env python3
"""Jasper semantic search server v2 — retrieval-optimized index.

Improvements over v1 (each measured by tools/eval_retrieval.py):
  * v2 index (models/jasper_index_v2/): noise-filtered (chrome zones,
    publisher furniture, bare folios dropped), tiny-fragment-merged,
    title-prefixed passages ("[An Essay on the Origin of Evil] …") so
    book-level queries match directly.
  * query-side: strip question chrome before embedding (matches the
    passage style; "What is X?" embeds closer to "[Title] X" passages).
  * hybrid rerank unchanged: 0.6·cosine + 0.4·archaic lexical.

Endpoints (same contract as v1):
  POST /semantic   {"query", "top_k"}       -> scored passages
  POST /bm25       {"query", "top_k"}       -> BM25 ranking
  POST /concepts   {"query", "top_k", "mode"} -> semantic concept-map search
  POST /query_graph {"query", n_concepts, n_docs} -> concept+book network
  GET  /healthz

Run:
  python tools/jasper_search_server_v2.py [--port 8790] [--device cuda]
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
MODEL_PATH = REPO / "models" / "Jasper-Token-Compression-600M"
IDX_DIR = REPO / "models" / "jasper_index_v2"

ARCH = {
    "virtue": ["vertue", "virtuous", "vertuous"],
    "virtuous": ["vertuous"],
    "heaven": ["heauen"],
    "heavens": ["heauens"],
    "evil": ["euil"],
    "use": ["vse"],
    "used": ["vsed"],
    "us": ["vs"],
    "upon": ["vpon"],
    "give": ["giue"],
    "given": ["giuen"],
    "over": ["ouer"],
    "self": ["felf"],
    "love": ["loue"],
    "loved": ["loued"],
    "serve": ["ferue", "serue"],
    "service": ["feruice", "seruice"],
    "saviour": ["sauyour"],
}

_state = {}


# ---------------------------------------------------------------- index
def load_index():
    emb = np.load(IDX_DIR / "embeddings.npy").astype(np.float32)
    meta = [json.loads(l) for l in open(IDX_DIR / "meta.jsonl", encoding="utf-8")]
    assert len(meta) == emb.shape[0], f"meta {len(meta)} != emb {emb.shape[0]}"
    for m in meta:
        # v2 meta carries `raw_text` (original chunk) + `prefix` (title/zone
        # used at embed time). Display/search uses raw_text.
        if "raw_text" not in m:
            m["raw_text"] = m.get("text") or m.get("prefix") or ""
        m["text"] = m["raw_text"]
        m["text_l"] = m["text"].lower()
    cemb = None
    cids = []
    cpath = REPO / "models" / "jasper_index" / "concepts.npy"
    if cpath.exists():
        cemb = np.load(cpath).astype(np.float32)
        cids = json.loads(
            (REPO / "models" / "jasper_index" / "concepts_meta.json").read_text()
        )
    return emb, meta, cemb, cids


def load_model(device: str):
    import torch
    from sentence_transformers import SentenceTransformer

    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    return SentenceTransformer(
        str(MODEL_PATH),
        model_kwargs={
            "torch_dtype": dtype,
            "attn_implementation": "sdpa",
            "trust_remote_code": True,
        },
        trust_remote_code=True,
        device=device,
    )


def work_key(book_id: str) -> str:
    """Normalize a book_id to the WORK level (editions/parts collapse).

    'Watts Philosophical Essays 1733 (part 2)', 'WATTS_1733_...-essays' and
    'Watts ... 1742 3rd ed (part 1)' all map to 'watts philosophical essays'
    so the per-work cap (3) limits cross-edition crowding in results.
    """
    b = re.sub(r"[\(\)]", " ", (book_id or "").lower())
    b = re.sub(r"[_\-]+", " ", b)
    b = re.sub(
        r"\b(3rd|2nd|1st|4th|new|ed(ition)?s?|part\s*\d*|vol\.?\s*\d*|copy of)\b",
        " ",
        b,
    )
    # ALL 4-digit years (ranges like 1731 1732 leave both, fine for identity)
    b = re.sub(r"\b(1[4-9]\d\d|20\d\d)\b", " ", b)
    b = re.sub(r"\s+", " ", b).strip()
    return b[:45]


def variants_for(word: str):
    vs = {word}
    if "s" in word:
        vs.add(word.replace("s", "f"))
    if "f" in word:
        vs.add(word.replace("f", "s"))
    if word in ARCH:
        vs.update(ARCH[word])
    return vs


# Function words carry no retrieval signal but used to saturate the lexical
# score to 1.00 for every candidate ("self-love AND benevolence" scored the
# same as "self-love benevolence"), so the hybrid blend lost all lexical
# discrimination. They are dropped from the lexical/graph term lists.
LEX_STOP = frozenset(
    """the a an and or but nor for yet so of in on at to from by with about as
    into over after before between under above is are was were be been being am
    do does did have has had having will would shall should may might must can
    could that this these those there their it its his her him she he they them
    we you your our not no all any some such which who whom whose what when
    where why how than then thus also more most much many very upon whether if
    either neither both each other others another same own one two say said
    let make made take taken come came go went thing things way ways""".split()
) - frozenset(
    # words that are function words in general English but load-bearing terms
    # here: "the will", "the good", "right"/"end" as moral vocabulary
    "will good right end".split()
)


def query_terms(q: str, *, keep_stop: bool = False):
    """Content words of a query, longest-first (>=3 chars, stopwords dropped)."""
    ws = [w for w in re.split(r"\W+", (q or "").lower()) if len(w) > 2]
    if not keep_stop:
        content = [w for w in ws if w not in LEX_STOP]
        if content:
            ws = content
    seen, out = set(), []
    for w in ws:
        if w not in seen:
            seen.add(w)
            out.append(w)
    return out


def lexical_overlap(query_terms_, text_l, idf=None):
    """IDF-weighted coverage + phrase-proximity bonus, in [0, 1].

    Coverage alone saturated at 1.0 whenever every query word appeared
    anywhere in a 400-char chunk. Weighting each term by its rarity and
    adding a bonus when the matches sit close together separates a passage
    that merely mentions the words from one that is actually about them.
    """
    if not query_terms_ or not text_l:
        return 0.0
    tot_w, hit_w, positions = 0.0, 0.0, []
    for vs in query_terms_:
        head = next(iter(vs)) if not isinstance(vs, (list, tuple)) else vs[0]
        w = (idf or {}).get(head, 1.0)
        tot_w += w
        best = -1
        for v in vs:
            i = text_l.find(v)
            if i >= 0 and (best < 0 or i < best):
                best = i
        if best >= 0:
            hit_w += w
            positions.append(best)
    if tot_w <= 0:
        return 0.0
    cover = hit_w / tot_w
    prox = 0.0
    if len(positions) > 1:
        span = max(positions) - min(positions)
        # all terms inside ~140 chars (a sentence or two) -> full bonus
        prox = max(0.0, 1.0 - span / 400.0)
    return min(1.0, 0.82 * cover + 0.18 * prox * cover)


QUESTION_CHROME = re.compile(
    r"^(the user seeks (information|passages) (on|about|which)[^.]*\.|"
    r"documents should (focus|include|analyse)[^.]*\.|"
    r"relevant (documents|passages|texts) should[^.]*\.|"
    r"what is|what are|who is|which|how does|why does|"
    r"please (find|show|search)[\s,]*)",
    re.I,
)


def clean_query(q: str) -> str:
    """Strip research-query chrome so the embedding matches passage style."""
    q = QUESTION_CHROME.sub("", q.strip())
    return re.sub(r"\s+", " ", q).strip() or q


# ------------------------------------------------------- query embedding cache
# On CPU a Jasper encode costs ~10s. One user query hits the model up to three
# times (passages, then a mode switch, then the query graph), so the same
# vector was recomputed for a 30s round trip. Caching by cleaned query makes
# every repeat instant and is what makes CPU mode usable at all.
_QCACHE: "OrderedDict[str, np.ndarray]" = None  # set in main()
_QCACHE_MAX = 256
_QSTATS = {"hits": 0, "misses": 0}


def embed_query(q: str) -> np.ndarray:
    global _QCACHE
    if _QCACHE is None:
        from collections import OrderedDict

        _QCACHE = OrderedDict()
    key = clean_query(q)
    hit = _QCACHE.get(key)
    if hit is not None:
        _QCACHE.move_to_end(key)
        _QSTATS["hits"] += 1
        return hit
    _QSTATS["misses"] += 1
    vec = (
        _state["model"]
        .encode(
            [key],
            prompt_name="query",
            normalize_embeddings=True,
            compression_ratio=0.3333,
            convert_to_numpy=True,
        )[0]
        .astype(np.float32)
    )
    _QCACHE[key] = vec
    while len(_QCACHE) > _QCACHE_MAX:
        _QCACHE.popitem(last=False)
    return vec


def clear_query_cache():
    """Vectors are device-independent (numpy), but a device switch may change
    dtype/precision, so drop the cache to keep scores self-consistent."""
    if _QCACHE is not None:
        _QCACHE.clear()


# ------------------------------------------------------------------- citations
_ROMAN = re.compile(r"^(?:[ivxlcdm]+)$", re.I)
_STOPCAP = {"and", "of", "the", "or", "on", "in", "to", "a", "an", "with", "de"}


def _titlecase(s: str) -> str:
    out = []
    for i, w in enumerate(s.split()):
        lw = w.lower()
        if len(w) > 1 and w.isupper() and _ROMAN.match(w):
            out.append(w.upper())  # genuine roman numeral (vol. III)
        elif i and lw in _STOPCAP:
            out.append(lw)
        elif w.isupper():
            out.append(lw[:1].upper() + lw[1:])  # CLARKE -> Clarke
        else:
            out.append(w[:1].upper() + w[1:] if w else w)
    return " ".join(out)


def parse_book_id(book_id: str) -> dict:
    """Turn a raw book_id into display fields.

    Two shapes exist in the corpus:
      OCR  'CLARKE_1706_1708_A-Discourse-concerning-the-...'  (AUTHOR_YEAR_REPRINT_Title)
      TXT  'Turnbull The Principles of Moral and Christian Philosophy vol. 1'

    Returns {author, year, title, volume, cite} — 'cite' is the one-line
    human form the UI shows instead of the raw id.
    """
    raw = (book_id or "").strip()
    if not raw:
        return {"author": "", "year": None, "title": "", "volume": "", "cite": ""}
    author = year = None
    volume = ""
    parts = raw.split("_")
    # OCR shape: first segment is an ALL-CAPS author token, second a 4-digit year
    _AUTHOR_SEG = r"[A-Z][A-Za-z\-]*(-and-[A-Z][A-Za-z\-]*)?"
    if len(parts) >= 2 and re.fullmatch(_AUTHOR_SEG, parts[0]) and (
        parts[0].isupper() or re.fullmatch(r"\d{4}(-\d{4})?", parts[1])
    ):
        author = parts[0].replace("-and-", " & ").replace("-", " ")
        author = " & ".join(_titlecase(a) for a in author.split(" & "))
        if author.lower() == "anon":
            author = "Anonymous"
        rest = parts[1:]
        if re.fullmatch(r"\d{4}(-\d{4})?", rest[0]):
            year = rest[0].split("-")[0]
            rest = rest[1:]
        # optional reprint/edition year ('0' means none)
        if rest and re.fullmatch(r"\d{1,4}", rest[0]):
            rest = rest[1:]
        # trailing volume marker '_0' / '_2'
        while rest and re.fullmatch(r"\d{1,2}", rest[-1]):
            v = rest.pop()
            if v != "0":
                volume = f"vol. {v}"
        title = _titlecase(" ".join(rest).replace("-", " ").replace("_", " "))
    else:
        # TXT shape: 'Author Rest of the title...'
        m = re.match(r"([A-Z][a-zA-Z'\-]+)\s+(.*)", raw)
        if m:
            author, title = m.group(1), m.group(2)
        else:
            title = raw
        title = title.replace("_", " ")
        ym = re.search(r"\b(1[4-9]\d\d|20\d\d)\b", title)
        if ym:
            year = ym.group(1)
        vm = re.search(r"\b(vol\.?\s*\d+|part\s*\d+)\b", title, re.I)
        if vm:
            volume = vm.group(1)
            title = (title[: vm.start()] + title[vm.end() :]).strip(" ,")
        if year:
            title = title.replace(year, " ")  # year moves to the (1733) suffix
    title = re.sub(r"\(\s*\)|\[\s*\]", " ", title or "")  # empties left by extraction
    title = re.sub(r"\s+", " ", title).strip(" ,.-")
    if not title and author:  # e.g. 'Whartonia vol. 2' -> the name IS the work
        title, author = author, ""
    cite = title
    if author:
        cite = f"{author}, {title}" if title else author
    if volume:
        cite += f", {volume}"
    if year:
        cite += f" ({year})"
    return {
        "author": author or "",
        "year": year,
        "title": title,
        "volume": volume,
        "cite": cite,
    }


_CITE_CACHE = {}


def cite_for(book_id: str) -> dict:
    c = _CITE_CACHE.get(book_id)
    if c is None:
        c = parse_book_id(book_id)
        _CITE_CACHE[book_id] = c
    return c


# --------------------------------------------------------------------- snippets
_OCR_NOISE = [
    (re.compile(r"\$[^$]{0,60}\$"), " "),          # $ \parallel^{4 2}$ math fragments
    (re.compile(r"\\[a-zA-Z]+\s*"), " "),          # stray \circ, \parallel
    (re.compile(r"\{|\}|\^"), " "),
    (re.compile(r"_([A-Za-z][^_]{0,40})_"), r"\1"),  # _emphasis_ markers
    (re.compile(r"\s+([,.;:!?])"), r"\1"),
    (re.compile(r"[ \t]{2,}"), " "),
]


def clean_display(t: str) -> str:
    """Strip OCR/markup artifacts that are meaningless to a reader."""
    for rx, rep in _OCR_NOISE:
        t = rx.sub(rep, t)
    return t.strip()


def make_snippet(text: str, words, width: int = 340) -> str:
    """A readable window around the densest cluster of query terms.

    The old version cut a fixed [-100, +200] slice around the *first* match,
    which routinely began and ended mid-word ('...at the grea'). This centres
    on the best-covered region and snaps both edges to word boundaries.
    """
    t = clean_display(re.sub(r"[ \t]*\n[ \t]*", " ", text or ""))
    if not t:
        return ""
    tl = t.lower()
    hits = []
    for w in words or []:
        start = 0
        while len(hits) < 200:
            i = tl.find(w, start)
            if i < 0:
                break
            hits.append(i)
            start = i + max(1, len(w))
    if not hits:
        cut = t[:width]
        return (cut.rsplit(" ", 1)[0] if len(t) > width else cut).rstrip(" ,;") + (
            "…" if len(t) > width else ""
        )
    hits.sort()
    # window with the most distinct hits inside `width`
    best_i, best_n = hits[0], 0
    for i, h in enumerate(hits):
        n = sum(1 for x in hits[i:] if x - h <= width)
        if n > best_n:
            best_n, best_i = n, h
    lo = max(0, best_i - width // 3)
    hi = min(len(t), lo + width)
    if lo > 0:
        sp = t.find(" ", lo)
        lo = sp + 1 if 0 <= sp < lo + 30 else lo
    if hi < len(t):
        sp = t.rfind(" ", lo, hi)
        hi = sp if sp > lo + 40 else hi
    out = t[lo:hi].strip()
    return ("…" if lo > 0 else "") + out + ("…" if hi < len(t) else "")


# ----------------------------------------------------------------------- facets
def build_facets(results):
    """Author / period / source counts for the result-list facet rail."""
    authors, periods, works = {}, {}, {}
    for r in results:
        c = r.get("_cite") or cite_for(r.get("book_id", ""))
        a = c["author"] or "unattributed"
        authors[a] = authors.get(a, 0) + 1
        wk = c["title"][:60] or r.get("book_id", "")
        works[wk] = works.get(wk, 0) + 1
        y = c["year"]
        if y:
            d = f"{int(y) // 10 * 10}s"
            periods[d] = periods.get(d, 0) + 1
    top = lambda d, n: [  # noqa: E731
        {"value": k, "count": v} for k, v in sorted(d.items(), key=lambda x: (-x[1], x[0]))[:n]
    ]
    return {
        "authors": top(authors, 24),
        "periods": sorted(
            ({"value": k, "count": v} for k, v in periods.items()),
            key=lambda x: x["value"],
        ),
        "works": top(works, 24),
    }


# ---------------------------------------------------------------- bm25
def build_bm25_index():
    """Postings-list BM25.

    The previous build kept the full token list of every passage and rescored
    all 90,975 of them per query in Python. It also never ran: `s, dl, norm =
    0.0, len(toks), k1 * (... dl ...)` reads `dl` while the tuple is still
    being evaluated, so every /bm25 call raised UnboundLocalError. Postings
    fix both — scoring now touches only the passages that contain a query
    term, and doc lengths are computed once at build time.
    """
    meta = _state["meta"]
    postings: dict[str, dict[int, int]] = {}
    doclen = np.zeros(len(meta), dtype=np.int32)
    for i, m in enumerate(meta):
        tf: dict[str, int] = {}
        n = 0
        for w in re.split(r"\W+", m["text_l"]):
            if len(w) < 2:
                continue
            forms = [w]
            # long-s OCR confusion: "vertue"/"felf" ↔ "vertue"/"self"
            if "s" in w and "f" not in w:
                forms.append(w.replace("s", "f"))
            if "f" in w and "s" not in w:
                forms.append(w.replace("f", "s"))
            for t in forms:
                tf[t] = tf.get(t, 0) + 1
                n += 1
        doclen[i] = n
        for t, c in tf.items():
            postings.setdefault(t, {})[i] = c
    N = len(meta)
    # freeze each posting list into parallel numpy arrays for vectorised scoring
    frozen = {
        t: (
            np.fromiter(d.keys(), dtype=np.int32, count=len(d)),
            np.fromiter(d.values(), dtype=np.float32, count=len(d)),
        )
        for t, d in postings.items()
    }
    df = {t: len(d) for t, d in postings.items()}
    _state.update(
        bm25_post=frozen,
        bm25_df=df,
        bm25_N=N,
        bm25_doclen=doclen.astype(np.float32),
        bm25_avgdl=float(doclen.mean()) if N else 1.0,
    )
    # idf for the hybrid lexical score: rare words (benevolence) should count
    # far more than common ones (nature), which flat coverage ignored.
    idf = {}
    for t, n_t in df.items():
        idf[t] = max(0.05, math.log((N - n_t + 0.5) / (n_t + 0.5) + 1.0))
    hi = max(idf.values()) if idf else 1.0
    _state["idf"] = {t: v / hi for t, v in idf.items()}
    print(f"BM25 index: {N:,} docs, vocab {len(df):,}; idf table built")


def bm25_search(query: str, top_k: int = 40, k1: float = 1.5, b: float = 0.75):
    if not query.strip() or "bm25_post" not in _state:
        return {"query": query, "n": 0, "results": []}
    t0 = time.time()
    meta = _state["meta"]
    post, df = _state["bm25_post"], _state["bm25_df"]
    N, avgdl, doclen = _state["bm25_N"], _state["bm25_avgdl"], _state["bm25_doclen"]
    words = query_terms(query)
    qterms = []
    for w in words:
        for v in variants_for(w):
            if v not in qterms:
                qterms.append(v)
    scores = np.zeros(N, dtype=np.float32)
    hit_any = False
    norm = k1 * (1 - b + b * doclen / max(avgdl, 1e-6))
    for qt in qterms:
        pl = post.get(qt)
        if pl is None:
            continue
        hit_any = True
        ids, tfs = pl
        n_t = df[qt]
        w_idf = math.log(1 + (N - n_t + 0.5) / (n_t + 0.5))
        scores[ids] += w_idf * (tfs * (k1 + 1)) / (tfs + norm[ids])
    if not hit_any:
        return {"query": query, "n": 0, "mode": "bm25", "results": []}
    pool = min(N, max(top_k * 20, 400))
    cand = np.argpartition(-scores, pool - 1)[:pool]
    cand = cand[np.argsort(-scores[cand])]
    per_work, results = {}, []
    seen = set()
    for i in cand:
        sc = float(scores[i])
        if sc <= 0:
            break
        m = meta[i]
        wk = work_key(m["book_id"])
        if per_work.get(wk, 0) >= 3:
            continue
        dup = re.sub(r"\s+", " ", m["text"][:120]).strip().lower()
        if dup in seen:
            continue
        seen.add(dup)
        per_work[wk] = per_work.get(wk, 0) + 1
        c = cite_for(m["book_id"])
        results.append(
            {
                "book_id": m["book_id"],
                "page": m["page"],
                "printed_page": m.get("printed_page"),
                "source": m.get("source"),
                "author": c["author"],
                "year": c["year"],
                "title": c["title"],
                "volume": c["volume"],
                "cite": c["cite"],
                "score": round(sc, 4),
                "snippet": make_snippet(m["text"], words),
                "bbox_pts": m.get("bbox_pts"),
                "count": 1,
            }
        )
        if len(results) >= top_k:
            break
    return {
        "query": query,
        "n": len(results),
        "mode": "bm25",
        "terms": words,
        "facets": build_facets(results),
        "took_ms": round((time.time() - t0) * 1000),
        "results": results,
    }


# ---------------------------------------------------------------- graph
def build_query_graph(query: str, n_concepts: int = 8, n_docs: int = 24):
    if not query.strip():
        return {
            "query": "",
            "concepts": [],
            "docs": [],
            "c2c": [],
            "c2d": [],
            "d2d": [],
        }
    qv = embed_query(query)

    concepts, matched_ids = [], set()
    cemb, cids, cnodes = (
        _state.get("cemb"),
        _state.get("cids") or [],
        _state.get("cnodes") or {},
    )
    if cemb is not None and len(cids):
        csims = cemb @ qv
        for ci in np.argsort(-csims)[: max(n_concepts * 3, 24)]:
            cid = cids[ci]
            node = cnodes.get(cid)
            if not node:
                continue
            concepts.append(
                {
                    "id": cid,
                    "label": node.get("label", cid),
                    "score": round(float(csims[ci]), 4),
                    "category": node.get("category", []),
                    "definition": (node.get("definition") or "")[:200],
                }
            )
            matched_ids.add(cid)
            if len(concepts) >= n_concepts:
                break
    cedges_all = _state.get("cedges") or []
    nbr = {}
    for e in cedges_all:
        if e["s"] in matched_ids and e["t"] not in matched_ids:
            nbr[e["t"]] = nbr.get(e["t"], 0) + e["w"]
        if e["t"] in matched_ids and e["s"] not in matched_ids:
            nbr[e["s"]] = nbr.get(e["s"], 0) + e["w"]
    for cid, sc in sorted(nbr.items(), key=lambda x: -x[1])[:n_concepts]:
        node = cnodes.get(cid)
        if not node:
            continue
        concepts.append(
            {
                "id": cid,
                "label": node.get("label", cid),
                "score": round(float(sc) / 3.0, 4),
                "category": node.get("category", []),
                "definition": (node.get("definition") or "")[:200],
                "match": "bridge",
            }
        )
        matched_ids.add(cid)

    emb, meta = _state["emb"], _state["meta"]
    sims = emb @ qv
    pool = min(max(n_docs * 6, 120), 600)
    cand = np.argpartition(-sims, pool - 1)[:pool]
    words = [w for w in re.split(r"\W+", query.lower()) if len(w) > 2]
    terms = [variants_for(w) for w in words]
    scored = []
    for ci in cand:
        m = meta[ci]
        lex = lexical_overlap(terms, m["text_l"]) if terms else 0.0
        scored.append((0.6 * float(sims[ci]) + 0.4 * lex, float(sims[ci]), ci))
    scored.sort(key=lambda x: -x[0])
    per_book, docs = {}, []
    for score, sem, ci in scored:
        m = meta[ci]
        bid = m["book_id"]
        if per_book.get(bid, 0) >= 3:
            continue
        per_book[bid] = per_book.get(bid, 0) + 1
        docs.append(
            {
                "book_id": bid,
                "page": m["page"],
                "printed_page": m.get("printed_page"),
                "score": round(score, 4),
                "semantic": round(sem, 4),
                "snippet": (m["text"][:160] + "…")
                if len(m["text"]) > 160
                else m["text"],
                "bbox_pts": m.get("bbox_pts"),
            }
        )
        if len(docs) >= n_docs:
            break

    c2c = [
        {"s": e["s"], "t": e["t"], "r": e["r"], "w": e["w"]}
        for e in (_state.get("cedges") or [])
        if e["s"] in matched_ids and e["t"] in matched_ids
    ]
    c2b = _state.get("c2b") or {}
    c2d, seen = [], set()
    for c in concepts:
        for d in docs:
            if (
                d["book_id"] in c2b.get(c["id"], set())
                and (c["id"], d["book_id"]) not in seen
            ):
                seen.add((c["id"], d["book_id"]))
                c2d.append({"concept": c["id"], "book": d["book_id"], "w": 0.6})
    d2d, by_book = [], {}
    for i, d in enumerate(docs):
        by_book.setdefault(d["book_id"], []).append(i)
    for idxs in by_book.values():
        for i in range(len(idxs)):
            for j in range(i + 1, len(idxs)):
                d2d.append({"a": idxs[i], "b": idxs[j], "w": 0.3})
    return {
        "query": query,
        "concepts": concepts,
        "docs": docs,
        "c2c": c2c,
        "c2d": c2d,
        "d2d": d2d,
    }


# ---------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/healthz"):
            self._json(
                200,
                {
                    "status": "ok",
                    "index": _state["n"],
                    "dim": int(_state["emb"].shape[1]),
                    "books": _state.get("n_books", 0),
                    "concepts": len(_state.get("cids") or []),
                    "device": _state.get("device", "cpu"),
                    "cache": {
                        "size": len(_QCACHE or ()),
                        "hits": _QSTATS["hits"],
                        "misses": _QSTATS["misses"],
                    },
                },
            )
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length) or b"{}")
        except Exception as e:
            self._json(400, {"error": str(e)})
            return
        try:
            if self.path == "/query_graph":
                self._json(
                    200,
                    build_query_graph(
                        req.get("query", ""),
                        int(req.get("n_concepts", 8)),
                        int(req.get("n_docs", 24)),
                    ),
                )
            elif self.path == "/bm25":
                self._json(
                    200, bm25_search(req.get("query", ""), int(req.get("top_k", 40)))
                )
            elif self.path == "/semantic":
                self._json(
                    200,
                    semantic_search(
                        req.get("query", ""),
                        int(req.get("top_k", 20)),
                        mode=req.get("mode", "hybrid"),
                    ),
                )
            elif self.path == "/concepts":
                self._json(
                    200,
                    concept_search(
                        req.get("query", ""),
                        int(req.get("top_k", 20)),
                        mode=req.get("mode", "hybrid"),
                    ),
                )
            elif self.path == "/device":
                self._json(200, handle_device_request(req))
            else:
                self._json(404, {"error": "not found"})
        except Exception as e:
            self._json(500, {"error": str(e)})

    def log_message(self, fmt, *args):  # noqa: A002
        import sys

        sys.stderr.write("[jasper-v2] " + (fmt % args) + "\n")


def handle_device_request(req: dict) -> dict:
    """POST /device {"action": "get"|"switch", "device": "cpu"|"cuda"}

    get:    -> {"device": current, "available": {cpu: true, cuda: bool}}
    switch: moves the model to the requested device IN-PROCESS (no restart),
            reports the new device + load time.
    """
    import torch

    action = req.get("action", "get")
    cuda_ok = torch.cuda.is_available()
    if action == "get":
        return {
            "device": _state.get("device", "cpu"),
            "available": {"cpu": True, "cuda": cuda_ok},
        }
    if action == "switch":
        target = req.get("device", "cpu")
        if target == "cuda" and not cuda_ok:
            return {"error": "cuda not available", "device": _state.get("device")}
        if target not in ("cpu", "cuda"):
            return {"error": f"unknown device {target}"}
        current = _state.get("device")
        if current == target:
            return {"device": target, "changed": False}
        t0 = time.time()
        model = _state["model"]
        try:
            # sentence-transformers: move submodules then the ST wrapper
            model._target_device = torch.device(target)
            for module in model.modules():
                try:
                    module.to(target)
                except Exception:
                    pass
            # free the old device's cache when leaving cuda
            if current == "cuda":
                torch.cuda.empty_cache()
            _state["device"] = target
            clear_query_cache()
            return {
                "device": target,
                "changed": True,
                "took_ms": round((time.time() - t0) * 1000),
            }
        except Exception as e:
            return {"error": str(e), "device": _state.get("device")}
    return {"error": f"unknown action {action}"}


def semantic_search(query: str, top_k: int, mode: str = "hybrid"):
    """mode: 'hybrid' (0.6·cosine + 0.4·lexical) or 'semantic' (pure cosine).

    Pure semantic keeps the full cosine ranking untouched — the embedding
    space IS the ranking — with the same work-cap + near-dup diversity
    filters so one book doesn't crowd the top-k.
    """
    query = (query or "").strip()
    if not query:
        return {"query": "", "n": 0, "results": [], "mode": mode}
    t0 = time.time()
    qv = embed_query(query)
    emb, meta = _state["emb"], _state["meta"]
    sims = emb @ qv
    pool = min(max(top_k * 8, 160), 800)
    cand = np.argpartition(-sims, pool - 1)[:pool]
    words = query_terms(query)
    terms = [sorted(variants_for(w), key=lambda v: (v != w, v)) for w in words]
    idf = _state.get("idf") or {}
    scored = []
    for ci in cand:
        m = meta[ci]
        lex = lexical_overlap(terms, m["text_l"], idf) if terms else 0.0
        if mode == "semantic":
            score = float(sims[ci])  # pure cosine — the index IS the ranking
        else:
            score = 0.6 * float(sims[ci]) + 0.4 * lex
        scored.append((score, float(sims[ci]), lex, ci))
    scored.sort(key=lambda x: -x[0])
    per_work, results = {}, []  # per-WORK cap: editions collapse together
    seen_snippets = set()
    for score, sem, lex, ci in scored:
        m = meta[ci]
        wk = work_key(m["book_id"])
        if per_work.get(wk, 0) >= 3:
            continue
        # near-dup key: normalized 100-char window from the passage core
        core = re.sub(r"\s+", " ", m["text"][200:300]).strip().lower()
        dup_key = (
            core
            if len(core) > 40
            else re.sub(r"\s+", " ", m["text"][:100]).strip().lower()
        )
        if dup_key in seen_snippets:
            continue
        seen_snippets.add(dup_key)
        per_work[wk] = per_work.get(wk, 0) + 1
        c = cite_for(m["book_id"])
        results.append(
            {
                "book_id": m["book_id"],
                "page": m["page"],
                "printed_page": m.get("printed_page"),
                "block_id": m.get("block_id"),
                "zone": m.get("zone"),
                "bbox_pts": m.get("bbox_pts"),
                "source": m.get("source"),
                "author": c["author"],
                "year": c["year"],
                "title": c["title"],
                "volume": c["volume"],
                "cite": c["cite"],
                "text": m["text"][:400],
                "snippet": make_snippet(m["text"], words),
                "score": round(score, 4),
                "semantic": round(sem, 4),
                "lexical": round(lex, 3),
                "_cite": c,
            }
        )
        if len(results) >= top_k:
            break
    facets = build_facets(results)
    for r in results:
        r.pop("_cite", None)
    return {
        "query": query,
        "n": len(results),
        "mode": mode,
        "terms": words,
        "facets": facets,
        "device": _state.get("device", "cpu"),
        "cached": _QSTATS["hits"],
        "took_ms": round((time.time() - t0) * 1000),
        "results": results,
    }


def concept_search(query: str, top_k: int = 20, mode: str = "hybrid"):
    """Rank the concept map itself against the query.

    The 202 concept vectors were already loaded but never exposed: concept
    lookup in the UI was pure string matching, so a question like "what makes
    an action right?" matched no concept at all. This ranks every concept by
    cosine on its embedding, optionally blended with a label/alias lexical
    score, and returns the graph node payload the UI needs to render cards.
    """
    query = (query or "").strip()
    cemb, cids = _state.get("cemb"), _state.get("cids") or []
    cnodes = _state.get("cnodes") or {}
    if not query or cemb is None or not len(cids):
        return {"query": query, "n": 0, "results": [], "mode": mode}
    t0 = time.time()
    qv = embed_query(query)
    csims = cemb @ qv
    words = query_terms(query)
    c2b = _state.get("c2b") or {}
    out = []
    for i in np.argsort(-csims)[: max(top_k * 3, 40)]:
        cid = cids[i]
        node = cnodes.get(cid)
        if not node:
            continue
        sem = float(csims[i])
        label_l = (node.get("label") or cid).lower()
        alias_l = " ".join(node.get("aliases") or []).lower()
        hay = f"{label_l} {cid.replace('_', ' ')} {alias_l}"
        if words:
            hay_words = set(re.split(r"\W+", hay))
            hit = 0
            for w in words:
                if w in hay_words or any(hw.startswith(w) for hw in hay_words):
                    hit += 1
            lex = hit / len(words)
            if label_l == query.lower():
                lex = 1.0
        else:
            lex = 0.0
        score = sem if mode == "semantic" else 0.7 * sem + 0.3 * lex
        out.append(
            {
                "id": cid,
                "label": node.get("label", cid),
                "definition": node.get("definition") or "",
                "aliases": node.get("aliases") or [],
                "category": node.get("category") or [],
                "importance": node.get("importance"),
                "books": len(c2b.get(cid, ())),
                "score": round(score, 4),
                "semantic": round(sem, 4),
                "lexical": round(lex, 3),
            }
        )
    out.sort(key=lambda x: -x["score"])
    return {
        "query": query,
        "n": min(top_k, len(out)),
        "mode": mode,
        "took_ms": round((time.time() - t0) * 1000),
        "results": out[:top_k],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--device", default=None)
    args = ap.parse_args()

    import torch

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")

    print("loading v2 index…")
    emb, meta, cemb, cids = load_index()
    print(
        f"index: {emb.shape[0]:,} passages, dim {emb.shape[1]}"
        + (f"; {len(cids)} concepts" if cemb is not None else "")
    )

    print(f"loading Jasper on {device}…")
    _state["model"] = load_model(device)
    _state["device"] = device
    _state.update(
        emb=emb,
        meta=meta,
        n=emb.shape[0],
        cemb=cemb,
        cids=cids,
        n_books=len({m["book_id"] for m in meta}),
    )

    graph_path = REPO / "Concept Maps" / "final" / "concept_graph.jsonl"
    inv_path = REPO / "Concept Maps" / "final" / "inverted_index.jsonl"
    if graph_path.exists():
        cnodes, cedges = {}, []
        for line in open(graph_path, encoding="utf-8"):
            d = json.loads(line)
            if d.get("type") == "node":
                cnodes[d["id"]] = d
            else:
                cedges.append(
                    {
                        "s": d["source"],
                        "t": d["target"],
                        "r": d["relation"],
                        "w": d.get("strength", 0.5),
                    }
                )
        _state.update(cnodes=cnodes, cedges=cedges)
        c2b = {}
        if inv_path.exists():
            for line in open(inv_path, encoding="utf-8"):
                d = json.loads(line)
                c2b.setdefault(d["concept_id"], set()).add(d["book_id"])
        _state["c2b"] = c2b
        print(f"concept map: {len(cnodes)} nodes, {len(cedges)} edges")
    build_bm25_index()

    class DualStackServer(ThreadingHTTPServer):
        address_family = __import__("socket").AF_INET6

        def server_bind(self):
            import socket as _s

            # IPV6_V6ONLY is platform-specific; use the numeric fallback (26)
            v6only = getattr(_s, "IPV6_V6ONLY", 26)
            self.socket.setsockopt(_s.IPPROTO_IPV6, v6only, 0)
            super().server_bind()

    try:
        srv = DualStackServer(("::", args.port), Handler)
    except OSError:
        srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    srv.daemon_threads = True
    print(f"Jasper v2 on http://0.0.0.0:{args.port}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
