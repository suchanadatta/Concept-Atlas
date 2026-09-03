#!/usr/bin/env python3
"""Add paragraph-level structure to corpus page JSONLs.

For every block, splits its text into semantic paragraphs (blank-line
separators) and attaches ``paragraphs[]``:

    paragraphs[] = [{
        "id", "text",
        "start"/"end"   : char offsets into the BLOCK text,
        "bbox_pts"      : union of member word boxes (PDF points),
        "words"         : block words inside the paragraph, offsets REBASED
                          to the paragraph text,
        "word_coverage"
    }]

Pure geometry/text pass — no OCR re-inference. Idempotent.

Usage: python tools/add_paragraphs.py --output outputs/corpus
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "GLM-OCR") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "GLM-OCR"))

from glmocr.utils.word_mapping import split_block_paragraphs  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", default="outputs/corpus")
    args = ap.parse_args()

    files = sorted(Path(args.output).rglob("*.pages.jsonl"))
    total_p = 0
    multi = 0
    for f in files:
        lines = []
        with open(f, "r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if raw:
                    lines.append(json.loads(raw))
        n_p = 0
        for line in lines:
            for b in line.get("blocks") or []:
                paras = split_block_paragraphs(b)
                if len(paras) > 1:
                    multi += 1
                b["paragraphs"] = paras or None
                n_p += len(paras)
        with open(f, "w", encoding="utf-8") as fh:
            for line in lines:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        total_p += n_p
    print(f"add_paragraphs: {len(files)} files, {total_p} paragraphs "
          f"({multi} blocks were split into multiple paragraphs)")


if __name__ == "__main__":
    main()
