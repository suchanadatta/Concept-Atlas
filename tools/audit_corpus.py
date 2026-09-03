#!/usr/bin/env python3
"""Corpus-level completeness audit: every PDF -> every page -> JSONL mapping.

Verifies the deliverable claim end to end:
  1. every PDF under the corpus data dir has a parsed output directory
  2. every parsed JSONL has one line per PDF page (page count match)
  3. every line passes the schema checks (format_version, keys, geometry)
  4. every page has block geometry (bbox_pts) and, after the word pass,
     per-word geometry with char offsets
  5. parse log shows no failures

Usage:
  python tools/audit_corpus.py \
      --data data/BMoral_pdf_collection \
      --output outputs/corpus \
      [--require-words] [--parse-log log/corpus.log] [--strict]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pymupdf

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "GLM-OCR") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "GLM-OCR"))

from glmocr.parser_result.pipeline_result import JSONL_FORMAT_VERSION  # noqa: E402


def _pdf_page_count(path: Path) -> int:
    with pymupdf.open(str(path)) as doc:
        return doc.page_count


def _audit_one(
    pdf: Path,
    data_root: Path,
    out_root: Path,
    require_words: bool,
    parse_log: str,
) -> Tuple[bool, Dict[str, Any]]:
    """Audit one PDF against its parsed output. Returns (ok, details)."""
    rel = pdf.relative_to(data_root)
    stem = pdf.stem
    jsonl_candidates = sorted((out_root / rel.parent).glob(f"{stem}.pages.jsonl"))
    # fallback: search anywhere under out_root for the stem (author dir may differ)
    if not jsonl_candidates:
        jsonl_candidates = sorted(out_root.rglob(f"{stem}.pages.jsonl"))

    det: Dict[str, Any] = {
        "pdf": str(rel),
        "pages": _pdf_page_count(pdf),
        "jsonl": None,
        "jsonl_lines": 0,
        "problems": [],
    }

    if not jsonl_candidates:
        det["problems"].append("MISSING JSONL")
        det["blocks"] = 0
        det["words"] = 0
        return False, det
    jsonl = jsonl_candidates[0]
    det["jsonl"] = str(jsonl.relative_to(out_root))

    lines: List[Dict[str, Any]] = []
    with open(jsonl, "r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if raw:
                try:
                    lines.append(json.loads(raw))
                except json.JSONDecodeError:
                    det["problems"].append("invalid JSON line")
    det["jsonl_lines"] = len(lines)

    if len(lines) != det["pages"]:
        det["problems"].append(
            f"line count {len(lines)} != PDF pages {det['pages']}"
        )

    # per-line schema + geometry
    words_total = 0
    blocks_total = 0
    for i, line in enumerate(lines):
        if line.get("format_version") != JSONL_FORMAT_VERSION:
            det["problems"].append(f"line {i}: format_version != {JSONL_FORMAT_VERSION}")
        if line.get("page_index") != i:
            det["problems"].append(f"line {i}: page_index != {i}")
        rect = line.get("page_rect_pts")
        for b in line.get("blocks") or []:
            blocks_total += 1
            if not b.get("bbox_2d"):
                det["problems"].append(f"line {i}: block missing bbox_2d")
            if rect and not b.get("bbox_pts"):
                det["problems"].append(f"line {i}: block missing bbox_pts")
            for w in b.get("words") or []:
                words_total += 1
                if require_words:
                    s, e = w.get("start", -1), w.get("end", 0)
                    if not (0 <= s < e):
                        det["problems"].append(f"line {i}: word bad offsets")
                    if rect and not w.get("bbox_pts"):
                        det["problems"].append(f"line {i}: word missing bbox_pts")
        if not (line.get("text") or "").strip() and line.get("blocks"):
            # allowed when every block is a figure/image/chart zone, or a
            # chrome zone (header/footer/page_number): engraved plates carry
            # a caption block labeled footer/header while page_text excludes
            # chrome by construction (e.g. GWINNETT frontispiece
            # "6. King of Crocodile and Python").
            PLATE_OK = {"figure", "image", "chart", "header", "footer", "page_number"}
            if not all(
                (b.get("zone") or b.get("label")) in PLATE_OK
                for b in line["blocks"]
            ):
                det["problems"].append(f"line {i}: empty text with text-bearing blocks")
    det["blocks"] = blocks_total
    det["words"] = words_total

    # parse log failures for this book
    if parse_log:
        try:
            log_text = Path(parse_log).read_text(errors="ignore")
            if f"Failed: {pdf.name}" in log_text:
                det["problems"].append("parse log shows 'Failed' for this book")
        except OSError:
            pass

    return not det["problems"], det


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="data/BMoral_pdf_collection")
    ap.add_argument("--output", default="outputs/corpus")
    ap.add_argument("--require-words", action="store_true")
    ap.add_argument("--parse-log", default="log/corpus.log")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    data_root = Path(args.data)
    out_root = Path(args.output)
    pdfs = sorted(data_root.rglob("*.pdf"))
    if not pdfs:
        print(f"no PDFs under {data_root}", file=sys.stderr)
        sys.exit(1)

    ok_count = 0
    total_pages = 0
    total_blocks = 0
    total_words = 0
    problems_all: List[str] = []
    print(f"{'book':58s} {'pages':>5} {'lines':>5} {'blocks':>7} {'words':>8}  status")
    for pdf in pdfs:
        ok, det = _audit_one(pdf, data_root, out_root, args.require_words, args.parse_log)
        total_pages += det["pages"]
        total_blocks += det["blocks"]
        total_words += det["words"]
        if ok:
            ok_count += 1
            status = "OK"
        else:
            status = f"FAIL({len(det['problems'])})"
            problems_all.append(str(det["pdf"]))
            for p in det["problems"]:
                print(f"    ! {det['pdf']}: {p}")
        print(
            f"{str(det['pdf'])[:58]:58s} {det['pages']:>5} {det['jsonl_lines']:>5} "
            f"{det['blocks']:>7} {det['words']:>8}  {status}"
        )

    print(
        f"\n{ok_count}/{len(pdfs)} books OK | {total_pages} pages | "
        f"{total_blocks} blocks | {total_words} words"
    )
    if problems_all:
        print("books with problems:", *problems_all, sep="\n  ")
    sys.exit(0 if (ok_count == len(pdfs) and (not args.strict or not problems_all)) else 1)


if __name__ == "__main__":
    main()
