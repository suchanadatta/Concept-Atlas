"""Shared: which passages does each concept actually appear in?

Several analyses need the same thing -- for every concept, the set of passage
indices whose text uses one of its aliases. Doing it per analysis meant 202
regular expressions dragged across 90,975 texts, several times over.

So it is computed once and cached. The single pass lowercases each passage
once, then tests aliases with str.find plus an explicit boundary check, which
is markedly cheaper than a case-insensitive regex per concept per passage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common as C

CACHE = C.DATA / "concept_support.json"
LETTERS = frozenset("abcdefghijklmnopqrstuvwxyz")


def aliases_for(node: dict) -> list[str]:
    words = {node["label"].lower()} | {a.lower() for a in (node.get("aliases") or [])}
    words = {w for w in words if len(w) > 3}
    return sorted(words or {node["label"].lower()}, key=len, reverse=True)


def _hit(hay: str, needle: str) -> bool:
    """Whole-word containment, without the cost of a regex."""
    n = len(needle)
    start = 0
    while True:
        i = hay.find(needle, start)
        if i < 0:
            return False
        if (i == 0 or hay[i - 1] not in LETTERS) and \
           (i + n >= len(hay) or hay[i + n] not in LETTERS):
            return True
        start = i + 1


def build(force: bool = False) -> dict[str, list[int]]:
    if CACHE.exists() and not force:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    nodes, _ = C.load_graph()
    meta = C.load_meta()
    lowered = [(m.get("raw_text") or "").lower() for m in meta]
    print(f"  scanning {len(lowered):,} passages for {len(nodes)} concepts", flush=True)
    out: dict[str, list[int]] = {}
    for n, node in enumerate(nodes, 1):
        al = aliases_for(node)
        out[node["id"]] = [i for i, t in enumerate(lowered)
                           if any(_hit(t, a) for a in al)]
        if n % 25 == 0:
            print(f"    {n}/{len(nodes)}", flush=True)
    CACHE.write_text(json.dumps(out), encoding="utf-8")
    print(f"  cached {CACHE.relative_to(C.REPO)}", flush=True)
    return out


if __name__ == "__main__":
    s = build(force="--force" in sys.argv)
    print(f"  {len(s)} concepts, {sum(len(v) for v in s.values()):,} concept-passage pairs")
