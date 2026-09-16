"""A0 — recover a publication year for books whose id does not carry one.

Two thirds of the book ids are AUTHOR_YEAR_Title and date themselves. The rest
are typed editions and rescans filed under a plain title, and dropping them
would throw away a third of the corpus in any analysis over time.

Rather than supply dates from outside, we read them off the books. The naive
version of this -- take the first year printed in the front matter -- is worse
than useless: it returns 1671 for Shaftesbury's Characteristicks (his birth
year, from a modern editor's note) and 1740 for four different Hutcheson works
that share a Liberty Fund preface. Both are the same failure: modern apparatus
sits in front of the original title page and prints dates of its own.

So a year is accepted only when the page it sits on looks like a period title
page -- an imprint line naming a place and a printer -- or when it is set in
roman numerals, which modern front matter does not use. Any year equal to the
author's own birth or death year, as recorded in the author registry, is
refused outright. Every accepted date is written out with its page and the
exact string it came from, and every rejection with its reason, so the whole
table can be checked against the scans.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common as C

ARABIC = re.compile(r"(?<!\d)(1[5-8]\d\d)(?!\d)")
ROMAN = re.compile(r"\bM[.\s]?D?[.\s]?C{0,4}[.\s]?(?:XC|XL|L?X{0,3})[.\s]?(?:IX|IV|V?I{0,3})\b")
# An eighteenth-century imprint names where and by whom the thing was printed.
IMPRINT = re.compile(
    r"\b(printed|imprinted|sold by|bookseller|booksellers|for the author"
    r"|london|edinburgh|glasgow|dublin|oxford|cambridge|westminster)\b", re.I)
# Modern apparatus announces itself just as clearly.
MODERN = re.compile(
    r"\b(liberty fund|copyright|©|isbn|reprinted|editor|edited by|introduction by"
    r"|library of congress|all rights reserved|this edition|indianapolis)\b", re.I)
FRONT_PAGES = 8
PLAUSIBLE = range(1600, 1831)


def roman_value(s: str) -> int | None:
    s = re.sub(r"[.\s]", "", s).upper()
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    if not s or any(ch not in vals for ch in s):
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        v = vals[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def author_lifespans() -> dict[str, tuple[int | None, int | None]]:
    """book_id -> (born, died), so a birth year can never pass as an imprint."""
    a = C.get(f"{C.UI}/book/api/authors")
    span: dict[str, tuple[int | None, int | None]] = {}
    for au in a["authors"]:
        for bid in au.get("book_ids") or []:
            span[bid] = (au.get("born"), au.get("died"))
    return span


def main():
    meta = C.load_meta()
    books: dict[str, list[dict]] = {}
    for m in meta:
        books.setdefault(m["book_id"], []).append(m)
    span = author_lifespans()

    recovered, rejected, failed = {}, [], []
    for bid, rows in books.items():
        if C.book_year(bid):
            continue
        born, died = span.get(bid, (None, None))
        front = sorted((r for r in rows if (r.get("page") or 99) <= FRONT_PAGES),
                       key=lambda r: (r.get("page") or 0, r.get("block_id") or 0))
        # A page is judged once; the candidates on it inherit that judgement.
        by_page: dict[int, list[dict]] = {}
        for r in front:
            by_page.setdefault(r.get("page") or 0, []).append(r)

        hit = None
        for page in sorted(by_page):
            text = "\n".join(r.get("raw_text") or "" for r in by_page[page])
            imprint, modern = bool(IMPRINT.search(text)), bool(MODERN.search(text))
            cands: list[tuple[int, str, str]] = []
            for m in ROMAN.finditer(text):
                y = roman_value(m.group(0))
                if y in PLAUSIBLE:
                    cands.append((y, "roman", m.group(0)))
            for m in ARABIC.finditer(text):
                y = int(m.group(1))
                if y in PLAUSIBLE:
                    cands.append((y, "arabic", m.group(1)))
            for y, form, s in cands:
                if y in (born, died):
                    rejected.append({"book": bid, "year": y, "page": page,
                                     "why": "matches the author's birth or death year"})
                    continue
                if form == "arabic" and not imprint:
                    rejected.append({"book": bid, "year": y, "page": page,
                                     "why": "no imprint on the page"})
                    continue
                if form == "arabic" and modern and not imprint:
                    rejected.append({"book": bid, "year": y, "page": page,
                                     "why": "modern front matter"})
                    continue
                hit = {"year": y, "page": page, "form": form, "string": s,
                       "imprint": imprint, "modern_matter": modern}
                break
            if hit:
                break
        (recovered.__setitem__(bid, hit) if hit else failed.append(bid))

    forms = Counter(v["form"] for v in recovered.values())
    dated_before = sum(1 for b in books if C.book_year(b))
    p_before = sum(len(r) for b, r in books.items() if C.book_year(b))
    p_after = p_before + sum(len(books[b]) for b in recovered)

    out = {
        "books_total": len(books),
        "dated_by_id": dated_before,
        "recovered_from_title_page": len(recovered),
        "still_undated": len(failed),
        "forms": dict(forms),
        "rejections": len(rejected),
        "rejection_reasons": dict(Counter(r["why"] for r in rejected)),
        "passage_coverage_before": p_before,
        "passage_coverage_after": p_after,
        "passages_total": len(meta),
        "recovered": recovered,
        "rejected": rejected,
        "failed": failed,
    }
    C.save("a0_dates.json", out)
    print(f"  dated by id: {dated_before}/{len(books)}")
    print(f"  recovered from a title page: {len(recovered)} ({dict(forms)})")
    print(f"  candidates refused: {len(rejected)} {dict(Counter(r['why'] for r in rejected))}")
    print(f"  still undated: {len(failed)}")
    print(f"  passage coverage {p_before/len(meta)*100:.1f}% -> {p_after/len(meta)*100:.1f}%")


if __name__ == "__main__":
    main()
