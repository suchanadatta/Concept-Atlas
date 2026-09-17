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

# Settings come from the repo's single .env (see .env.example); a port given
# on the command line still wins, and so do real environment variables.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))
try:
    from atlas_env import env as _env
except Exception:      # running the UI without the tools tree
    def _env(name, default=None, cast=None):
        import os
        raw = os.environ.get(name)
        if raw in (None, ""):
            return default
        return cast(raw) if cast else raw

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else _env("ATLAS_UI_PORT", 8788, int)
ROOT = os.path.dirname(os.path.abspath(__file__))

# How long a token stream may go quiet before we send a keepalive comment.
# Well under the sixty seconds at which tunnels and load balancers give up.
SSE_HEARTBEAT_SECS = _env("ATLAS_SSE_HEARTBEAT", 15, int)

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


def _attachment(filename: str) -> str:
    """Content-Disposition for a download. Book ids carry spaces, commas and
    apostrophes, none of which survive a bare quoted header, so send an ASCII
    fallback alongside the RFC 5987 UTF-8 form."""
    ascii_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename) or "download"
    quoted = urllib.parse.quote(filename, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quoted}"


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
        if path == "/book/api/authors":
            return BookAPI.authors(query)
        if path == "/book/api/engine":
            return BookAPI.engine_status(query)
        if path == "/book/api/library":
            return BookAPI.library()
        if path == "/book/api/formats":
            return BookAPI.formats(query.get("book", ""))
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
        # The path arrives percent-encoded (urlparse does not decode it) and most
        # book ids contain spaces, so the id has to be unquoted before it can be
        # matched against a filename — serve_pdf does this internally, which is
        # why the PDF download worked while these three 404'd on almost every book.
        if path.startswith("/book/txt/"):
            bid = urllib.parse.unquote(path[len("/book/txt/") :])
            return BookAPI.serve_file(
                _find_book_txt(bid), "text/plain; charset=utf-8",
                filename=f"{bid}.txt",
            )
        if path.startswith("/book/md/"):
            bid = urllib.parse.unquote(path[len("/book/md/") :])
            return BookAPI.serve_file(
                _find_book_md(bid), "text/markdown; charset=utf-8",
                filename=f"{bid}.md",
            )
        if path.startswith("/book/jsonl/"):
            bid = urllib.parse.unquote(path[len("/book/jsonl/") :])
            return BookAPI.serve_file(
                _find_book_jsonl(bid), "application/x-ndjson",
                filename=f"{bid}.pages.jsonl",
            )
        return None

    _library_cache = None          # in-process, so repeat calls are free

    @staticmethod
    def _library_signature():
        """Cheap fingerprint of the corpus: how many PDFs and the newest one.

        Enough to notice a book being added or replaced without stat-ing the
        9.7 GB of OCR output that computing the answer actually costs."""
        n, newest = 0, 0.0
        for d in BOOK_DIRS:
            if not d.exists():
                continue
            for pdf in d.rglob("*.pdf"):
                n += 1
                try:
                    newest = max(newest, pdf.stat().st_mtime)
                except OSError:
                    pass
        return f"{n}:{newest:.0f}"

    @staticmethod
    def library():
        """The shelf, for the Add-to-context picker.

        Building this reads every OCR JSONL to count its pages — 9.7 GB across
        the corpus, 26 seconds — and the picker blocked on it, which is why it
        took so long to open. The answer only changes when a book is added, so
        it is computed once and kept: in memory for the process, and on disk so
        a restart does not pay for it again."""
        sig = BookAPI._library_signature()
        if BookAPI._library_cache and BookAPI._library_cache.get("signature") == sig:
            return 200, "application/json", BookAPI._library_cache["body"]
        cache_file = Path(__file__).resolve().parent / "data" / "library-cache.json"
        try:
            disk = _json.loads(cache_file.read_text(encoding="utf-8"))
            if disk.get("signature") == sig:
                body = _json.dumps({"books": disk["books"], "count": len(disk["books"]),
                                    "cached": True}).encode()
                BookAPI._library_cache = {"signature": sig, "body": body}
                return 200, "application/json", body
        except Exception:
            pass   # no cache, or a stale/corrupt one; build it

        books = BookAPI._build_library()
        body = _json.dumps({"books": books, "count": len(books)}).encode()
        BookAPI._library_cache = {"signature": sig, "body": body}
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(_json.dumps({"signature": sig, "books": books}),
                                  encoding="utf-8")
        except OSError:
            pass   # a read-only deployment still works, just slowly
        return 200, "application/json", body

    @staticmethod
    def _build_library():
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
        return books

    @staticmethod
    def formats(book_id: str):
        """GET /book/api/formats?book=ID -> which downloads exist for this book.

        The reader's overflow menu used to offer all four source formats for
        every book, so you learned that a text-only edition has no scan by
        clicking and getting an error. Four stat() calls is cheap enough to
        answer that up front."""
        if not book_id:
            return 400, "application/json", b'{"error":"book required"}'
        n = 0
        jl = _find_book_jsonl(book_id)
        if jl:
            try:
                with open(jl, "r", encoding="utf-8") as fh:
                    n = sum(1 for _ in fh)
            except OSError:
                n = 0
        return (
            200,
            "application/json",
            _json.dumps(
                {
                    "book_id": book_id,
                    "pdf": bool(_find_book_pdf(book_id)),
                    "txt": bool(_find_book_txt(book_id)),
                    "md": bool(_find_book_md(book_id)),
                    "jsonl": bool(jl),
                    "ocr_pages": n,
                }
            ).encode(),
        )

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
        if query.get("dl"):
            return (
                200,
                "application/pdf",
                data,
                {"Content-Disposition": _attachment(f"{book_id}.pdf")},
            )
        return 200, "application/pdf", data

    @staticmethod
    def serve_file(path, ctype, filename=None):
        """Serve a book file. `filename` turns it into a download rather than
        something the browser renders in place — a text edition navigated to
        with location.href would otherwise replace the whole app with raw text."""
        if not path or not Path(path).exists():
            return 404, "application/json", b'{"error":"not found"}'
        body = Path(path).read_bytes()
        if not filename:
            return 200, ctype, body
        return 200, ctype, body, {"Content-Disposition": _attachment(filename)}

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
            return (
                200,
                "text/markdown; charset=utf-8",
                "\n".join(lines).encode(),
                {"Content-Disposition": _attachment(f"{safe}.annotations.md")},
            )
        return (
            200,
            "application/json",
            _json.dumps(
                {"book": book, "pages": out}, ensure_ascii=False, indent=1
            ).encode(),
            {"Content-Disposition": _attachment(f"{safe}.annotations.json")},
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
    JASPER = _env("ATLAS_JASPER", "http://127.0.0.1:8790")

    @staticmethod
    def _jasper(endpoint: str, body: bytes, timeout: int = 30):
        import urllib.request as _urllib
        import socket as _socket

        try:
            req = _urllib.Request(
                f"{BookAPI.JASPER}{endpoint}",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with _urllib.urlopen(req, timeout=timeout) as resp:
                return 200, "application/json", resp.read()
        except _socket.timeout:
            return (
                504,
                "application/json",
                _json.dumps(
                    {
                        "error": f"the search engine did not answer within {timeout}s",
                        "hint": "it may be loading the index, or running on CPU",
                    }
                ).encode(),
            )
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
        # Asking which device is in use is a field read; only MOVING the model
        # between devices is slow. Sharing one 90s timeout meant a hung engine
        # left the status chip stuck on "checking…" indefinitely.
        try:
            action = _json.loads(body or b"{}").get("action", "get")
        except Exception:
            action = "get"
        return BookAPI._jasper("/device", body, timeout=90 if action == "switch" else 6)

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
    def semantic_graph_proxy(query: dict, body: bytes):
        """Passage network induced from the embeddings, not the concept map."""
        return BookAPI._jasper("/semantic_graph", body, timeout=120)

    @staticmethod
    def compare_proxy(query: dict, body: bytes):
        """Side-by-side of 2-4 concepts or free-text ideas across the corpus."""
        return BookAPI._jasper("/compare", body, timeout=120)

    # ---- chat / accounts / sessions (atlas_chat_server on :8793) ----
    CHAT = _env("ATLAS_CHAT", "http://127.0.0.1:8793")

    # A hung or paused backend used to block a request thread for the full
    # timeout with no feedback, so clicking Ask could hang for two minutes.
    # Only the token stream is genuinely long-running; everything else is a
    # database read and should fail fast enough to show an error instead.
    CHAT_TIMEOUTS = {
        "/healthz": 4,
        "/auth/me": 6,
        "/auth/login": 12,
        "/auth/register": 12,
        "/auth/logout": 6,
        "/auth/update": 12,
        "/auth/forgot": 8,
        "/auth/reset": 12,
        "/sessions": 10,
        "/sessions/import": 45,
    }

    @staticmethod
    def chat_timeout_for(path: str) -> int:
        if path in BookAPI.CHAT_TIMEOUTS:
            return BookAPI.CHAT_TIMEOUTS[path]
        if path.endswith("/export"):
            return 30
        if "/context/add" in path:
            return 90          # resolving a whole book takes real work
        return 15

    @staticmethod
    def chat_proxy(path: str, method: str, body: bytes, token: str, timeout: int = None):
        if timeout is None:
            timeout = BookAPI.chat_timeout_for(path)
        """Forward a chat/account call, carrying the caller's auth token.

        Same reason as the Jasper proxies: 127.0.0.1 resolves to the client's
        own machine, so every intranet browser must go through :8788.
        """
        import urllib.request as _urllib

        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Atlas-Token"] = token
        try:
            req = _urllib.Request(
                f"{BookAPI.CHAT}{path}",
                data=body if method == "POST" else None,
                headers=headers,
                method=method,
            )
            with _urllib.urlopen(req, timeout=timeout) as resp:
                ctype = resp.headers.get("Content-Type", "application/json")
                disp = resp.headers.get("Content-Disposition")
                data = resp.read()
            extra = {"Content-Disposition": disp} if disp else None
            return 200, ctype, data, extra
        except _urllib.HTTPError as e:  # pass the service's own error through
            return e.code, "application/json", e.read() or b"{}", None
        except Exception as e:
            return (
                502,
                "application/json",
                _json.dumps({"error": f"chat backend unavailable: {e}"}).encode(),
                None,
            )

    @staticmethod
    def authors(query: dict):
        """GET /book/api/authors — the author registry joined to the corpus
        (built by tools/build_author_stats.py)."""
        f = Path(__file__).resolve().parent / "data" / "authors.json"
        if not f.exists():
            return 200, "application/json", b'{"authors":[],"groups":[]}'
        return 200, "application/json", f.read_bytes()

    @staticmethod
    def engine_status(query: dict):
        """GET /book/api/engine — Jasper health (device, index size, cache)."""
        import urllib.request as _urllib

        try:
            with _urllib.urlopen(f"{BookAPI.JASPER}/healthz", timeout=4) as resp:
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


# The pages ship asset links like `chat.js?v=1788717937`. That number was typed
# in once and then stopped tracking anything: by the time it was noticed, six of
# the seven scripts had been edited since, chat.js by eight days. A browser
# holding the old file has no way to know, and would keep running last week's
# agent against this week's server.
#
# So the number is stamped here instead, from each file's own mtime, whenever
# the page is served. Every asset gets its own version, and none of them can
# drift again because nobody has to remember to bump anything.
_ASSET_REF = re.compile(rb'(?P<file>[A-Za-z0-9_.\-]+\.(?:js|css|mjs))\?v=[0-9]+')


def _stamp_assets(page_path: str, data: bytes, mtime: float):
    """Rewrite ?v= on every local asset the page links, using its real mtime."""
    root = os.path.dirname(page_path)
    newest = mtime

    def sub(m):
        nonlocal newest
        name = m.group("file").decode("ascii", "replace")
        try:
            st = os.stat(os.path.join(root, name))
        except OSError:
            return m.group(0)          # linked file is gone; leave the link be
        newest = max(newest, st.st_mtime)
        return b"%s?v=%d" % (m.group("file"), int(st.st_mtime))

    stamped = _ASSET_REF.sub(sub, data)
    # The page's own Last-Modified has to move too, or a browser holding the
    # old HTML never asks for it again and never sees the new version numbers.
    return stamped, newest


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
        if ctype == "text/html":
            data, mtime = _stamp_assets(path, data, mtime)
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
        # chat / accounts / sessions live in their own service; these need the
        # caller's token and, for /chat itself, an unbuffered stream
        if path.startswith("/book/api/chat/"):
            sub = "/" + path[len("/book/api/chat/"):]
            token = self.headers.get("X-Atlas-Token", "")
            # Both of these stream SSE for minutes; the buffered proxy below
            # would hold the whole thing and time out long before the end.
            if sub in ("/chat", "/debate") and method == "POST":
                return self._stream_chat(token, sub)
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if (method == "POST" and length) else b"{}"
            status, ctype, data, extra = BookAPI.chat_proxy(sub, method, body, token)  # per-path timeout
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)
            return True
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
            elif path == "/book/api/semantic_graph_proxy":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length else b"{}"
                res = BookAPI.semantic_graph_proxy(query, body)
            elif path == "/book/api/compare_proxy":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length else b"{}"
                res = BookAPI.compare_proxy(query, body)
            else:
                res = None
        if res is None:
            return False
        status, ctype, body = res[0], res[1], res[2]
        extra = res[3] if len(res) > 3 else None
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        if ctype == "application/pdf" and not (extra or {}).get("Content-Disposition"):
            self.send_header("Content-Disposition", "inline")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
        return True

    def _stream_chat(self, token: str, sub: str = "/chat"):
        """Pass an SSE stream through unbuffered.

        The other proxies read the whole response before replying, which for a
        token stream would mean the user watches nothing happen for a minute
        and then sees the finished answer appear at once. A debate is worse:
        several agent turns, so nothing at all until every one has finished.
        """
        import urllib.request as _urllib

        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b"{}"
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Atlas-Token"] = token
        try:
            req = _urllib.Request(
                f"{BookAPI.CHAT}{sub}", data=body, headers=headers, method="POST"
            )
            up = _urllib.urlopen(req, timeout=1800)
        except _urllib.HTTPError as e:
            data = e.read() or b"{}"
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return True
        except Exception as e:
            data = _json.dumps({"error": f"chat backend unavailable: {e}"}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        # A long silence in the middle of a stream is normal: the model can
        # think for the better part of a minute before the first token, and a
        # debate turn can be slower still. Proxies in between read that as a
        # dead connection and hang up — zrok's public frontend does it at
        # around sixty seconds, which kills the answer exactly when the model
        # was about to speak. So the upstream is drained on a thread and this
        # loop emits an SSE comment whenever the wire goes quiet. Comments are
        # part of the protocol and every client skips them; only this loop
        # ever writes to the socket, so there is no interleaving to get wrong.
        import queue as _queue
        import threading as _threading

        relay: _queue.Queue = _queue.Queue()

        def pump():
            try:
                for chunk in up:
                    relay.put(chunk)
            except Exception:
                pass
            finally:
                relay.put(None)

        _threading.Thread(target=pump, daemon=True).start()
        try:
            while True:
                try:
                    chunk = relay.get(timeout=SSE_HEARTBEAT_SECS)
                except _queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue
                if chunk is None:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # the reader navigated away mid-answer
        finally:
            up.close()  # unblocks the pump if nobody is listening any more
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
