#!/usr/bin/env python3
"""Jasper semantic search server for the BMoral corpus.

Loads the prebuilt embedding index (models/jasper_index/) and serves:

  POST /semantic  {"query": "...", "top_k": 20}
      -> {"results": [{book_id, page, printed_page, block_id, zone,
                       bbox_pts, text, snippet, score}]}
          hybrid rerank: semantic score + lexical (archaic-aware) overlap

  GET  /healthz
      -> {"status": "ok", "index": N, "dim": 2048}

Run (GPU when free; falls back to CPU):
  python tools/jasper_search_server.py [--port 8790] [--device cuda]
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
IDX_DIR = REPO / "models" / "jasper_index"

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


def load_index():
    emb = np.load(IDX_DIR / "embeddings.npy").astype(np.float32)
    meta = [json.loads(l) for l in open(IDX_DIR / "meta.jsonl", encoding="utf-8")]
    assert len(meta) == emb.shape[0]
    # concept vectors for query->concept semantic matching
    cemb = None
    cids = []
    cpath = IDX_DIR / "concepts.npy"
    if cpath.exists():
        cemb = np.load(cpath).astype(np.float32)
        cids = json.loads((IDX_DIR / "concepts_meta.json").read_text())
    return emb, meta, cemb, cids


def load_model(device: str):
    import torch
    from sentence_transformers import SentenceTransformer

    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    model = SentenceTransformer(
        str(MODEL_PATH),
        model_kwargs={
            "torch_dtype": dtype,
            "attn_implementation": "sdpa",
            "trust_remote_code": True,
        },
        trust_remote_code=True,
        device=device,
    )
    return model


def lexical_overlap(query_terms, text_l):
    """archaic-aware term coverage of a paragraph (0..1)."""
    if not query_terms:
        return 0.0
    hit = 0
    for vs in query_terms:
        if any(v in text_l for v in vs):
            hit += 1
    return hit / len(query_terms)


def variants_for(word: str):
    vs = {word}
    if "s" in word:
        vs.add(word.replace("s", "f"))
    if "f" in word:
        vs.add(word.replace("f", "s"))
    if word in ARCH:
        vs.update(ARCH[word])
    return vs


def build_bm25_index():
    """Precompute BM25 statistics over all paragraphs (archaic-tokenized)."""
    meta = _state["meta"]
    docs = []
    df = {}
    for m in meta:
        # tokenize with archaic expansion: each raw token + its variants
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
    avgdl = sum(len(d) for d in docs) / max(1, N)
    _state["bm25_docs"] = docs
    _state["bm25_df"] = df
    _state["bm25_N"] = N
    _state["bm25_avgdl"] = avgdl
    print(f"BM25 index: {N:,} docs, avgdl {avgdl:.0f}, vocab {len(df):,}")


def bm25_search(query: str, top_k: int = 40, k1: float = 1.5, b: float = 0.75):
    """Classic BM25 ranking with archaic-spelling expansion."""
    if not query.strip() or "bm25_docs" not in _state:
        return {"query": query, "n": 0, "results": []}
    meta = _state["meta"]
    docs = _state["bm25_docs"]
    df = _state["bm25_df"]
    N = _state["bm25_N"]
    avgdl = _state["bm25_avgdl"]
    # query terms with variants
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
        s = 0.0
        dl = len(toks)
        norm = k1 * (1 - b + b * dl / avgdl)
        for qt in qterms:
            f = tf.get(qt, 0)
            if not f:
                continue
            n_t = df.get(qt, 0)
            idf = math.log(1 + (N - n_t + 0.5) / (n_t + 0.5))
            s += idf * (f * (k1 + 1)) / (f + norm)
        if s > 0:
            scores.append((s, i))
    scores.sort(key=lambda x: -x[0])
    per_book = {}
    results = []
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


def build_query_graph(query: str, n_concepts: int = 8, n_docs: int = 24):
    """Build a concept+book network for a query.

    Nodes: top concepts (semantic match via concept-definition vectors) +
    top documents (semantic passage hits). Edges: concept↔concept (relations
    from the concept map), concept→doc (concept evidence appears in that
    book), doc→doc (same book).
    """
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
        [query],
        prompt_name="query",
        normalize_embeddings=True,
        compression_ratio=0.3333,
        convert_to_numpy=True,
    )[0].astype(np.float32)

    # 1) concepts: cosine vs concept-definition vectors
    concepts = []
    cemb = _state.get("cemb")
    cids = _state.get("cids") or []
    cnodes = _state.get("cnodes") or {}
    if cemb is not None and len(cids):
        csims = cemb @ qv
        top = np.argsort(-csims)[: max(n_concepts * 3, 24)]
        for ci in top:
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
            if len(concepts) >= n_concepts:
                break
    # 1-hop expansion: bridge concepts connect the direct matches through
    # the existing concept map (matched concepts often don't share edges)
    matched_ids = {c["id"] for c in concepts}
    cedges_all = _state.get("cedges") or []
    nbr_score = {}
    for e in cedges_all:
        if e["s"] in matched_ids and e["t"] not in matched_ids:
            nbr_score[e["t"]] = nbr_score.get(e["t"], 0) + e["w"]
        if e["t"] in matched_ids and e["s"] not in matched_ids:
            nbr_score[e["s"]] = nbr_score.get(e["s"], 0) + e["w"]
    for cid, sc in sorted(nbr_score.items(), key=lambda x: -x[1])[:n_concepts]:
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

    # 2) documents: hybrid passage search (compact /semantic logic)
    emb = _state["emb"]
    meta = _state["meta"]
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
    per_book = {}
    docs = []
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

    # 3) concept↔concept edges among matched concepts
    cedges = _state.get("cedges") or []
    cid_set = {c["id"] for c in concepts}
    c2c = [
        {"s": e["s"], "t": e["t"], "r": e["r"], "w": e["w"]}
        for e in cedges
        if e["s"] in cid_set and e["t"] in cid_set
    ]

    # 4) concept→doc edges: concept's books ∩ doc books (from inverted index)
    c2d = []
    c2b = _state.get("c2b") or {}
    for c in concepts:
        cbooks = c2b.get(c["id"], set())
        for d in docs:
            if d["book_id"] in cbooks:
                c2d.append({"concept": c["id"], "book": d["book_id"], "w": 0.6})
    seen = set()
    c2d = [
        x
        for x in c2d
        if (x["concept"], x["book"]) not in seen
        and not seen.add((x["concept"], x["book"]))
    ]

    # 5) doc→doc same-book edges
    d2d = []
    by_book = {}
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


def make_snippet(text: str, terms, width: int = 220) -> str:
    tl = text.lower()
    pos = -1
    for vs in terms:
        for v in vs:
            pos = tl.find(v)
            if pos >= 0:
                break
        if pos >= 0:
            break
    if pos < 0:
        return text[:width] + ("…" if len(text) > width else "")
    start = max(0, pos - 80)
    end = min(len(text), pos + width - 80)
    return (
        ("…" if start > 0 else "") + text[start:end] + ("…" if end < len(text) else "")
    )


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _json(self, code: int, obj):
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
        # CRITICAL: HTTP/1.1 keep-alive requires a terminating body;
        # without Content-Length the browser waits forever on the preflight
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
        if self.path == "/query_graph":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length) or b"{}")
                self._json(
                    200,
                    build_query_graph(
                        req.get("query", ""),
                        int(req.get("n_concepts", 8)),
                        int(req.get("n_docs", 24)),
                    ),
                )
            except Exception as e:
                self._json(500, {"error": str(e)})
            return
        if self.path == "/bm25":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length) or b"{}")
                self._json(
                    200, bm25_search(req.get("query", ""), int(req.get("top_k", 40)))
                )
            except Exception as e:
                self._json(500, {"error": str(e)})
            return
        if self.path != "/semantic":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length) or b"{}")
            query = (req.get("query") or "").strip()
            top_k = min(int(req.get("top_k", 20)), 100)
            if not query:
                self._json(400, {"error": "query required"})
                return
            t0 = time.time()

            # 1) semantic
            model = _state["model"]
            qv = model.encode(
                [query],
                prompt_name="query",
                normalize_embeddings=True,
                compression_ratio=0.3333,
                convert_to_numpy=True,
            )[0].astype(np.float32)
            emb = _state["emb"]
            sims = emb @ qv  # cosine (both normalized)

            # 2) hybrid: take wide semantic pool, rerank with lexical overlap
            pool = min(max(top_k * 6, 120), 600)
            cand = np.argpartition(-sims, pool - 1)[:pool]
            meta = _state["meta"]
            words = [w for w in re.split(r"\W+", query.lower()) if len(w) > 2]
            terms = [variants_for(w) for w in words]
            scored = []
            for ci in cand:
                m = meta[ci]
                lex = lexical_overlap(terms, m["text_l"])
                # hybrid: 0.6 semantic + 0.4 lexical (philosophers' queries are term-heavy)
                score = 0.6 * float(sims[ci]) + 0.4 * lex
                scored.append((score, float(sims[ci]), lex, ci))
            scored.sort(key=lambda x: -x[0])

            # dedup: max 3 paragraphs per book
            per_book = {}
            results = []
            for score, sem, lex, ci in scored:
                m = meta[ci]
                bid = m["book_id"]
                if per_book.get(bid, 0) >= 3:
                    continue
                per_book[bid] = per_book.get(bid, 0) + 1
                results.append(
                    {
                        "book_id": bid,
                        "page": m["page"],
                        "printed_page": m["printed_page"],
                        "block_id": m["block_id"],
                        "zone": m["zone"],
                        "bbox_pts": m["bbox_pts"],
                        "text": m["text"],
                        "snippet": make_snippet(m["text"], terms),
                        "score": round(score, 4),
                        "semantic": round(sem, 4),
                        "lexical": round(lex, 3),
                    }
                )
                if len(results) >= top_k:
                    break
            self._json(
                200,
                {
                    "query": query,
                    "n": len(results),
                    "took_ms": round((time.time() - t0) * 1000),
                    "results": results,
                },
            )
        except Exception as e:
            self._json(500, {"error": str(e)})

    def log_message(self, fmt, *args):
        sys.stderr.write("[jasper] " + (fmt % args) + "\n")


import sys  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--device", default=None)
    args = ap.parse_args()

    import torch

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")

    print("loading index…")
    emb, meta, cemb, cids = load_index()
    for m in meta:
        m["text_l"] = m["text"].lower()
    print(
        f"index: {emb.shape[0]:,} paragraphs, dim {emb.shape[1]}"
        + (f"; {len(cids)} concepts" if cemb is not None else "")
    )

    print(f"loading Jasper on {device}…")
    _state["model"] = load_model(device)
    _state["emb"] = emb
    _state["meta"] = meta
    _state["n"] = emb.shape[0]
    _state["cemb"] = cemb
    _state["cids"] = cids
    # concept map data for the query graph (nodes + edges + book links)
    graph_path = Path("/store/shuvam/BMoral/Concept Maps/final/concept_graph.jsonl")
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
        _state["cnodes"] = cnodes
        _state["cedges"] = cedges
        # concept -> set of book_ids (from the inverted evidence index)
        c2b = {}
        inv_path = Path("/store/shuvam/BMoral/Concept Maps/final/inverted_index.jsonl")
        if inv_path.exists():
            for line in open(inv_path, encoding="utf-8"):
                d = json.loads(line)
                c2b.setdefault(d["concept_id"], set()).add(d["book_id"])
        _state["c2b"] = c2b
        build_bm25_index()
        print(
            f"concept map: {len(cnodes)} nodes, {len(cedges)} edges, {len(c2b)} concept->book sets"
        )

    # dual-stack: bind IPv6 "::" with V6ONLY off so both ::1 (localhost in
    # Chromium) and 127.0.0.1/0.0.0.0 (IPv4) reach the server
    class DualStackServer(ThreadingHTTPServer):
        address_family = __import__("socket").AF_INET6

        def server_bind(self):
            import socket as _s

            self.socket.setsockopt(_s.IPPROTO_IPV6, _s.IPV6_V6ONLY, 0)
            super().server_bind()

    try:
        srv = DualStackServer(("::", args.port), Handler)
    except OSError:
        srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    srv.daemon_threads = True
    print(f"Jasper semantic search on http://0.0.0.0:{args.port}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
