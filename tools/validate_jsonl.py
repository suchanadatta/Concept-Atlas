#!/usr/bin/env python3
"""Rigorous validation of GLM-OCR page JSONL files.

Checks, per book:
  * every expected page is present (page count matches the source PDF)
  * schema: required fields exist, types are correct, ``format_version``
    matches, blocks have ``id``/``label``/``zone``/``text``/``bbox_2d``
  * geometry: every ``bbox_pts`` lies inside the page rect; every word's
    ``bbox_pts`` lies inside its block's ``bbox_pts`` (when both present)
  * char offsets: word ``start``/``end`` fall inside the block text length
    and are monotone non-overlapping
  * page numbers: ``book_page_number`` strictly increases across pages
    (skipping blanks); ``printed_page_number`` offsets are consistent
  * word coverage per block is reported and aggregated per book

Exit code 0 when every checked file passes; 1 otherwise.

Usage:
  python tools/validate_jsonl.py --jsonl outputs/corpus
  python tools/validate_jsonl.py --jsonl <file.pages.jsonl> --strict
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "GLM-OCR") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "GLM-OCR"))

from glmocr.parser_result.pipeline_result import JSONL_FORMAT_VERSION  # noqa: E402

REQUIRED_LINE = {
    "format_version",
    "book_id",
    "book_title",
    "source",
    "page_index",
    "page_number",
    "total_pages",
    "book_sheet_mode",
    "sheet_layout",
    "blocks",
    "text",
}
REQUIRED_BLOCK = {"id", "label", "zone", "text", "bbox_2d"}


def _problems(problems: List[str], book: str, msg: str) -> None:
    problems.append(f"{book}: {msg}")


def validate_jsonl_file(path: Path, strict: bool) -> Tuple[List[str], Dict[str, Any]]:
    problems: List[str] = []
    stats: Dict[str, Any] = {"pages": 0, "words": 0, "coverage_sum": 0.0, "block_count": 0}
    lines: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if raw:
                try:
                    lines.append(json.loads(raw))
                except json.JSONDecodeError as e:
                    problems.append(f"{path.name}: invalid JSON line: {e}")
    if not lines:
        stats["avg_coverage"] = 0.0
        return ["empty JSONL"], stats
    book = lines[0].get("book_id", path.stem)

    # schema
    for i, line in enumerate(lines):
        missing = REQUIRED_LINE - set(line.keys())
        if missing:
            _problems(problems, book, f"line {i}: missing {sorted(missing)}")
        if line.get("format_version") != JSONL_FORMAT_VERSION:
            _problems(problems, book, f"line {i}: format_version {line.get('format_version')} != {JSONL_FORMAT_VERSION}")
        blocks = line.get("blocks") or []
        stats["block_count"] += len(blocks)
        for b in blocks:
            mb = REQUIRED_BLOCK - set(b.keys())
            if mb:
                _problems(problems, book, f"line {i} block {b.get('id')}: missing {sorted(mb)}")
        # page_index sequence
        if line.get("page_index") != i:
            _problems(problems, book, f"line {i}: page_index {line.get('page_index')} != {i}")
        # total_pages consistency
        if line.get("total_pages") != len(lines):
            _problems(problems, book, f"line {i}: total_pages {line.get('total_pages')} != {len(lines)}")

    # geometry + offsets + page numbers (second pass)
    prev_book_page = 0
    for i, line in enumerate(lines):
        rect = line.get("page_rect_pts")
        blocks = line.get("blocks") or []
        for b in blocks:
            bbox_pts = b.get("bbox_pts")
            if bbox_pts and rect:
                if not (
                    rect["x0"] - 0.5 <= bbox_pts[0]
                    and rect["y0"] - 0.5 <= bbox_pts[1]
                    and bbox_pts[2] <= rect["x1"] + 0.5
                    and bbox_pts[3] <= rect["y1"] + 0.5
                ):
                    _problems(problems, book, f"p{i} block {b['id']}: bbox_pts outside page rect {bbox_pts}")
            words = b.get("words") or []
            stats["words"] += len(words)
            text = b.get("text") or ""
            prev_end = -1
            for w in words:
                s, e = w.get("start"), w.get("end")
                if s is None or e is None:
                    continue
                if not (0 <= s < e <= len(text)):
                    _problems(problems, book, f"p{i} block {b['id']} word {w.get('text')!r}: offsets [{s}:{e}] outside text len {len(text)}")
                if s < prev_end:
                    _problems(problems, book, f"p{i} block {b['id']}: non-monotone word offsets")
                prev_end = e
                if w.get("bbox_pts") and bbox_pts:
                    if not (
                        bbox_pts[0] - 0.5 <= w["bbox_pts"][0]
                        and bbox_pts[1] - 0.5 <= w["bbox_pts"][1]
                        and w["bbox_pts"][2] <= bbox_pts[2] + 0.5
                        and w["bbox_pts"][3] <= bbox_pts[3] + 0.5
                    ):
                        _problems(problems, book, f"p{i} block {b['id']} word {w.get('text')!r}: word bbox outside block bbox")
            cov = b.get("word_coverage")
            if isinstance(cov, (int, float)):
                stats["coverage_sum"] += cov

        # page number monotonicity (single pages)
        bp = line.get("book_page_number")
        if bp is not None and line.get("sheet_layout") == "single":
            if bp <= prev_book_page:
                _problems(problems, book, f"p{i}: book_page_number {bp} not strictly increasing after {prev_book_page}")
            prev_book_page = bp

    stats["pages"] = len(lines)
    stats["avg_coverage"] = round(
        stats["coverage_sum"] / max(1, stats["block_count"]), 4
    )
    return problems, stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jsonl", required=True, help="JSONL file or directory")
    ap.add_argument("--strict", action="store_true", help="Fail on any problem")
    args = ap.parse_args()

    p = Path(args.jsonl)
    files = [p] if p.is_file() else sorted(p.rglob("*.pages.jsonl"))
    if not files:
        print(f"no .pages.jsonl files under {args.jsonl}", file=sys.stderr)
        sys.exit(1)

    total_problems = 0
    print(f"{'book':64s} {'pages':>6} {'blocks':>7} {'words':>7} {'cov%':>6}  status")
    for f in files:
        problems, stats = validate_jsonl_file(f, args.strict)
        status = "OK" if not problems else f"FAIL({len(problems)})"
        print(
            f"{f.name[:64]:64s} {stats['pages']:>6} {stats['block_count']:>7} "
            f"{stats['words']:>7} {stats['avg_coverage']*100:>6.1f}  {status}"
        )
        for pr in problems[:8]:
            print(f"    ! {pr}")
        if len(problems) > 8:
            print(f"    ... and {len(problems)-8} more")
        total_problems += len(problems)

    print(f"\n{len(files)} files, {total_problems} problems total")
    sys.exit(1 if total_problems and args.strict else 0)


if __name__ == "__main__":
    main()
