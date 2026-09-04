#!/usr/bin/env python3
"""Retrieval evaluation harness for the BMoral search engine.

Runs a set of test queries against the live semantic server (:8790) and
scores results with graded relevance judgments. Produces nDCG@k, MRR, and
per-query diagnostics so index changes can be measured, not guessed.

Relevance grading (automatic heuristics, corpus-specific):
  2 = strong: query content-terms present AND (semantic sim > 0.55 OR
      the passage is from a book whose title/concept matches the query)
  1 = partial: some query terms present, moderate similarity
  0 = noise: no term overlap and low similarity

Usage:
  python tools/eval_retrieval.py [--port 8790] [--k 10]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- test set
# Complex, philosopher-style queries (mirroring the corpus's 42 research
# queries) with the books a perfect engine SHOULD surface.
TESTS: list[dict] = [
    {
        "query": "whether humans are by nature self-interested or benevolent",
        "expect_books": [
            "Hutcheson",
            "Mandeville",
            "Butler",
            "Shaftesbury",
            "Cockburn",
        ],
        "expect_terms": ["self-love", "benevolen", "selfish", "social"],
    },
    {
        "query": "the role of sympathy in moral judgement",
        "expect_books": ["Hutcheson", "Smith", "Turnbull"],
        "expect_terms": ["sympathy", "fellow-feel", "moral sense"],
    },
    {
        "query": "can atheists be virtuous and accountable for their actions",
        "expect_books": ["Cockburn", "Warburton", "Clarke", "Locke"],
        "expect_terms": ["atheis", "virtue", "accountable"],
    },
    {
        "query": "liberty and necessity whether the will is free",
        "expect_books": ["Clarke", "Collins", "King", "Turnbull"],
        "expect_terms": ["liberty", "necessity", "will", "free"],
    },
    {
        "query": "marriage compared to slavery in the condition of women",
        "expect_books": ["Astell", "Chudleigh", "Drake", "Chapone"],
        "expect_terms": ["marriage", "slaver", "women", "subjection"],
    },
    {
        "query": "government of the passions by reason and habit",
        "expect_books": ["Watts", "Astell", "Shaftesbury", "Fordyce"],
        "expect_terms": ["passion", "govern", "reason", "habit"],
    },
    {
        "query": "the origin of evil and why God allows it",
        "expect_books": ["King", "Turnbull", "Law"],
        "expect_terms": ["evil", "origin", "God", "divine"],
    },
    {
        "query": "conscience as the authority in moral deliberation",
        "expect_books": ["Butler", "Cockburn", "Price"],
        "expect_terms": ["conscience", "authority", "moral"],
    },
]


def content_terms(q: str) -> list[str]:
    STOP = {
        "the",
        "a",
        "an",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "and",
        "or",
        "by",
        "with",
        "as",
        "is",
        "are",
        "be",
        "whether",
        "can",
        "their",
        "it",
        "its",
        "why",
        "how",
        "what",
        "which",
        "who",
        "compared",
        "role",
        "condition",
        "in",
        "for",
    }
    return [t for t in re.split(r"\W+", q.lower()) if len(t) > 2 and t not in STOP]


def grade(result: dict, test: dict) -> int:
    """Corpus-specific graded relevance (0/1/2)."""
    text_l = (result.get("snippet") or "").lower()
    book = (result.get("book_id") or "").lower()
    terms = [t.lower() for t in test["expect_terms"]]
    qterms = content_terms(test["query"])
    sem = float(result.get("semantic") or result.get("score") or 0)

    term_hits = sum(1 for t in terms if t in text_l)
    qterm_hits = sum(1 for t in qterms if t in text_l)
    book_hit = any(b.lower() in book for b in test["expect_books"])

    if (term_hits >= 2 or (qterm_hits >= 2 and sem > 0.5)) and (book_hit or sem > 0.55):
        return 2
    if term_hits >= 1 or (qterm_hits >= 1 and sem > 0.45) or book_hit:
        return 1
    return 0


def ndcg(grades: list[int], k: int) -> float:
    """nDCG@k with graded relevance (2/1/0)."""

    def dcg(g):
        return sum((2**gi - 1) / math.log2(i + 2) for i, gi in enumerate(g[:k]))

    ideal = sorted(grades, reverse=True)
    return dcg(grades) / dcg(ideal) if dcg(ideal) > 0 else 0.0


def run_query(port: int, query: str, top_k: int) -> list[dict]:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/semantic",
        data=json.dumps({"query": query, "top_k": top_k}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()).get("results", [])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args()

    all_ndcg, all_mrr, all_recall2 = [], [], []
    print(
        f"{'query':58s} {'nDCG@' + str(args.k):>8} {'MRR':>6} {'rel2@' + str(args.k):>9}"
    )
    print("-" * 84)
    for test in TESTS:
        t0 = time.time()
        results = run_query(args.port, test["query"], args.k * 2)
        dt = time.time() - t0
        grades = [grade(r, test) for r in results[: args.k]]
        q_ndcg = ndcg(grades, args.k)
        # MRR: first grade-2 result
        mrr = 0.0
        for i, g in enumerate(grades):
            if g == 2:
                mrr = 1.0 / (i + 1)
                break
        rel2 = sum(1 for g in grades if g == 2)
        all_ndcg.append(q_ndcg)
        all_mrr.append(mrr)
        all_recall2.append(rel2)
        print(
            f"{test['query'][:58]:58s} {q_ndcg:8.3f} {mrr:6.3f} {rel2:9d}  ({dt:.1f}s)"
        )

    print("-" * 84)
    print(
        f"{'MEAN':58s} {sum(all_ndcg) / len(all_ndcg):8.3f} "
        f"{sum(all_mrr) / len(all_mrr):6.3f} "
        f"{sum(all_recall2) / len(all_recall2):9.1f}"
    )
    print(
        f"\nnDCG@{args.k}: {sum(all_ndcg) / len(all_ndcg):.3f}  "
        f"MRR: {sum(all_mrr) / len(all_mrr):.3f}  "
        f"rel2/query: {sum(all_recall2) / len(all_recall2):.1f}"
    )


if __name__ == "__main__":
    main()
