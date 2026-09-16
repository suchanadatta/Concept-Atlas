"""A0b — how good is reading the date off the title page?

The recovery in A0 can be checked, because 139 books carry a year in the file
id *and* have their own title page in the scan. Running the same reader over
those gives a direct measurement: how often does the page agree with the
catalogue, and when it disagrees, by how much and in which direction?
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common as C
from a0_dates import ARABIC, ROMAN, FRONT_PAGES, PLAUSIBLE, IMPRINT, MODERN, roman_value, author_lifespans


def read_page_year(rows, born, died):
    by_page = {}
    for r in rows:
        if (r.get("page") or 99) <= FRONT_PAGES:
            by_page.setdefault(r.get("page") or 0, []).append(r)
    for page in sorted(by_page):
        text = "\n".join(r.get("raw_text") or "" for r in by_page[page])
        imprint, modern = bool(IMPRINT.search(text)), bool(MODERN.search(text))
        cands = []
        for m in ROMAN.finditer(text):
            y = roman_value(m.group(0))
            if y in PLAUSIBLE:
                cands.append((y, "roman"))
        for m in ARABIC.finditer(text):
            y = int(m.group(1))
            if y in PLAUSIBLE:
                cands.append((y, "arabic"))
        for y, form in cands:
            if y in (born, died):
                continue
            if form == "arabic" and not imprint:
                continue
            if form == "arabic" and modern and not imprint:
                continue
            return y, form, page
    return None


def main():
    meta = C.load_meta()
    books = {}
    for m in meta:
        books.setdefault(m["book_id"], []).append(m)
    span = author_lifespans()

    rows = []
    for bid, rs in books.items():
        catalogue = C.book_year(bid)
        if not catalogue:
            continue
        born, died = span.get(bid, (None, None))
        got = read_page_year(rs, born, died)
        if got:
            y, form, page = got
            rows.append({"book": bid, "catalogue": catalogue, "page_year": y,
                         "delta": y - catalogue, "form": form, "page": page})

    exact = [r for r in rows if r["delta"] == 0]
    within1 = [r for r in rows if abs(r["delta"]) <= 1]
    later = [r for r in rows if r["delta"] > 1]
    earlier = [r for r in rows if r["delta"] < -1]
    deltas = sorted(r["delta"] for r in rows)

    out = {
        "books_with_catalogue_year": sum(1 for b in books if C.book_year(b)),
        "title_page_readable": len(rows),
        "exact_match": len(exact),
        "within_one_year": len(within1),
        "page_later_than_catalogue": len(later),
        "page_earlier_than_catalogue": len(earlier),
        "exact_rate": round(len(exact) / len(rows), 4) if rows else None,
        "within_one_rate": round(len(within1) / len(rows), 4) if rows else None,
        "median_abs_delta": int(sorted(abs(d) for d in deltas)[len(deltas) // 2]) if deltas else None,
        "by_form": dict(Counter(r["form"] for r in rows)),
        "exact_by_form": dict(Counter(r["form"] for r in exact)),
        "worst": sorted(rows, key=lambda r: -abs(r["delta"]))[:12],
    }
    C.save("a0b_date_validation.json", out)
    for k, v in out.items():
        if not isinstance(v, list):
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
