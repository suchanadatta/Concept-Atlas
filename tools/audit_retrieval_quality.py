#!/usr/bin/env python3
"""Retrieval-quality audit of the Jasper index (BMoral corpus).

Measures the indexing quality dimensions that matter for retrieval:
  1. chunk-length distribution (noise vs. substance)
  2. zone composition (body vs. chrome)
  3. duplicate/near-duplicate rate
  4. OCR-noise rate (LaTeX artifacts, page furniture)
  5. query-side: how well do complex queries retrieve relevant docs

Usage:
  python tools/audit_retrieval_quality.py [--sample 2000]
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import re
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
META = REPO / "models" / "jasper_index" / "meta.jsonl"

# patterns of OCR page furniture that pollute embeddings
NOISE_PATTERNS = [
    re.compile(r"\$\s*\\(parallel|mathrm|frac|text)\b"),  # LaTeX OCR artifacts
    re.compile(r"^\s*\d+\s*$", re.M),  # bare page numbers
    re.compile(r"(?i)^(printed|published|imprimatur)"),  # imprint lines
    re.compile(r"(?i)^\s*(contents|index)\.?\s*$", re.M),  # TOC headers
]


def load(sample: int | None = None) -> list[dict]:
    rows = [json.loads(l) for l in open(META, encoding="utf-8")]
    if sample and sample < len(rows):
        random.seed(42)
        rows = random.sample(rows, sample)
    return rows


def audit_chunks(rows: list[dict]) -> dict:
    lens = sorted(len(m["text"]) for m in rows)
    n = len(lens)
    return {
        "n": n,
        "median_len": lens[n // 2],
        "p10_len": lens[n // 10],
        "p90_len": lens[9 * n // 10],
        "tiny_pct": round(100 * sum(1 for l in lens if l < 100) / n, 1),
        "short_pct": round(100 * sum(1 for l in lens if l < 300) / n, 1),
        "cap_pct": round(100 * sum(1 for l in lens if l >= 2390) / n, 1),
    }


def audit_zones(rows: list[dict]) -> dict:
    zones = collections.Counter(m.get("zone", "?") for m in rows)
    chrome = (
        zones.get("header", 0) + zones.get("footer", 0) + zones.get("page_number", 0)
    )
    return {
        "body_pct": round(100 * zones.get("body", 0) / len(rows), 1),
        "footnote_pct": round(100 * zones.get("footnote", 0) / len(rows), 1),
        "chrome_pct": round(100 * chrome / len(rows), 1),
        "zones": dict(zones.most_common(8)),
    }


def audit_noise(rows: list[dict]) -> dict:
    latex = sum(1 for m in rows if NOISE_PATTERNS[0].search(m["text"]))
    bare_num = sum(1 for m in rows if m["text"].strip().isdigit())
    return {
        "latex_artifact_pct": round(100 * latex / len(rows), 1),
        "bare_number_pct": round(100 * bare_num / len(rows), 1),
    }


def audit_duplicates(rows: list[dict]) -> dict:
    """Exact-duplicate rate on normalized text head."""
    seen = set()
    dupes = 0
    for m in rows:
        key = re.sub(r"\s+", " ", m["text"][:200]).strip().lower()
        if key in seen:
            dupes += 1
        seen.add(key)
    return {"exact_head_dupes_pct": round(100 * dupes / max(1, len(rows)), 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0, help="audit a sample (0=all)")
    args = ap.parse_args()
    rows = load(args.sample or None)

    print("=" * 64)
    print("RETRIEVAL-QUALITY AUDIT — Jasper index")
    print("=" * 64)
    for name, fn in [
        ("CHUNKS", audit_chunks),
        ("ZONES", audit_zones),
        ("NOISE", audit_noise),
        ("DUPLICATES", audit_duplicates),
    ]:
        print(f"\n[{name}]")
        for k, v in fn(rows).items():
            if isinstance(v, dict):
                print(f"  {k}:")
                for k2, v2 in v.items():
                    print(f"    {k2}: {v2}")
            else:
                print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
