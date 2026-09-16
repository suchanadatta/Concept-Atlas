"""A1 — what the corpus actually contains.

Counts by decade, by source (page scan vs typed edition), by author and by the
sex recorded in the author registry. Everything here is a fact about the files
on disk, not an estimate.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common as C


def main():
    meta = C.load_meta()
    print(f"passages: {len(meta):,}")

    by_book = Counter(m["book_id"] for m in meta)
    by_source = Counter(m.get("source") or "?" for m in meta)
    by_zone = Counter(m.get("zone") or "?" for m in meta)

    years = {b: C.book_year(b) for b in by_book}
    dated = {b: y for b, y in years.items() if y}
    decade_books = Counter((y // 10) * 10 for y in dated.values())
    decade_passages = Counter()
    for m in meta:
        y = years.get(m["book_id"])
        if y:
            decade_passages[(y // 10) * 10] += 1

    authors = C.get(f"{C.UI}/book/api/authors")
    groups = {g["group"]: g for g in authors["groups"]}

    # Pages per book, to show how uneven the corpus is.
    pages = {b: len({m["page"] for m in meta if m["book_id"] == b}) for b in list(by_book)[:0]} or {}

    out = {
        "passages": len(meta),
        "books": len(by_book),
        "books_dated": len(dated),
        "year_min": min(dated.values()),
        "year_max": max(dated.values()),
        "by_source": dict(by_source),
        "by_zone": dict(by_zone.most_common(8)),
        "decade_books": dict(sorted(decade_books.items())),
        "decade_passages": dict(sorted(decade_passages.items())),
        "passages_per_book": {
            "min": min(by_book.values()),
            "median": sorted(by_book.values())[len(by_book) // 2],
            "max": max(by_book.values()),
            "largest": by_book.most_common(5),
        },
        "author_groups": groups,
        "authors": len(authors["authors"]),
    }
    C.save("a1_corpus.json", out)

    # ---- figure: the corpus in time, split by how the text was obtained
    plt = C.style()
    import numpy as np

    src_by_decade = defaultdict(Counter)
    for m in meta:
        y = years.get(m["book_id"])
        if y:
            src_by_decade[(y // 10) * 10][m.get("source") or "?"] += 1
    decs = sorted(src_by_decade)
    kinds = [k for k, _ in by_source.most_common()]
    fig, ax = plt.subplots(figsize=(5.4, 2.4))
    bottom = np.zeros(len(decs))
    label = {"ocr": "page scan (OCR)", "txt": "typed edition"}
    for k in kinds:
        vals = np.array([src_by_decade[d].get(k, 0) for d in decs], dtype=float)
        ax.bar([str(d) for d in decs], vals, bottom=bottom, label=label.get(k, k), width=0.78)
        bottom += vals
    ax.set_ylabel("passages")
    ax.set_xlabel("decade of publication")
    ax.tick_params(axis="x", rotation=60)
    ax.legend(loc="upper left")
    fig.savefig(C.FIGS / "corpus_time.pdf")
    print(f"  wrote {(C.FIGS / 'corpus_time.pdf').relative_to(C.REPO)}")

    for k, v in out.items():
        if not isinstance(v, dict):
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
