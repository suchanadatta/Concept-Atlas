#!/usr/bin/env python3
"""Attach word-level geometry to GLM-OCR page JSONL outputs.

The corpus parse (``glmocr parse``) produces ``<book>.pages.jsonl`` with
block-level bounding boxes. This pass adds per-word geometry so later
software can highlight an exact word/phrase on the PDF:

  for each book JSONL:
    for each page line:
      render the PDF page (300 dpi, matching the OCR dpi)
      run docTR (detection + recognition) -> word boxes with rough text
      assign boxes to GLM-OCR blocks by centroid containment
      align the block's GLM-OCR text to the provider words (fuzzy,
        monotone; GLM-OCR text is authoritative, provider text is only
        used to pair boxes with words)
      write ``words[]`` (text, char offsets, bbox_2d normalized 0-1000,
      bbox_pts in PDF points) back into each block

The pass is additive: every existing field is preserved; only
``words``/``word_coverage`` are added per block.

Usage:
  python tools/word_map.py --jsonl outputs/corpus
  python tools/word_map.py --jsonl outputs/corpus/Hutcheson, Francis*/Hutcheson*/*.pages.jsonl
  python tools/word_map.py --jsonl <file.pages.jsonl> --dpi 300
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pymupdf
from PIL import Image

# Make the local (editable-installed) SDK importable even when run from the
# repo checkout that does not have the package installed.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "GLM-OCR") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "GLM-OCR"))

from glmocr.parser_result.pipeline_result import _normalized_to_pts  # noqa: E402
from glmocr.utils.word_mapping import (  # noqa: E402
    align_words,
    assign_boxes_to_blocks,
    enrich_blocks,
    sort_words_reading_order,
    tokenize_words,
)

logger = logging.getLogger("word_map")

DET_ARCH = "fast_base"
RECO_ARCH = "crnn_mobilenet_v3_small"
CACHE_DIR = str(REPO_ROOT / "models" / "doctr")


def _relative_to_norm(rel: tuple, width: int, height: int) -> List[int]:
    """docTR relative (0-1) geometry -> normalized 0-1000 bbox [x1,y1,x2,y2]."""
    (xmin, ymin), (xmax, ymax) = rel
    return [
        int(round(xmin * 1000.0)),
        int(round(ymin * 1000.0)),
        int(round(xmax * 1000.0)),
        int(round(ymax * 1000.0)),
    ]


def extract_page_words(page_res, width_px: int, height_px: int) -> List[Dict[str, Any]]:
    """Extract word dicts from a single docTR page result (no re-inference).

    Each dict: ``{text, box_2d (normalized 0-1000), sort_x, sort_y}``.
    """
    words: List[Dict[str, Any]] = []
    for block in page_res.blocks:
        for line in block.lines:
            for word in line.words:
                box_2d = _relative_to_norm(word.geometry, width_px, height_px)
                words.append(
                    {
                        "text": word.value or "",
                        "box_2d": box_2d,
                        "sort_x": (box_2d[0] + box_2d[2]) / 2.0,
                        "sort_y": (box_2d[1] + box_2d[3]) / 2.0,
                    }
                )
    return sort_words_reading_order(words)


def collect_document_words(
    predictor, img: np.ndarray, width_px: int, height_px: int
) -> List[Dict[str, Any]]:
    """Run docTR on one page image and return flat word dicts.

    Each dict: ``{text, box_2d (normalized 0-1000), sort_x, sort_y}``.
    """
    out = predictor([img])
    return extract_page_words(out.pages[0], width_px, height_px)


def build_provider_map(
    page_words: List[Dict[str, Any]], blocks: List[Dict[str, Any]]
) -> Dict[int, List[Dict[str, Any]]]:
    """Assign detected words to blocks by centroid containment."""
    owned = assign_boxes_to_blocks(blocks, page_words, x_margin=25.0, y_margin=10.0)
    return owned


def enrich_jsonl_file(
    jsonl_path: Path, predictor, dpi: int, batch_size: int
) -> Dict[str, Any]:
    """Enrich one JSONL file in place. Returns stats."""
    lines: List[Dict[str, Any]] = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if raw:
                lines.append(json.loads(raw))

    if not lines:
        return {"pages": 0, "words": 0, "coverage": 0.0}

    source = lines[0].get("source")
    if not source or not source.lower().endswith(".pdf"):
        logger.warning("%s: source is not a PDF; skipping", jsonl_path.name)
        return {"pages": 0, "words": 0, "coverage": 0.0}

    doc = pymupdf.open(source)
    total_words = 0
    total_glm = 0
    total_matched = 0

    # batch pages for docTR (fewer python-side round trips)
    for start in range(0, len(lines), batch_size):
        chunk = lines[start : start + batch_size]
        imgs = []
        metas = []
        for line in chunk:
            page = doc[line["page_index"]]
            mat = pymupdf.Matrix(dpi / 72.0, dpi / 72.0)
            pix = page.get_pixmap(matrix=mat)  # RGB (docTR needs 3 channels)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n
            )
            imgs.append(img)
            metas.append((line, pix.width, pix.height))

        results = predictor(imgs)

        for line, page_res, (width_px, height_px) in zip(
            chunk, results.pages, [(m[1], m[2]) for m in metas]
        ):
            page_words = extract_page_words(page_res, width_px, height_px)
            provider_map = build_provider_map(page_words, line.get("blocks") or [])
            enriched = enrich_blocks(
                line.get("blocks") or [],
                provider_map,
                line.get("page_rect_pts"),
            )
            line["blocks"] = enriched["blocks"]
            stats = enriched["stats"]
            total_words += stats["glm_words"]
            total_matched += stats["matched"]
            total_glm += stats["glm_words"]

    doc.close()

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")

    coverage = total_matched / total_glm if total_glm else 0.0
    return {
        "pages": len(lines),
        "words": total_words,
        "coverage": round(coverage, 4),
    }


def discover_jsonl_files(path: str) -> List[Path]:
    p = Path(path)
    if p.is_file():
        return [p]
    if p.is_dir():
        return sorted(p.rglob("*.pages.jsonl"))
    return []


def is_enriched(path: Path) -> bool:
    """True when the JSONL already contains per-block word geometry.

    Scans ALL lines (title pages / plates often carry no words on the first
    line, so a first-line-only check wrongly reports books as unenriched).
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                line = json.loads(raw)
                if any(b.get("words") for b in line.get("blocks") or []):
                    return True
    except Exception:
        return False
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jsonl", required=True, help="JSONL file or directory")
    ap.add_argument("--dpi", type=int, default=300, help="Render dpi (default 300)")
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--resume", action="store_true", help="skip books that already have word geometry")
    ap.add_argument("--force", action="store_true", help="re-enrich even books that already have word geometry")
    ap.add_argument("--older-than", default=None, metavar="TS",
                    help="only process files with mtime older than TS (e.g. '2026-08-25 16:30:00'); "
                         "enables crash-resumable full passes: completed files get fresh mtimes "
                         "and are skipped on relaunch with the same TS")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    os.environ.setdefault("DOCTR_CACHE_DIR", CACHE_DIR)

    files = discover_jsonl_files(args.jsonl)
    if not files:
        logger.error("No .pages.jsonl files found under %s", args.jsonl)
        sys.exit(1)
    if args.older_than:
        from datetime import datetime as _dt
        ts = _dt.strptime(args.older_than, "%Y-%m-%d %H:%M:%S").timestamp()
        pending = [f for f in files if f.stat().st_mtime < ts]
        logger.info("older-than %s: %d/%d files pending",
                    args.older_than, len(pending), len(files))
        files = pending
        if not files:
            logger.info("nothing to do")
            sys.exit(0)
    if args.resume:
        pending = [f for f in files if not is_enriched(f)]
        logger.info("resume: %d files total, %d already enriched, %d pending",
                    len(files), len(files) - len(pending), len(pending))
        files = pending
        if not files:
            logger.info("nothing to do")
            sys.exit(0)

    from doctr.models import ocr_predictor

    logger.info("Loading docTR (%s / %s) ...", DET_ARCH, RECO_ARCH)
    t0 = time.time()
    predictor = ocr_predictor(
        det_arch=DET_ARCH,
        reco_arch=RECO_ARCH,
        pretrained=True,
    )
    import torch

    if torch.cuda.is_available():
        predictor = predictor.to("cuda")  # docTR does NOT move models to GPU itself
        predictor = predictor.half()  # fp16: ~2x faster on A100
        # raise internal batch sizes: docTR defaults to 2 (80GB-free GPU window)
        predictor.det_predictor.pre_processor.batch_size = 16
        predictor.reco_predictor.pre_processor.batch_size = 64
        logger.info("docTR on cuda:0 (fp16, det-batch 16 / reco-batch 64)")
    else:
        logger.info("docTR on CPU (cuda unavailable)")
    logger.info("docTR ready in %.1fs", time.time() - t0)

    grand = {"files": 0, "pages": 0, "words": 0}
    for f in files:
        t0 = time.time()
        try:
            stats = enrich_jsonl_file(f, predictor, args.dpi, args.batch_size)
        except Exception as e:  # noqa: BLE001
            logger.error("%s: FAILED (%s)", f.name, e)
            continue
        grand["files"] += 1
        grand["pages"] += stats["pages"]
        grand["words"] += stats["words"]
        logger.info(
            "%s: %d pages, %d words, coverage=%.1f%% (%.1fs)",
            f.name,
            stats["pages"],
            stats["words"],
            stats["coverage"] * 100.0,
            time.time() - t0,
        )

    logger.info("DONE: %d files, %d pages, %d words mapped", grand["files"], grand["pages"], grand["words"])


if __name__ == "__main__":
    main()
