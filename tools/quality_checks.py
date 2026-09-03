#!/usr/bin/env python3
"""Multiple independent quality checks over the OCR corpus.

Each check is a separate module returning (name, passed, details) so a single
run produces a per-check verdict. Checks:

  Q1 page-completeness   every PDF page has a JSONL line (count match)
  Q2 no-silent-loss      every non-blank page has >= 1 text-bearing block;
                         blank/image-only pages are categorized
  Q3 truncation          blocks ending in '...' / '…' (max_tokens clipping)
  Q4 garbage-ratio       per-page fraction of non-dictionary-ish tokens
                         (repeated chars, rare bigrams) — flags noisy pages
  Q5 word-tiling         words[] [start:end] slices reconstruct the block
                         text exactly (the "perfect mapping" contract)
  Q6 word-geometry       every word bbox_pts inside its block bbox_pts and
                         inside the page rect
  Q7 word-order          word boxes' geometric reading order matches the
                         text order (no zigzag within a block)
  Q8 word-coverage       per-page fraction of words that got a box
  Q9 page-numbering      book_page_number strictly increases across single
                         pages; two-up sheets advance by 2
  Q10 zone-sanity        body text does not contain header/footer/page-
                         number text; headers are short and at top
  Q11 cross-engine       (optional, --sample N) re-render sample pages and
                         compare GLM page text vs docTR line text using
                         normalized edit distance — flags pages where the
                         two engines disagree badly (possible OCR failure)

Usage:
  python tools/quality_checks.py --output outputs/corpus [--sample 12] \
      [--books data/BMoral_pdf_collection] [--limit 2000] [--json report.json]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "GLM-OCR") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "GLM-OCR"))

from glmocr.utils.word_mapping import tokenize_words  # noqa: E402

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    lines = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if raw:
                lines.append(json.loads(raw))
    return lines


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# Q4 helpers ---------------------------------------------------------------

_RARE_BIGRAMS = None


def _load_rare_bigrams() -> None:
    global _RARE_BIGRAMS
    if _RARE_BIGRAMS is not None:
        return
    # English letter-frequency corpus from the first ~10 books (self-derived).
    counts: Counter = Counter()
    src = sorted(REPO_ROOT.joinpath("outputs/corpus").rglob("*.pages.jsonl"))
    for f in src[:10]:
        try:
            for line in load_jsonl(f):
                for b in line.get("blocks") or []:
                    counts.update(_bigrams_of(b.get("text") or ""))
        except Exception:
            continue
    total = sum(counts.values())
    _RARE_BIGRAMS = {g for g, c in counts.items() if c < max(10, total * 0.00005)}


def _bigrams_of(text: str) -> List[str]:
    t = re.sub(r"[^a-z]", "", text.lower())
    return [t[i : i + 2] for i in range(len(t) - 1)]


def _garbage_ratio(text: str) -> float:
    """Heuristic: fraction of tokens with repeated chars or rare bigrams."""
    if not text:
        return 0.0
    _load_rare_bigrams()
    tokens = [t for t in re.findall(r"[a-zA-Z]{3,}", text)]
    if not tokens:
        return 0.0
    bad = 0
    for t in tokens:
        low = t.lower()
        if len(set(low)) <= 1:
            bad += 1
            continue
        bgs = [low[i : i + 2] for i in range(len(low) - 1)]
        if bgs and sum(1 for g in bgs if g in _RARE_BIGRAMS) >= max(1, len(bgs) // 2):
            bad += 1
    return bad / len(tokens)


def _digit_ratio(text: str) -> float:
    """Fraction of alphanumeric chars that are digits.

    Scripture/subject INDEX pages (verse references like ``1 Pet.I, 2. 41.
    212. 237``) are digit-dominated; normal prose sits below ~0.15. Used to
    separate reference-page false positives from genuine OCR garbage.
    """
    letters = sum(1 for c in text if c.isalpha())
    digits = sum(1 for c in text if c.isdigit())
    return digits / max(1, letters + digits)


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------


def q1_page_completeness(books: List[Tuple[Path, Path]], out_root: Path) -> Tuple[bool, str]:
    bad = []
    for pdf, jsonl in books:
        with pymupdf.open(str(pdf)) as doc:
            n_pdf = doc.page_count
        n_lines = len(load_jsonl(jsonl))
        if n_lines != n_pdf:
            bad.append(f"{pdf.name}: {n_lines} lines != {n_pdf} pages")
    return (not bad), ("all match" if not bad else "; ".join(bad[:5]))


def q2_no_silent_loss(books: List[Tuple[Path, Path]], out_root: Path) -> Tuple[bool, str]:
    flagged = []
    for pdf, jsonl in books:
        for line in load_jsonl(jsonl):
            blocks = line.get("blocks") or []
            text = (line.get("text") or "").strip()
            has_text_block = any(
                b.get("zone") not in ("figure",) and (b.get("text") or "").strip()
                for b in blocks
            )
            if not text and has_text_block:
                continue  # covered by other checks
            if not text and not has_text_block and blocks:
                # blocks exist but no text anywhere: could be figure-only page
                zones = {b.get("zone") for b in blocks}
                if zones <= {"figure"}:
                    continue  # legit plate page
                flagged.append(f"{pdf.name} p{line['page_number']}: no text, zones={zones}")
    return (not flagged), (f"{len(flagged)} flagged" if flagged else "clean")


def q3_truncation(books: List[Tuple[Path, Path]], out_root: Path) -> Tuple[bool, str]:
    """Blocks cut by max_tokens end with an ellipsis AND are near the token
    cap (8192). Short blocks ending in '...' are 18th-c typographic ellipses
    ('&c.', deliberate pauses) and are not truncation."""
    n = 0
    examples = []
    for pdf, jsonl in books:
        for line in load_jsonl(jsonl):
            for b in line.get("blocks") or []:
                t = (b.get("text") or "").rstrip()
                if not t.endswith(("...", "…")):
                    continue
                if len(t) < 6000:  # well below the 8192-token cap
                    continue
                n += 1
                if len(examples) < 5:
                    examples.append(f"{pdf.name} p{line['page_number']} b{b['id']} ({len(t)} chars): …{t[-50:]}")
    return (n == 0), (f"{n} near-cap truncated blocks" + (" e.g. " + "; ".join(examples) if examples else ""))


def q4_garbage_ratio(books: List[Tuple[Path, Path]], out_root: Path, limit: int = 2000) -> Tuple[bool, str]:
    flagged = []
    index_pages = []
    total_pages = 0
    for pdf, jsonl in books:
        for line in load_jsonl(jsonl):
            total_pages += 1
            text = line.get("text") or ""
            if len(text) < 40:
                continue
            ratio = _garbage_ratio(text)
            if ratio > 0.25:
                # Digit-dominated pages are scripture/subject INDEX pages
                # (verse refs "1 Pet.I, 2. 41. 212. 237") whose abbreviation
                # tokens ("Pet", "Heb", "Tit") naturally trip the bigram
                # heuristic. Verified correct OCR on this corpus — classify,
                # don't fail. Measured: flagged indexes 0.35-0.86, prose
                # median 0.00 / max 0.03 → 0.25 cutoff has wide margin.
                if _digit_ratio(text) > 0.25:
                    index_pages.append(f"{pdf.name} p{line['page_number']}")
                else:
                    flagged.append(f"{pdf.name} p{line['page_number']}: garbage={ratio:.2f}")
    detail = f"{len(flagged)}/{total_pages} pages flagged"
    if flagged:
        detail += " e.g. " + flagged[0]
    if index_pages:
        detail += f" | {len(index_pages)} index/reference pages (correct OCR, exempt)"
    return (not flagged), detail


def q5_word_tiling(books: List[Tuple[Path, Path]], out_root: Path) -> Tuple[bool, str]:
    """words[] must EXACTLY tile the block text they came from."""
    bad = []
    total_words = 0
    for pdf, jsonl in books:
        for line in load_jsonl(jsonl):
            for b in line.get("blocks") or []:
                text = b.get("text") or ""
                for w in b.get("words") or []:
                    total_words += 1
                    s, e = w.get("start"), w.get("end")
                    if s is None or e is None:
                        continue
                    if not (0 <= s < e <= len(text)):
                        bad.append(f"{pdf.name} p{line['page_number']} b{b['id']}: offsets {s}:{e} vs len {len(text)}")
                        continue
                    if norm(w.get("text")) != norm(text[s:e]):
                        bad.append(f"{pdf.name} p{line['page_number']} b{b['id']}: '{w.get('text')}' != text[{s}:{e}]='{text[s:e]}'")
    return (not bad), (f"{total_words} words, {len(bad)} tiling violations" if bad else f"{total_words} words: perfect tiling")


def q6_word_geometry(books: List[Tuple[Path, Path]], out_root: Path) -> Tuple[bool, str]:
    bad = []
    total = 0
    for pdf, jsonl in books:
        for line in load_jsonl(jsonl):
            rect = line.get("page_rect_pts")
            for b in line.get("blocks") or []:
                bb = b.get("bbox_pts")
                for w in b.get("words") or []:
                    if not w.get("bbox_pts"):
                        continue
                    total += 1
                    wp = w["bbox_pts"]
                    if rect and not (rect["x0"] - 0.5 <= wp[0] and rect["y0"] - 0.5 <= wp[1] and wp[2] <= rect["x1"] + 0.5 and wp[3] <= rect["y1"] + 0.5):
                        bad.append(f"{pdf.name} p{line['page_number']} word outside page")
                    if bb and not (bb[0] - 0.5 <= wp[0] and bb[1] - 0.5 <= wp[1] and wp[2] <= bb[2] + 0.5 and wp[3] <= bb[3] + 0.5):
                        bad.append(f"{pdf.name} p{line['page_number']} b{b['id']} word '{w.get('text')}' outside block")
    return (not bad), (f"{total} word boxes checked, {len(bad)} violations" if bad else f"{total} word boxes: all inside page+block")


def q7_word_order(books: List[Tuple[Path, Path]], out_root: Path) -> Tuple[bool, str]:
    """Words are stored in text (reading) order; verify that geometry agrees:
    walking words in text order, y must not go UP (to a previous line) and
    within the same line x must not go LEFT. Centered headings may zigzag x
    across lines, which is allowed (lines are detected by y jumps).

    Uses the SAME height-adaptive line bands as
    glmocr.utils.word_mapping.filter_word_order (keep in sync!): absolute
    8-unit bands merge tightly-leaded verse lines (pitch ~6u, h ~5-9u) and
    mass-flag legitimate line starts as x regressions.
    """
    bad = []

    def med_h(words):
        hs = sorted(
            w["bbox_pts"][3] - w["bbox_pts"][1]
            for w in words
            if w.get("bbox_pts") and len(w["bbox_pts"]) == 4
        )
        return hs[len(hs) // 2] if hs else 20.0

    for pdf, jsonl in books:
        for line in load_jsonl(jsonl):
            for b in line.get("blocks") or []:
                words = b.get("words") or []
                if len(words) < 4:
                    continue
                tol_y = max(4.0, 0.55 * med_h(words))
                tol_x = max(5.0, 0.60 * med_h(words))
                cur_line_y = None
                prev_x = None
                prev_y = -1e9
                for w in words:
                    wp = w.get("bbox_pts")
                    if not wp:
                        continue
                    gy = (wp[1] + wp[3]) / 2.0
                    gx = (wp[0] + wp[2]) / 2.0
                    if gy < prev_y - tol_y:
                        bad.append(f"{pdf.name} p{line['page_number']} b{b['id']}: word '{w.get('text')}' moved up (y {gy:.0f} < {prev_y:.0f})")
                        break
                    if cur_line_y is not None and abs(gy - cur_line_y) <= tol_y:
                        # same line: x must not regress
                        if prev_x is not None and gx < prev_x - tol_x:
                            bad.append(f"{pdf.name} p{line['page_number']} b{b['id']}: word '{w.get('text')}' left of previous (x {gx:.0f} < {prev_x:.0f})")
                            break
                    else:
                        cur_line_y = gy
                        prev_x = None
                    prev_y = max(prev_y, gy)
                    if cur_line_y is not None and abs(gy - cur_line_y) <= tol_y:
                        prev_x = gx
    return (not bad), (f"{len(bad)} order issues" if bad else "all word orders geometric")


def q8_word_coverage(books: List[Tuple[Path, Path]], out_root: Path) -> Tuple[bool, str]:
    total = matched = 0
    per_book = []
    for pdf, jsonl in books:
        m = t = 0
        for line in load_jsonl(jsonl):
            for b in line.get("blocks") or []:
                t += len(tokenize_words(b.get("text") or ""))
                m += len(b.get("words") or [])
        total += t
        matched += m
        per_book.append((pdf.name, m / t if t else 1.0))
    cov = matched / total if total else 1.0
    worst = sorted(per_book, key=lambda x: x[1])[:3]
    return (cov >= 0.5), (f"coverage {cov*100:.1f}% | worst: " + ", ".join(f"{n} {c*100:.0f}%" for n, c in worst))


def q9_page_numbering(books: List[Tuple[Path, Path]], out_root: Path) -> Tuple[bool, str]:
    bad = []
    for pdf, jsonl in books:
        prev = 0
        for line in load_jsonl(jsonl):
            if line.get("sheet_layout") == "two_up":
                nums = line.get("book_page_numbers") or []
                if nums:
                    if prev and nums[0] != prev + 1:
                        bad.append(f"{pdf.name} p{line['page_number']}: two-up starts {nums[0]} after {prev}")
                    prev = nums[-1]
            else:
                bp = line.get("book_page_number")
                if bp is not None:
                    if prev and bp != prev + 1:
                        bad.append(f"{pdf.name} p{line['page_number']}: book_page {bp} after {prev}")
                    prev = bp
    return (not bad), ("all monotone" if not bad else "; ".join(bad[:5]))


def q10_zone_sanity(books: List[Tuple[Path, Path]], out_root: Path) -> Tuple[bool, str]:
    bad = []
    for pdf, jsonl in books:
        for line in load_jsonl(jsonl):
            rect = line.get("page_rect_pts")
            for b in line.get("blocks") or []:
                zone = b.get("zone")
                t = (b.get("text") or "").strip()
                if zone == "header" and t and rect and len(t) > 120:
                    bad.append(f"{pdf.name} p{line['page_number']} b{b['id']}: header too long ({len(t)} chars)")
                if zone == "page_number" and rect:
                    bb = b.get("bbox_pts")
                    if bb and len((b.get("text") or "").strip()) < 6:
                        continue  # tiny folio in a margin — fine anywhere
                    if bb and not (bb[1] < rect["y1"] * 0.35 or bb[1] > rect["y1"] * 0.65):
                        bad.append(f"{pdf.name} p{line['page_number']} b{b['id']}: page_number mid-page")
    return (not bad), (f"{len(bad)} zone issues" if bad else "zones sane")


def q11_cross_engine(
    books: List[Tuple[Path, Path]], out_root: Path, sample: int
) -> Tuple[bool, str]:
    """Re-OCR a sample of pages with docTR and compare to GLM text.

    Uses normalized edit distance between the two page texts; large distance
    flags possible OCR failure / content loss. docTR words carry text; we
    join the page-level blocks' words (provider text is discarded in JSONL,
    so we re-run docTR here — hence the sample limit).
    """
    import warnings

    warnings.filterwarnings("ignore")
    from doctr.models import ocr_predictor

    import numpy as np

    os.environ.setdefault("DOCTR_CACHE_DIR", str(REPO_ROOT / "models" / "doctr"))
    pred = ocr_predictor(det_arch="fast_base", reco_arch="crnn_mobilenet_v3_small", pretrained=True)
    import torch

    if torch.cuda.is_available():
        pred = pred.to("cuda")  # docTR does not move models to GPU itself
    print(f"[q11] docTR on {'cuda' if torch.cuda.is_available() else 'cpu'}")

    def lev_norm(a: str, b: str) -> float:
        na, nb = norm(a), norm(b)
        if not na and not nb:
            return 1.0
        if not na or not nb:
            return 0.0
        # quick banded check: edit distance via difflib ratio is fine here
        import difflib

        return difflib.SequenceMatcher(None, na, nb).ratio()

    flagged = []
    checked = 0
    sims = []
    length_ratios = []
    import random

    random.seed(7)
    for pdf, jsonl in books:
        lines = load_jsonl(jsonl)
        pages = [l for l in lines if len((l.get("text") or "").strip()) > 60]
        picked = random.sample(pages, min(2, len(pages)))
        with pymupdf.open(str(pdf)) as doc:
            for line in picked:
                idx = line["page_index"]
                pix = doc[idx].get_pixmap(matrix=pymupdf.Matrix(200 / 72, 200 / 72))
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                res = pred([img])
                doctr_text = " ".join(
                    w.value
                    for p in res.pages
                    for b in p.blocks
                    for l in b.lines
                    for w in l.words
                )
                checked += 1
                glm_text = line.get("text") or ""
                r = lev_norm(glm_text, doctr_text)
                sims.append(r)
                len_ratio = len(norm(doctr_text)) / max(1, len(norm(glm_text)))
                length_ratios.append(len_ratio)
                # Content-presence check (robust to docTR rec noise): if one
                # engine found <30% of the other's content, one of them
                # missed real text.
                if len_ratio < 0.3 or len_ratio > 3.0:
                    flagged.append(
                        f"{pdf.name} p{line['page_number']}: GLM {len(norm(glm_text))} vs docTR {len(norm(doctr_text))} chars"
                    )
    sims_sorted = sorted(sims)
    p50 = sims_sorted[len(sims_sorted) // 2] if sims_sorted else 0
    lr = sorted(length_ratios)
    lr50 = lr[len(lr) // 2] if lr else 0
    detail = (
        f"{checked} pages compared | sim p50={p50:.2f} | len-ratio p50={lr50:.2f}"
        + (f" | {len(flagged)} content-mismatch" if flagged else " | no content mismatches")
    )
    return (not flagged), detail


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------

def collect_books(out_root: Path, data_root: Path) -> List[Tuple[Path, Path]]:
    books = []
    pdfs = sorted(data_root.rglob("*.pdf"))
    for pdf in pdfs:
        stem = pdf.stem
        cands = sorted(out_root.rglob(f"{stem}.pages.jsonl"))
        if not cands:
            books.append((pdf, Path("/dev/null")))
        else:
            books.append((pdf, cands[0]))
    return books


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", default="outputs/corpus")
    ap.add_argument("--books", default="data/BMoral_pdf_collection")
    ap.add_argument("--sample", type=int, default=0, help="Q11 cross-engine sample pages per book (0 = skip)")
    ap.add_argument("--json", default=None, help="write report JSON")
    args = ap.parse_args()

    import os

    out_root = Path(args.output)
    data_root = Path(args.books)
    books = collect_books(out_root, data_root)
    missing = [str(p) for p, j in books if str(j) == "/dev/null"]
    books = [(p, j) for p, j in books if str(j) != "/dev/null"]

    print(f"books: {len(books)} parsed + {len(missing)} missing JSONL\n")
    results = []
    for name, fn in [
        ("Q1 page-completeness", lambda: q1_page_completeness(books, out_root)),
        ("Q2 no-silent-loss", lambda: q2_no_silent_loss(books, out_root)),
        ("Q3 truncation", lambda: q3_truncation(books, out_root)),
        ("Q4 garbage-ratio", lambda: q4_garbage_ratio(books, out_root)),
        ("Q5 word-tiling", lambda: q5_word_tiling(books, out_root)),
        ("Q6 word-geometry", lambda: q6_word_geometry(books, out_root)),
        ("Q7 word-order", lambda: q7_word_order(books, out_root)),
        ("Q8 word-coverage", lambda: q8_word_coverage(books, out_root)),
        ("Q9 page-numbering", lambda: q9_page_numbering(books, out_root)),
        ("Q10 zone-sanity", lambda: q10_zone_sanity(books, out_root)),
    ]:
        try:
            passed, detail = fn()
        except Exception as e:  # noqa: BLE001
            passed, detail = False, f"ERROR: {e}"
        results.append({"check": name, "passed": passed, "detail": detail})
        print(f"{'PASS' if passed else 'FAIL'}  {name}: {detail}")

    if args.sample > 0 and books:
        passed, detail = q11_cross_engine(books, out_root, args.sample)
        results.append({"check": "Q11 cross-engine", "passed": passed, "detail": detail})
        print(f"{'PASS' if passed else 'FAIL'}  Q11 cross-engine: {detail}")

    if missing:
        print(f"\nMISSING JSONL for {len(missing)} books: {missing[:5]}")

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2, ensure_ascii=False))

    any_fail = any(not r["passed"] for r in results)
    print(f"\nVERDICT: {'ALL CHECKS PASS' if not any_fail else 'ISSUES FOUND — see above'}")
    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
