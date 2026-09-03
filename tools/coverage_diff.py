#!/usr/bin/env python3
"""Before/after coverage comparison from plans/coverage_snapshot_fullset.json.

Reads CURRENT stored coverage per book and diffs against the snapshot taken
before re-enrichment. Usage:
    python tools/coverage_diff.py [--snapshot plans/coverage_snapshot_fullset.json]
"""
import argparse
import glob
import json
import os

ap = argparse.ArgumentParser()
ap.add_argument("--snapshot", default="plans/coverage_snapshot_fullset.json")
args = ap.parse_args()

before = json.load(open(args.snapshot))
rows = []
for f in sorted(glob.glob("outputs/full_set/*/*.pages.jsonl")):
    if "/collection/" in f:
        continue
    stem = os.path.basename(f).replace(".pages.jsonl", "")
    glm = w = 0
    for line in open(f):
        d = json.loads(line)
        for b in d.get("blocks") or []:
            glm += len((b.get("text") or "").split())
            w += len(b.get("words") or [])
    cov = w / max(1, glm)
    b = before.get(stem, {})
    bcov = b.get("cov", 0.0)
    rows.append((stem, bcov * 100, cov * 100))

rows.sort(key=lambda r: r[2] - r[1])
print(f"{'book':58s} {'before':>7} {'after':>7} {'delta':>7}")
for stem, b, a in rows:
    print(f"{stem[:58]:58s} {b:6.1f}% {a:6.1f}% {a-b:+6.1f}")
agg_b = sum(r[1] for r in rows) / len(rows)
agg_a = sum(r[2] for r in rows) / len(rows)
print(f"\nmean: {agg_b:.1f}% -> {agg_a:.1f}% | books improved: "
      f"{sum(1 for r in rows if r[2] > r[1] + 0.5)}/{len(rows)}")
