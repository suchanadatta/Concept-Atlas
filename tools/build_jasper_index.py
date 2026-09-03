#!/usr/bin/env python3
"""Build the Jasper embedding index for the BMoral corpus.

Embeds every paragraph (OCR blocks with text) across all 129 books into
a flat float16 matrix + metadata JSONL, for instant cosine-search retrieval.

Outputs (models/jasper_index/):
  embeddings.npy   float16 [N, 2048]
  meta.jsonl       one line per paragraph: book_id, page, block_id, text,
                   bbox_pts, zone, printed_page

Run when GPU is free:
  python tools/build_jasper_index.py [--device cuda] [--batch 64]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
MODEL_PATH = REPO / "models" / "Jasper-Token-Compression-600M"
OUT_DIR = REPO / "models" / "jasper_index"
OCR_GLOBS = [
    str(REPO / "outputs" / "full_set" / "*" / "*.pages.jsonl"),
    str(REPO / "outputs" / "corpus" / "*" / "*" / "*.pages.jsonl"),
]
TXT_GLOB = str(REPO / "data" / "txt_books" / "*.txt")

# Jasper was trained with texts up to 1024 tokens; keep paragraphs within that.
MAX_CHARS = 2400


def iter_txt_paragraphs():
    """Yield paragraph dicts from plain-text books (paragraph-split)."""
    import glob as _glob
    for f in sorted(_glob.glob(TXT_GLOB)):
        book_id = Path(f).stem
        raw = Path(f).read_text(encoding="utf-8", errors="ignore")
        # paragraphs = blank-line separated chunks
        import re as _re
        chunks = [c.strip() for c in _re.split(r"\n\s*\n", raw) if c.strip()]
        for i, ch in enumerate(chunks):
            if len(ch) < 40:
                continue
            yield {
                "book_id": book_id,
                "page": None,          # txt books have no PDF pages
                "printed_page": None,
                "block_id": f"para-{i}",
                "zone": "body",
                "bbox_pts": None,
                "text": ch[:MAX_CHARS],
                "source": "txt",
            }


def iter_paragraphs():
    """Yield paragraph dicts across the corpus (deduped by path)."""
    seen = set()
    for pattern in OCR_GLOBS:
        for f in sorted(glob.glob(pattern)):
            if "/collection/" in f or f in seen:
                continue
            seen.add(f)
            book_id = Path(f).parent.name
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    page = d.get("page_number")
                    printed = d.get("printed_page_number")
                    printed_val = (
                        printed.get("value") if isinstance(printed, dict) else printed
                    )
                    for b in d.get("blocks") or []:
                        text = (b.get("text") or "").strip()
                        if len(text) < 40:  # skip headers/fragments
                            continue
                        yield {
                            "book_id": book_id,
                            "page": page,
                            "printed_page": printed_val,
                            "block_id": b.get("id"),
                            "zone": b.get("zone"),
                            "bbox_pts": b.get("bbox_pts"),
                            "text": text[:MAX_CHARS],
                        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--device",
        default="cuda" if os.environ.get("BMORAL_FORCE_CPU") != "1" else "cpu",
    )
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument(
        "--limit", type=int, default=0, help="embed only first N paragraphs (debug)"
    )
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    emb_path = OUT_DIR / "embeddings.npy"
    meta_path = OUT_DIR / "meta.jsonl"

    # collect paragraphs
    t0 = time.time()
    paras = list(iter_paragraphs())
    txt_paras = list(iter_txt_paragraphs())
    print(f"txt paragraphs: {len(txt_paras):,} from plain-text books")
    paras.extend(txt_paras)
    if args.limit:
        paras = paras[: args.limit]
    print(f"corpus paragraphs: {len(paras):,} (collected in {time.time() - t0:.1f}s)")

    # load model
    import torch
    from sentence_transformers import SentenceTransformer

    dtype = torch.bfloat16 if args.device == "cuda" else torch.float32
    print(f"loading Jasper on {args.device} ({dtype})…")
    model = SentenceTransformer(
        str(MODEL_PATH),
        model_kwargs={
            "torch_dtype": dtype,
            "attn_implementation": "sdpa",
            "trust_remote_code": True,
        },
        trust_remote_code=True,
        device=args.device,
    )

    # embed
    texts = [p["text"] for p in paras]
    t0 = time.time()
    print(f"embedding {len(texts):,} paragraphs (batch {args.batch})…")
    emb = model.encode(
        texts,
        normalize_embeddings=True,
        compression_ratio=0.3333,
        batch_size=args.batch,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    dt = time.time() - t0
    print(f"encoded in {dt:.0f}s ({len(texts) / dt:.0f} paras/s), shape={emb.shape}")

    # save float16 (halves disk, negligible quality loss for cosine ranking)
    emb16 = emb.astype(np.float16)
    np.save(emb_path, emb16)
    with open(meta_path, "w", encoding="utf-8") as f:
        for p in paras:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(
        f"saved: {emb_path} ({emb16.nbytes / 1e6:.0f} MB), {meta_path.name} ({len(paras):,} lines)"
    )


if __name__ == "__main__":
    main()
