#!/usr/bin/env python3
"""Index builder v2 — retrieval-scientist improvements over v1.

Changes vs tools/build_jasper_index.py (v1), each driven by the audit:
  1. NOISE FILTER: drop chrome zones (header/footer/page_number/title),
     bare page numbers, and publisher furniture — they pollute the
     embedding space with near-identical vectors.
  2. MIN-LENGTH GATE: chunks < 120 chars are merged forward into the next
     chunk of the same page when possible, else dropped (v1 indexed 31%
     tiny fragments — running heads, folios — that crowd the top-k).
  3. RICH-PASSAGE CONCATENATION: each chunk is prefixed with
     "[book title] [zone]" before embedding — Jasper is a distilled model;
     the prefix grounds the vector in its source (title terms like
     'An Essay on the Origin of Evil' become part of the passage vector,
     so book-level queries match directly).
  4. FOOTNOTE UPSAMPLING: footnotes are scholarly gold but only 4.9% of
     chunks; keep them all (they already pass the gate).

Output (models/jasper_index_v2/):
  embeddings.npy   float16 [N, 2048]
  meta.jsonl       original fields + `prefix` used at embed time

Run when GPU is free:
  python tools/build_jasper_index_v2.py [--device cuda] [--batch 128]
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
MODEL_PATH = REPO / "models" / "Jasper-Token-Compression-600M"
OUT_DIR = REPO / "models" / "jasper_index_v2"
OCR_GLOBS = [
    str(REPO / "outputs" / "full_set" / "*" / "*.pages.jsonl"),
    str(REPO / "outputs" / "corpus" / "*" / "*" / "*.pages.jsonl"),
]
TXT_GLOB = str(REPO / "data" / "txt_books" / "*.txt")

MAX_CHARS = 2400  # Jasper trained to 1024 tokens ≈ 2400 chars
MIN_CHARS = 120  # below this: merge or drop
DROP_ZONES = {"header", "footer", "page_number", "title"}
KEEP_ZONES = {"body", "footnote", "reference", "table"}  # None-zone body text kept
CHROME_RE = re.compile(
    r"^(printed (for|by)|imprimatur|contents\.?$|index\.?$|errata|"
    r"advertisements?\b|books (printed|sold))",
    re.I,
)


def norm_title(book_id: str) -> str:
    """Human-readable book title from the book_id for the embed prefix."""
    t = re.sub(r"^[A-Z\-]+(?:_[A-Za-z0-9.\-]+)*_\d{4}(?:_\d{4})*_?", "", book_id)
    t = t.replace("_", " ").replace("-", " ").strip()
    return t[:80] if t else book_id[:80]


def iter_page_chunks():
    """Yield (text, meta) chunks from OCR JSONLs with zone filtering."""
    seen = set()
    for pattern in OCR_GLOBS:
        for f in sorted(glob.glob(pattern)):
            if "/collection/" in f or f in seen:
                continue
            seen.add(f)
            book_id = Path(f).parent.name
            title = norm_title(book_id)
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
                        zone = b.get("zone") or "body"
                        text = (b.get("text") or "").strip()
                        if len(text) < 20:
                            continue
                        if zone in DROP_ZONES:
                            continue
                        if CHROME_RE.search(text[:60]):
                            continue
                        if re.fullmatch(r"[\dIVXLC]+\.?", text):
                            continue
                        yield (
                            text[:MAX_CHARS],
                            {
                                "book_id": book_id,
                                "page": page,
                                "printed_page": printed_val,
                                "block_id": b.get("id"),
                                "zone": zone,
                                "bbox_pts": b.get("bbox_pts"),
                                "source": "ocr",
                            },
                            title,
                            zone,
                        )


def iter_txt_chunks():
    """Yield paragraph chunks from plain-text books."""
    for f in sorted(glob.glob(TXT_GLOB)):
        book_id = Path(f).stem
        title = norm_title(book_id)
        raw = Path(f).read_text(encoding="utf-8", errors="ignore")
        for i, ch in enumerate(re.split(r"\n\s*\n", raw)):
            ch = ch.strip()
            if len(ch) < 40:
                continue
            yield (
                ch[:MAX_CHARS],
                {
                    "book_id": book_id,
                    "page": None,
                    "printed_page": None,
                    "block_id": f"para-{i}",
                    "zone": "body",
                    "bbox_pts": None,
                    "source": "txt",
                },
                title,
                "body",
            )


def build_passages():
    """Collect, gate, and merge chunks into embedding passages."""
    raw = []
    for text, meta, title, zone in iter_page_chunks():
        raw.append((text, meta, title, zone))
    for text, meta, title, zone in iter_txt_chunks():
        raw.append((text, meta, title, zone))

    # merge tiny same-page body chunks forward
    merged: list[tuple[str, dict, str]] = []
    for text, meta, title, zone in raw:
        if len(text) < MIN_CHARS and zone == "body" and merged:
            ptext, pmeta, ptitle = merged[-1]
            if (
                ptitle == title
                and pmeta.get("page") == meta.get("page")
                and len(ptext) + len(text) + 1 <= MAX_CHARS
            ):
                merged[-1] = (ptext + "\n" + text, pmeta, ptitle)
                continue
        if len(text) >= MIN_CHARS or zone == "footnote":
            merged.append((text, meta, title))

    # build embed passages: "[title] [zone] text"
    passages, metas = [], []
    for text, meta, title in merged:
        prefix = f"[{title}]"
        if meta["zone"] == "footnote":
            prefix += " [footnote]"
        passages.append(f"{prefix} {text}")
        m = dict(meta)
        m["prefix"] = prefix
        m["raw_text"] = text          # original chunk (display/snippets)
        metas.append(m)
    return passages, metas


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--limit", type=int, default=0, help="debug: first N passages")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    passages, metas = build_passages()
    if args.limit:
        passages, metas = passages[: args.limit], metas[: args.limit]
    print(
        f"passages: {len(passages):,} (from 132,444 v1 chunks) in {time.time() - t0:.0f}s"
    )
    lens = sorted(len(p) for p in passages)
    n = len(lens)
    print(
        f"len: min={lens[0]} median={lens[n // 2]} p90={lens[9 * n // 10]} max={lens[-1]}"
    )

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
    t0 = time.time()
    print(f"embedding {len(passages):,} passages (batch {args.batch})…")
    emb = model.encode(
        passages,
        normalize_embeddings=True,
        compression_ratio=0.3333,
        batch_size=args.batch,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    print(
        f"encoded in {time.time() - t0:.0f}s ({len(passages) / (time.time() - t0):.0f}/s), shape={emb.shape}"
    )

    np.save(OUT_DIR / "embeddings.npy", emb.astype(np.float16))
    with open(OUT_DIR / "meta.jsonl", "w", encoding="utf-8") as f:
        for m in metas:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    print(
        f"saved: {OUT_DIR / 'embeddings.npy'} ({emb.nbytes / 1e6:.0f} MB), meta {len(metas):,} lines"
    )


if __name__ == "__main__":
    main()
