#!/usr/bin/env python3
"""Benchmark docTR recognition models for word-coverage on the worst books.

Runs the REAL enrichment path (docTR detect+reco -> assign to blocks ->
DP alignment via glmocr.utils.word_mapping.enrich_blocks) over a sample of
pages, comparing reco architectures head-to-head:

    python tools/bench_reco.py --book ASTELL_1704_Moderation_truly_Stated \
        --recos crnn_mobilenet_v3_small parseq --pages 10
"""
from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "GLM-OCR"))
sys.path.insert(0, str(REPO_ROOT / "tools"))

os.environ.setdefault("DOCTR_CACHE_DIR", str(REPO_ROOT / "models" / "doctr"))

import numpy as np  # noqa: E402
import pymupdf  # noqa: E402

from word_map import extract_page_words, build_provider_map  # noqa: E402
from glmocr.utils.word_mapping import enrich_blocks  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bench_reco")


def sample_pages(jsonl_path: Path, n: int):
    lines = []
    with open(jsonl_path) as f:
        for raw in f:
            if raw.strip():
                d = json.loads(raw)
                if len((d.get("text") or "").strip()) > 200:
                    lines.append(d)
    step = max(1, len(lines) // n)
    return lines[::step][:n]


def run_arch(reco: str, det: str, pages, doc, dpi: int, batch: int, fp16: bool):
    from doctr.models import ocr_predictor
    import torch

    t0 = time.time()
    predictor = ocr_predictor(det_arch=det, reco_arch=reco, pretrained=True)
    if torch.cuda.is_available():
        predictor = predictor.to("cuda")
        if fp16:
            predictor = predictor.half()
        predictor.det_predictor.pre_processor.batch_size = 8
        predictor.reco_predictor.pre_processor.batch_size = 32
    log.info("[%s] model ready in %.1fs", reco, time.time() - t0)

    glm_words = matched = 0
    t0 = time.time()
    for start in range(0, len(pages), batch):
        chunk = pages[start : start + batch]
        imgs, metas = [], []
        for line in chunk:
            page = doc[line["page_index"]]
            pix = page.get_pixmap(matrix=pymupdf.Matrix(dpi / 72.0, dpi / 72.0))
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n
            )
            imgs.append(img)
            metas.append((pix.width, pix.height))
        results = predictor(imgs)
        for line, page_res, (w_px, h_px) in zip(chunk, results.pages, metas):
            page_words = extract_page_words(page_res, w_px, h_px)
            provider_map = build_provider_map(page_words, line.get("blocks") or [])
            enriched = enrich_blocks(
                line.get("blocks") or [], provider_map, line.get("page_rect_pts")
            )
            stats = enriched["stats"]
            glm_words += stats["glm_words"]
            matched += stats["matched"]
    dt = time.time() - t0
    cov = matched / max(1, glm_words)
    return cov, glm_words, dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True, help="book dir stem under outputs/full_set")
    ap.add_argument("--out-root", default="outputs/full_set")
    ap.add_argument("--det", default="fast_base")
    ap.add_argument("--recos", nargs="+", default=["crnn_mobilenet_v3_small", "parseq"])
    ap.add_argument("--pages", type=int, default=10)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--no-fp16", action="store_true")
    args = ap.parse_args()

    cands = glob.glob(f"{args.out_root}/{args.book}/*.pages.jsonl") or glob.glob(
        f"{args.out_root}/**/{args.book}/*.pages.jsonl", recursive=True
    )
    if not cands:
        sys.exit(f"no jsonl for {args.book}")
    jsonl_path = Path(cands[0])
    source = None
    with open(jsonl_path) as f:
        first = json.loads(f.readline())
    source = first["source"]
    pages = sample_pages(jsonl_path, args.pages)
    log.info("book=%s pages=%d source=%s", args.book, len(pages), source)

    doc = pymupdf.open(source)
    fp16 = not args.no_fp16
    for reco in args.recos:
        try:
            cov, n, dt = run_arch(reco, args.det, pages, doc, args.dpi, args.batch, fp16)
            print(
                f"RESULT {jsonl_path.parent.name[:40]} reco={reco:28s} "
                f"coverage={cov*100:.1f}% ({n} glm words) {dt:.1f}s"
            )
        except Exception as e:  # noqa: BLE001
            print(f"RESULT reco={reco}: FAILED {e}")
            if torch_cuda_check() and not fp16:
                raise
    doc.close()


def torch_cuda_check():
    try:
        import torch

        return torch.cuda.is_available()
    except Exception:
        return False


if __name__ == "__main__":
    main()
