#!/usr/bin/env python3
"""Concept Atlas — static file server for the intranet.

Threading HTTP server with gzip compression and cache headers.
Binds 0.0.0.0 so any machine on the intranet can reach it.

Usage:  python3 serve.py [port]      (default 8788)
"""

import gzip
import json as _json
import os
import re
import sys
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8788
ROOT = os.path.dirname(os.path.abspath(__file__))

GZIP_TYPES = (
    "text/html",
    "text/css",
    "application/javascript",
    "application/json",
    "image/svg+xml",
)
GZIP_MIN = 1400  # bytes


# ———————————————————— Book/Reader API ————————————————————
import json as _json
import urllib.parse

BOOK_DIRS = [
    Path("/store/shuvam/BMoral/data/full_set_pdfs/pdf"),
    Path("/store/shuvam/BMoral/data/BMoral_pdf_collection"),
]
OCR_DIRS = [
    Path("/store/shuvam/BMoral/outputs/full_set"),
    Path("/store/shuvam/BMoral/outputs/corpus"),
]
TXT_DIR = Path("/store/shuvam/BMoral/data/txt_books")
ANN_DIR = Path("/store/shuvam/BMoral/Concept Maps/graph-ui/data/annotations")
ANN_DIR.mkdir(parents=True, exist_ok=True)


def _find_book_pdf(book_id: str):
    """Locate source PDF for a book_id."""
    for d in BOOK_DIRS:
        cand = d / f"{book_id}.pdf"
        if cand.exists():
            return cand
    for d in BOOK_DIRS:
        hits = list(d.rglob(f"{book_id}.pdf"))
        if hits:
            return hits[0]
    return None


def _find_book_jsonl(book_id: str):
    for d in OCR_DIRS:
        cand = d / book_id / f"{book_id}.pages.jsonl"
        if cand.exists():
            return cand
    for d in OCR_DIRS:
        hits = list(d.rglob(f"{book_id}.pages.jsonl"))
        if hits:
            return hits[0]
    return None


def _find_book_txt(book_id: str):
    cand = TXT_DIR / f"{book_id}.txt"
    if cand.exists():
        return cand
    hits = list(TXT_DIR.glob(f"{book_id}*.txt"))
    return hits[0] if hits else None


def _find_book_md(book_id: str):
    for d in OCR_DIRS:
        cand = d / book_id / f"{book_id}.md"
        if cand.exists():
            return cand
    for d in OCR_DIRS:
        hits = list(d.rglob(f"{book_id}.md"))
        if hits:
            return hits[0]
    return None


class BookAPI:
    """Handlers for /book/* endpoints. Return (status, ctype, body_bytes) or None."""

    @staticmethod
    def handle(path: str, query: dict):
        parts = path.split("/")
        # /book/api/library
        if path == "/book/api/engine":
            return BookAPI.engine_status(query)
        if path == "/book/api/library":
            return BookAPI.library()
        if path.startswith("/book/api/export_annotations"):
            return BookAPI.export_annotations(
                query.get("book", ""), query.get("fmt", "json")
            )
        if path == "/book/api/annotations" and "book" in query:
            return BookAPI.get_annotations(query["book"])
        if path.startswith("/book/api/gsearch"):
            return BookAPI.global_search(query)
        if path.startswith("/book/api/search"):
            return BookAPI.search_book(query)
        if path.startswith("/book/api/txt_paragraphs"):
            return BookAPI.txt_paragraphs(query)
        if path.startswith("/book/api/page_text"):
            return BookAPI.page_text(query)
        if path.startswith("/book/pdf/"):
            return BookAPI.serve_pdf(path[len("/book/pdf/") :], query)
        if path.startswith("/book/txt/"):
            return BookAPI.serve_file(
                _find_book_txt(path[len("/book/txt/") :]), "text/plain; charset=utf-8"
            )
        if path.startswith("/book/md/"):
            return BookAPI.serve_file(
                _find_book_md(path[len("/book/md/") :]), "text/markdown; charset=utf-8"
            )
        if path.startswith("/book/jsonl/"):
            return BookAPI.serve_file(
                _find_book_jsonl(path[len("/book/jsonl/") :]), "application/x-ndjson"
            )
        return None

    @staticmethod
    def library():
        books = []
        seen = set()
        for d in BOOK_DIRS:
            for pdf in sorted(d.rglob("*.pdf")):
                bid = pdf.stem
                if bid in seen:
                    continue
                seen.add(bid)
                jl = _find_book_jsonl(bid)
                npages = 0
                if jl:
                    try:
                        with open(jl, "rb") as fh:
                            npages = sum(1 for _ in fh)
                    except OSError:
                        pass
                books.append(
                    {
                        "book_id": bid,
                        "author": bid.split("_")[0].title().replace("-", " ")
                        if "_" in bid
                        else bid.split(" ")[0],
                        "size_mb": round(pdf.stat().st_size / 1e6, 1),
                        "pages": npages,
                        "has_ocr": bool(jl),
                        "has_txt": bool(_find_book_txt(bid)),
                        "has_md": bool(_find_book_md(bid)),
                    }
                )
        body = _json.dumps({"books": books, "count": len(books)}).encode()
        return 200, "application/json", body

    @staticmethod
    def serve_pdf(book_id: str, query: dict):
        import urllib.parse as _up

        book_id = _up.unquote(book_id)
        pdf = _find_book_pdf(book_id)
        if not pdf:
            return (
                404,
                "application/json",
                _json.dumps({"error": f"no pdf for {book_id}"}).encode(),
            )
        data = pdf.read_bytes()
        return 200, "application/pdf", data

    @staticmethod
    def serve_file(path, ctype):
        if not path or not Path(path).exists():
            return 404, "application/json", b'{"error":"not found"}'
        return 200, ctype, Path(path).read_bytes()

    @staticmethod
    def page_text(query: dict):
        """GET /book/api/page_text?book=ID&page=N -> blocks with text+bbox for overlay."""
        book = query.get("book", "")
        try:
            page = int(query.get("page", "1"))
        except ValueError:
            return 400, "application/json", b'{"error":"bad page"}'
        jl = _find_book_jsonl(book)
        if not jl:
            return 404, "application/json", b'{"error":"no ocr jsonl"}'
        # page param is 1-based page_number; JSONL lines are sequential
        with open(jl, encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if i + 1 == page:
                    d = _json.loads(line)
                    blocks = []
                    for b in d.get("blocks") or []:
                        if not (b.get("text") or "").strip():
                            continue
                        # word-level geometry for precise highlighting
                        words = []
                        for w in (b.get("words") or [])[:80]:
                            words.append(
                                {
                                    "t": w.get("text", ""),
                                    "bbox_pts": w.get("bbox_pts"),
                                }
                            )
                        # paragraphs carry rebased word boxes too
                        for para in (b.get("paragraphs") or [])[:6]:
                            for w in (para.get("words") or [])[:40]:
                                words.append(
                                    {
                                        "t": w.get("text", ""),
                                        "bbox_pts": w.get("bbox_pts"),
                                    }
                                )
                        blocks.append(
                            {
                                "text": b["text"],
                                "bbox_pts": b.get("bbox_pts"),
                                "zone": b.get("zone"),
                                "label": b.get("label"),
                                "words": words,
                            }
                        )
                    out = {
                        "book_id": d.get("book_id", book),
                        "page_number": d.get("page_number", page),
                        "printed_page_number": d.get("printed_page_number"),
                        "page_rect_pts": d.get("page_rect_pts"),
                        "sheet_layout": d.get("sheet_layout"),
                        "blocks": blocks,
                    }
                    return (
                        200,
                        "application/json",
                        _json.dumps(out, ensure_ascii=False).encode(),
                    )
        return 404, "application/json", b'{"error":"page out of range"}'

    @staticmethod
    def search_book(query: dict):
        """GET /book/api/search?book=ID&q=term -> matching pages with snippets."""
        book = query.get("book", "")
        term = (query.get("q") or "").strip()
        if not book or not term:
            return 400, "application/json", b'{"error":"book and q required"}'
        jl = _find_book_jsonl(book)
        if not jl:
            # TXT-only book: search the plain-text file paragraph by paragraph
            tf = _find_book_txt(book)
            if not tf:
                return 404, "application/json", b'{"error":"no ocr jsonl or txt"}'
            import re as _re

            raw = Path(tf).read_text(encoding="utf-8", errors="ignore")
            chunks = [c.strip() for c in _re.split(r"\n\s*\n", raw) if c.strip()]
            variants = {term.lower()}
            if "s" in term.lower():
                variants.add(term.lower().replace("s", "f"))
            if "f" in term.lower():
                variants.add(term.lower().replace("f", "s"))
            results = []
            for i, ch in enumerate(chunks):
                cl = ch.lower()
                if not any(v in cl for v in variants):
                    continue
                pos = cl.find(term.lower())
                snippet = ch[max(0, pos - 120) : pos + 180].replace("\n", " ")
                results.append(
                    {
                        "page": None,
                        "printed_page_number": None,
                        "snippet": snippet,
                        "blocks": [],
                        "count": sum(cl.count(v) for v in variants),
                        "para_idx": i,
                    }
                )
                if len(results) >= 80:
                    break
            return (
                200,
                "application/json",
                _json.dumps(
                    {"book": book, "q": term, "results": results, "n": len(results)},
                    ensure_ascii=False,
                ).encode(),
            )
        # 18th-c spelling variants: long-s f<->s swap + known archaic forms
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
            "value": ["value", "vse"],
            "give": ["giue"],
            "given": ["giuen"],
            "over": ["ouer"],
            "self": ["felf"],
            "love": ["loue"],
            "loved": ["loued"],
            "serve": ["ferue", "serue"],
            "service": ["feruice", "seruice"],
            "saviour": ["savioure", "sauyour"],
        }
        variants = {term.lower()}
        for v in list(variants):
            if "s" in v:
                variants.add(v.replace("s", "f"))
            if "f" in v:
                variants.add(v.replace("f", "s"))
        for v in list(variants):
            if v in ARCH:
                variants.update(ARCH[v])
        results = []
        with open(jl, encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                try:
                    d = _json.loads(line)
                except Exception:
                    continue
                page_text = d.get("text") or ""
                page_l = page_text.lower()
                matched = None
                for v in variants:
                    if v in page_l:
                        matched = v
                        break
                if not matched:
                    continue
                hits = []
                for b in d.get("blocks") or []:
                    bt = b.get("text") or ""
                    bt_l = bt.lower()
                    for v in variants:
                        if v in bt_l:
                            hits.append(
                                {
                                    "text": bt[:300],
                                    "bbox_pts": b.get("bbox_pts"),
                                    "zone": b.get("zone"),
                                    "variant": v if v != term.lower() else None,
                                }
                            )
                            break
                pos = page_l.find(matched)
                snippet = page_text[max(0, pos - 120) : pos + 180].replace("\n", " ")
                results.append(
                    {
                        "page": d.get("page_number", i + 1),
                        "printed_page_number": d.get("printed_page_number"),
                        "snippet": snippet,
                        "blocks": hits[:6],
                        "count": sum(page_l.count(v) for v in variants),
                        "variant": matched if matched != term.lower() else None,
                    }
                )
                if len(results) >= 80:
                    break
        return (
            200,
            "application/json",
            _json.dumps(
                {
                    "book": book,
                    "q": term,
                    "results": results,
                    "n": len(results),
                    "variants_searched": sorted(variants),
                },
                ensure_ascii=False,
            ).encode(),
        )

    @staticmethod
    def export_annotations(book, fmt):
        import re as _re

        safe = _re.sub(r"[^A-Za-z0-9._-]", "_", book)
        out = {}
        for f in ANN_DIR.glob(f"{safe}__p*.json"):
            page = int(f.stem.rsplit("__p", 1)[-1])
            try:
                out[page] = _json.loads(f.read_text())
            except Exception:
                pass
        if fmt == "markdown":
            lines = [f"# Annotations — {book}", ""]
            for page in sorted(out):
                lines.append(f"## Page {page}")
                for a in out[page]:
                    note = a.get("note") or "(no note)"
                    r = a.get("rect", {})
                    lines.append(
                        f"- **{a.get('type', 'highlight')}** ({r.get('x', 0):.0f},{r.get('y', 0):.0f} {r.get('w', 0):.0f}×{r.get('h', 0):.0f}): {note}"
                    )
                lines.append("")
            return 200, "text/markdown; charset=utf-8", "\n".join(lines).encode()
        return (
            200,
            "application/json",
            _json.dumps(
                {"book": book, "pages": out}, ensure_ascii=False, indent=1
            ).encode(),
        )

    _page_index = (
        None  # lazy: [{book_id, page, printed, text_lower, blocks:[{text,bbox}]}]
    )

    @staticmethod
    def _load_page_index():
        if BookAPI._page_index is not None:
            return BookAPI._page_index
        idx = []
        for d in BOOK_DIRS:
            for pdf in sorted(d.rglob("*.pdf")):
                bid = pdf.stem
                jl = _find_book_jsonl(bid)
                if not jl:
                    continue
                with open(jl, encoding="utf-8") as fh:
                    for i, line in enumerate(fh):
                        try:
                            rec = _json.loads(line)
                        except Exception:
                            continue
                        text = rec.get("text") or ""
                        if not text.strip():
                            continue
                        blocks = []
                        for b in rec.get("blocks") or []:
                            bt = b.get("text") or ""
                            if bt.strip():
                                blocks.append(
                                    {"text": bt, "bbox_pts": b.get("bbox_pts")}
                                )
                        idx.append(
                            {
                                "book_id": bid,
                                "page": rec.get("page_number", i + 1),
                                "printed": rec.get("printed_page_number"),
                                "text_lower": text.lower(),
                                "blocks": blocks,
                            }
                        )
        BookAPI._page_index = idx
        return idx

    @staticmethod
    def global_search(query: dict):
        """GET /book/api/gsearch?q=term[&limit=40] -> passage hits across ALL books.

        Searches every book's OCR text (with archaic variants), ranks by
        hit density, returns page + block bbox for direct highlighting.
        """
        import re as _re

        term = (query.get("q") or "").strip()
        limit = min(int(query.get("limit", "40")), 120)
        if not term:
            return 400, "application/json", b'{"error":"q required"}'

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
        variants = {term.lower()}
        for v in list(variants):
            if "s" in v:
                variants.add(v.replace("s", "f"))
            if "f" in v:
                variants.add(v.replace("f", "s"))
        for v in list(variants):
            if v in ARCH:
                variants.update(ARCH[v])
        # multi-word: each CONTENT word must appear on the page. Requiring
        # every token including "to"/"and"/"the" meant a natural research
        # question ("Moral relations to ourselves, to others, and to God")
        # matched nothing at all — the strict AND was over function words.
        STOP = {
            "the", "a", "an", "and", "or", "but", "of", "in", "on", "at", "to",
            "from", "by", "with", "as", "is", "are", "was", "were", "be", "it",
            "its", "this", "that", "these", "those", "for", "not", "no", "than",
            "then", "which", "who", "what", "when", "where", "why", "how",
            "whether", "if", "into", "over", "upon", "their", "his", "her",
            "our", "we", "they", "them", "you", "there", "such", "so",
        }
        all_words = [w for w in _re.split(r"\W+", term.lower()) if w]
        words = [w for w in all_words if len(w) > 2 and w not in STOP] or all_words
        word_variants = []
        for w in words:
            vs = {w}
            if "s" in w:
                vs.add(w.replace("s", "f"))
            if "f" in w:
                vs.add(w.replace("f", "s"))
            if w in ARCH:
                vs.update(ARCH[w])
            word_variants.append(vs)

        idx = BookAPI._load_page_index()

        def collect(require_all: bool):
            hits, per_book = [], {}
            for pg in idx:
                pl = pg["text_lower"]
                if len(words) > 1:
                    n_hit = sum(
                        1 for vs in word_variants if any(v in pl for v in vs)
                    )
                    need = len(words) if require_all else max(2, (len(words) + 1) // 2)
                    if n_hit < need:
                        continue
                else:
                    if not any(v in pl for v in variants):
                        continue
                if per_book.get(pg["book_id"], 0) >= 8:
                    continue
                blocks = []
                for b in pg["blocks"]:
                    btl = b["text"].lower()
                    ok = any(
                        any(v in btl for v in vs) for vs in (word_variants or [variants])
                    )
                    if ok:
                        blocks.append(
                            {"text": b["text"][:280], "bbox_pts": b["bbox_pts"]}
                        )
                if not blocks:
                    continue
                count = (
                    sum(pl.count(v) for vs in word_variants for v in vs)
                    if len(words) > 1
                    else sum(pl.count(v) for v in variants)
                )
                pos = min(
                    (i for i in (pl.find(w) for w in words) if i >= 0), default=-1
                )
                snippet = (
                    pl[max(0, pos - 100) : pos + 220] if pos >= 0 else pl[:220]
                ).replace("\n", " ")
                hits.append(
                    {
                        "book_id": pg["book_id"],
                        "page": pg["page"],
                        "printed_page_number": pg["printed"],
                        "count": count,
                        "snippet": snippet,
                        "blocks": blocks[:5],
                        "pdf_url": f"/book/pdf/{pg['book_id']}",
                    }
                )
                per_book[pg["book_id"]] = per_book.get(pg["book_id"], 0) + 1
                if len(hits) >= limit * 3:
                    break
            return hits

        hits = collect(require_all=True)
        if not hits and len(words) > 1:
            hits = collect(require_all=False)  # relax to a majority of terms
        # rank: hit count desc
        hits.sort(key=lambda h: -h["count"])
        total = len(hits)
        return (
            200,
            "application/json",
            _json.dumps(
                {
                    "q": term,
                    "n": total,
                    "returned": len(hits[:limit]),
                    "results": hits[:limit],
                },
                ensure_ascii=False,
            ).encode(),
        )

    @staticmethod
    def txt_paragraphs(query: dict):
        """GET /book/api/txt_paragraphs?book=ID -> paragraphs with word tokens.

        Each paragraph: {para_idx, text, words: [{w, s, e}]} where s/e are
        char offsets — the TXT equivalent of bbox_pts for annotation.
        """
        import re as _re

        book = query.get("book", "")
        tf = _find_book_txt(book)
        if not tf:
            # fuzzy: txt stem startswith book_id or vice versa
            for cand in TXT_DIR.glob("*.txt"):
                if cand.stem.startswith(book[:20]) or book.startswith(cand.stem[:20]):
                    tf = cand
                    break
        if not tf:
            return 404, "application/json", b'{"error":"no txt for book"}'
        raw = Path(tf).read_text(encoding="utf-8", errors="ignore")
        chunks = [c.strip() for c in _re.split(r"\n\s*\n", raw) if c.strip()]
        paras = []
        for i, ch in enumerate(chunks):
            if len(ch) < 1:
                continue
            words = [
                {"w": m.group(0), "s": m.start(), "e": m.end()}
                for m in _re.finditer(r"\S+", ch[:8000])
            ]
            paras.append(
                {
                    "para_idx": i,
                    "text": ch[:8000],
                    "words": words[:400],
                    "n_words": len(words),
                }
            )
        return (
            200,
            "application/json",
            _json.dumps(
                {
                    "book_id": book,
                    "file": Path(tf).name,
                    "n_paragraphs": len(paras),
                    "paragraphs": paras,
                },
                ensure_ascii=False,
            ).encode(),
        )

    # ---- Jasper backend proxies ----
    # Browsers on other intranet machines resolve 127.0.0.1 to THEMSELVES, so
    # a direct :8790 fetch only works on the host. Everything goes through
    # :8788 instead, which makes search work from any client.
    JASPER = "http://127.0.0.1:8790"

    @staticmethod
    def _jasper(endpoint: str, body: bytes, timeout: int = 30):
        import urllib.request as _urllib

        try:
            req = _urllib.Request(
                f"{BookAPI.JASPER}{endpoint}",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with _urllib.urlopen(req, timeout=timeout) as resp:
                return 200, "application/json", resp.read()
        except Exception as e:
            return (
                502,
                "application/json",
                _json.dumps(
                    {"error": f"{endpoint.lstrip('/')} backend unavailable: {e}"}
                ).encode(),
            )

    @staticmethod
    def device_proxy(query: dict, body: bytes):
        return BookAPI._jasper("/device", body, timeout=90)

    @staticmethod
    def bm25_proxy(query: dict, body: bytes):
        return BookAPI._jasper("/bm25", body, timeout=45)

    @staticmethod
    def query_graph_proxy(query: dict, body: bytes):
        return BookAPI._jasper("/query_graph", body, timeout=90)

    @staticmethod
    def semantic_proxy(query: dict, body: bytes):
        return BookAPI._jasper("/semantic", body, timeout=90)

    @staticmethod
    def concepts_proxy(query: dict, body: bytes):
        """Semantic search over the concept map itself (202 concept vectors)."""
        return BookAPI._jasper("/concepts", body, timeout=90)

    @staticmethod
    def engine_status(query: dict):
        """GET /book/api/engine — Jasper health (device, index size, cache)."""
        import urllib.request as _urllib

        try:
            with _urllib.urlopen(f"{BookAPI.JASPER}/healthz", timeout=5) as resp:
                return 200, "application/json", resp.read()
        except Exception as e:
            return (
                200,
                "application/json",
                _json.dumps({"status": "offline", "error": str(e)}).encode(),
            )

    # ---- annotations (per book+page, JSON files) ----
    @staticmethod
    def _ann_path(book, page):
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", book)
        return ANN_DIR / f"{safe}__p{page}.json"

    @staticmethod
    def get_annotations(book):
        out = {}
        for f in ANN_DIR.glob(f"{re.sub(r'[^A-Za-z0-9._-]', '_', book)}__p*.json"):
            page = f.stem.rsplit("__p", 1)[-1]
            try:
                out[page] = _json.loads(f.read_text())
            except Exception:
                pass
        return (
            200,
            "application/json",
            _json.dumps({"book": book, "annotations": out}).encode(),
        )

    @staticmethod
    def save_annotations(book, page, body: bytes):
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", book)
        try:
            data = _json.loads(body)
        except Exception:
            return 400, "application/json", b'{"error":"bad json"}'
        (ANN_DIR / f"{safe}__p{page}.json").write_text(
            _json.dumps(data, ensure_ascii=False, indent=1)
        )
        return 200, "application/json", b'{"ok":true}'


class Handler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ConceptAtlas/1.0"

    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "application/javascript",
        ".json": "application/json",
        ".woff2": "font/woff2",
        ".css": "text/css",
    }

    def _resolve(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            path = os.path.join(path, "index.html")
        return path

    def _respond(self, include_body=True):
        if self.path.split("?")[0] == "/healthz":
            body = b'{"status":"ok","service":"concept-atlas"}\n'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if include_body:
                self.wfile.write(body)
            return
        path = self._resolve()
        try:
            with open(path, "rb") as f:
                data = f.read()
            mtime = os.fstat(os.open(path, os.O_RDONLY)).st_mtime
        except OSError:
            self.send_error(404, "Not Found")
            return
        ctype = self.guess_type(path)
        accept = self.headers.get("Accept-Encoding", "") or ""
        encoding = None
        if ctype in GZIP_TYPES and len(data) >= GZIP_MIN and "gzip" in accept:
            data = gzip.compress(data, 6)
            encoding = "gzip"
        # conditional request support (Last-Modified revalidation)
        ims = self.headers.get("If-Modified-Since")
        if ims:
            try:
                import email.utils

                since = email.utils.parsedate_to_datetime(ims).timestamp()
                if int(mtime) <= int(since):
                    self.send_response(304)
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    return
            except (TypeError, ValueError):
                pass
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Last-Modified", self.date_time_string(mtime))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Vary", "Accept-Encoding")
        if encoding:
            self.send_header("Content-Encoding", encoding)
        self.end_headers()
        if include_body:
            self.wfile.write(data)

    def _route_book(self, method: str):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
        if method == "GET":
            res = BookAPI.handle(path, query)
        else:  # POST
            if path == "/book/api/annotations":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length else b"{}"
                res = BookAPI.save_annotations(
                    query.get("book", ""), query.get("page", "0"), body
                )
            elif path == "/book/api/device_proxy":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length else b"{}"
                res = BookAPI.device_proxy(query, body)
            elif path == "/book/api/bm25_proxy":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length else b"{}"
                res = BookAPI.bm25_proxy(query, body)
            elif path == "/book/api/query_graph_proxy":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length else b"{}"
                res = BookAPI.query_graph_proxy(query, body)
            elif path == "/book/api/semantic_proxy":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length else b"{}"
                res = BookAPI.semantic_proxy(query, body)
            elif path == "/book/api/concepts_proxy":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length else b"{}"
                res = BookAPI.concepts_proxy(query, body)
            else:
                res = None
        if res is None:
            return False
        status, ctype, body = res
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        if ctype == "application/pdf":
            self.send_header("Content-Disposition", "inline")
        self.end_headers()
        self.wfile.write(body)
        return True

    def do_GET(self):
        if self.path.startswith("/book/"):
            if self._route_book("GET"):
                return
        self._respond(include_body=True)

    def do_POST(self):
        if self.path.startswith("/book/"):
            if self._route_book("POST"):
                return
        self.send_error(404)

    def do_HEAD(self):
        if self.path.startswith("/book/"):
            if self._route_book("HEAD"):
                return
        self._respond(include_body=False)

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), format % args))


def main():
    os.chdir(ROOT)
    # warm the global-search page index at startup (not lazily on first query)
    import threading

    def _warm():
        try:
            BookAPI._load_page_index()
            print("[warm] page index ready")
        except Exception as e:
            print("[warm] failed:", e)

    threading.Thread(target=_warm, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    srv.daemon_threads = True
    print(f"Concept Atlas serving {ROOT}")
    print(f"  -> http://0.0.0.0:{PORT}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
