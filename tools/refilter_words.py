#!/usr/bin/env python3
"""Apply the geometry-consistency word filter to all corpus JSONLs.

Pure geometry pass (no OCR re-inference): drops words whose boxes break
reading order (mis-paired by alignment), so the final mappings contain no
out-of-order word boxes. Idempotent. Runs in the final check pipeline.

Usage: python tools/refilter_words.py --output outputs/corpus
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "GLM-OCR") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "GLM-OCR"))

from glmocr.utils.word_mapping import filter_word_order  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", default="outputs/corpus")
    args = ap.parse_args()

    files = sorted(Path(args.output).rglob("*.pages.jsonl"))
    total_dropped = 0
    total_kept = 0
    for f in files:
        lines = []
        with open(f, "r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if raw:
                    lines.append(json.loads(raw))
        changed = False
        for line in lines:
            for b in line.get("blocks") or []:
                words = b.get("words") or []
                if not words:
                    continue
                kept = filter_word_order(words)
                if len(kept) != len(words):
                    total_dropped += len(words) - len(kept)
                    changed = True
                b["words"] = kept or None
                b["word_coverage"] = (
                    round(len(kept) / max(1, len(words)), 4)
                    if words
                    else 1.0
                )
                total_kept += len(kept)
        if changed:
            with open(f, "w", encoding="utf-8") as fh:
                for line in lines:
                    fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    print(f"refilter: {len(files)} files, kept {total_kept}, dropped {total_dropped}")


if __name__ == "__main__":
    main()
