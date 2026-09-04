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


def lexical_overlap(query_terms, text_l):
    if not query_terms or not text_l:
        return 0.0
    hit = sum(1 for vs in query_terms if any(v in text_l for v in vs))
    return hit / len(query_terms)


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


# ---------------------------------------------------------------- bm25
def build_bm25_index():
    meta = _state["meta"]
    docs, df = [], {}
    for m in meta:
        toks = []
        for w in re.split(r"\W+", m["text_l"]):
            if len(w) < 2:
                continue
            toks.append(w)
            if "s" in w and "f" not in w:
                toks.append(w.replace("s", "f"))
            if "f" in w and "s" not in w:
                toks.append(w.replace("f", "s"))
        docs.append(toks)
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    N = len(docs)
    _state.update(
        bm25_docs=docs,
        bm25_df=df,
        bm25_N=N,
        bm25_avgdl=sum(len(d) for d in docs) / max(1, N),
    )
    print(f"BM25 index: {N:,} docs, vocab {len(df):,}")


def bm25_search(query: str, top_k: int = 40, k1: float = 1.5, b: float = 0.75):
    if not query.strip() or "bm25_docs" not in _state:
        return {"query": query, "n": 0, "results": []}
    meta, docs, df = _state["meta"], _state["bm25_docs"], _state["bm25_df"]
    N, avgdl = _state["bm25_N"], _state["bm25_avgdl"]
    qterms = []
    for w in re.split(r"\W+", query.lower()):
        if len(w) < 2:
            continue
        qterms.append(w)
        for v in variants_for(w):
            if v != w and v not in qterms:
                qterms.append(v)
    scores = []
    for i, toks in enumerate(docs):
        tf = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        s, dl, norm = 0.0, len(toks), k1 * (1 - b + b * dl / avgdl)
        for qt in qterms:
            f = tf.get(qt, 0)
            if f:
                n_t = df.get(qt, 0)
                s += (
                    math.log(1 + (N - n_t + 0.5) / (n_t + 0.5))
                    * (f * (k1 + 1))
                    / (f + norm)
                )
        if s > 0:
            scores.append((s, i))
    scores.sort(key=lambda x: -x[0])
    per_book, results = {}, []
    for s, i in scores:
        m = meta[i]
        bid = m["book_id"]
        if per_book.get(bid, 0) >= 3:
            continue
        per_book[bid] = per_book.get(bid, 0) + 1
        pos = m["text_l"].find(qterms[0]) if qterms else -1
        snippet = (
            m["text"][max(0, pos - 100) : pos + 180].replace("\n", " ")
            if pos >= 0
            else m["text"][:180]
        )
        results.append(
            {
                "book_id": bid,
                "page": m["page"],
                "printed_page": m.get("printed_page"),
                "score": round(s, 4),
                "snippet": snippet,
                "bbox_pts": m.get("bbox_pts"),
                "count": 1,
            }
        )
        if len(results) >= top_k:
            break
    return {"query": query, "n": len(results), "results": results}


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
    model = _state["model"]
    qv = model.encode(
        [clean_query(query)],
        prompt_name="query",
        normalize_embeddings=True,
        compression_ratio=0.3333,
        convert_to_numpy=True,
    )[0].astype(np.float32)

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
    model = _state["model"]
    qv = model.encode(
        [clean_query(query)],
        prompt_name="query",
        normalize_embeddings=True,
        compression_ratio=0.3333,
        convert_to_numpy=True,
    )[0].astype(np.float32)
    emb, meta = _state["emb"], _state["meta"]
    sims = emb @ qv
    pool = min(max(top_k * 6, 120), 600)
    cand = np.argpartition(-sims, pool - 1)[:pool]
    words = [w for w in re.split(r"\W+", query.lower()) if len(w) > 2]
    terms = [variants_for(w) for w in words]
    scored = []
    for ci in cand:
        m = meta[ci]
        lex = lexical_overlap(terms, m["text_l"]) if terms else 0.0
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
        pos = m["text_l"].find(words[0]) if words else -1
        snippet = (
            m["text"][max(0, pos - 100) : pos + 200].replace("\n", " ")
            if pos >= 0
            else m["text"][:200]
        )
        results.append(
            {
                "book_id": m["book_id"],
                "page": m["page"],
                "printed_page": m.get("printed_page"),
                "block_id": m.get("block_id"),
                "zone": m.get("zone"),
                "bbox_pts": m.get("bbox_pts"),
                "text": m["text"][:400],
                "snippet": snippet,
                "score": round(score, 4),
                "semantic": round(sem, 4),
                "lexical": round(lex, 3),
            }
        )
        if len(results) >= top_k:
            break
    return {
        "query": query,
        "n": len(results),
        "mode": mode,
        "took_ms": round((time.time() - t0) * 1000),
        "results": results,
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
    _state.update(emb=emb, meta=meta, n=emb.shape[0], cemb=cemb, cids=cids)

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
