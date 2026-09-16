#!/usr/bin/env python3
"""Fail if the LaTeX run produced any warning at all.

"Compiles cleanly" usually means "no errors". Here it means no warnings and no
bad boxes either, because those are the things that quietly ruin a page:
an overfull line sticking into the margin, a reference that silently resolved
to ??, a font substituted for one that was never installed.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Patterns that count as a complaint worth failing on.
PATTERNS = [
    (re.compile(r"^(?:! )?LaTeX Warning:.*", re.M), "LaTeX warning"),
    (re.compile(r"^Package (\w+) Warning:.*", re.M), "package warning"),
    (re.compile(r"^Class \w+ Warning:.*", re.M), "class warning"),
    (re.compile(r"^LaTeX Font Warning:.*", re.M), "font warning"),
    (re.compile(r"^(Overfull|Underfull) \\[hv]box.*", re.M), "bad box"),
    (re.compile(r"^! .*", re.M), "error"),
    (re.compile(r"^pdfTeX warning.*", re.M), "pdfTeX warning"),
    (re.compile(r"^Missing character:.*", re.M), "missing character"),
]

# Noise that is not ours to fix and cannot be silenced from the document.
IGNORE = [
    re.compile(r"Package rerunfilecheck Warning: File .* has changed"),
]


def main(path: str) -> int:
    log = Path(path)
    if not log.exists():
        print(f"no log at {path}", file=sys.stderr)
        return 2
    text = log.read_text(encoding="utf-8", errors="replace")
    found: list[tuple[str, str]] = []
    for pat, kind in PATTERNS:
        for m in pat.finditer(text):
            line = m.group(0).strip()
            if any(ig.search(line) for ig in IGNORE):
                continue
            found.append((kind, line))
    if not found:
        print(f"{log.name}: clean — no warnings, no bad boxes")
        return 0
    print(f"{log.name}: {len(found)} complaint(s)")
    for kind, line in found:
        print(f"  [{kind}] {line[:160]}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "paper.log"))
