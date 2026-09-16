"""A6 — who wrote what, and what the difference looks like.

The author registry records a sex for each author, supplied by the project
lead, and the corpus is deliberately not the usual canon: forty of its books
are by women, which is a far larger share than a reading list of eighteenth-
century moral philosophy normally carries.

This asks a narrow, answerable question -- which concepts are used at
noticeably different rates in the two sets of texts -- and nothing wider. The
comparison is between two collections of books, not between two kinds of mind;
the sets differ in date, genre and size as well as in authorship, and those
confounds are measured here rather than waved at.
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common as C
from a_support import build as build_support

MIN_TOTAL = 60      # a concept seen fewer times than this is not worth ranking


def alias_pattern(node: dict) -> re.Pattern:
    words = {node["label"].lower()} | {a.lower() for a in (node.get("aliases") or [])}
    words = {w for w in words if len(w) > 3} or {node["label"].lower()}
    alts = "|".join(sorted((re.escape(w) for w in words), key=len, reverse=True))
    return re.compile(rf"(?<![a-z]){alts}(?![a-z])", re.I)


def main():
    nodes, _ = C.load_graph()
    meta = C.load_meta()
    authors = C.get(f"{C.UI}/book/api/authors")
    rec = json.loads((C.DATA / "a0_dates.json").read_text())["recovered"]

    sex_of_book: dict[str, str] = {}
    author_of_book: dict[str, str] = {}
    for a in authors["authors"]:
        for b in a.get("book_ids") or []:
            sex_of_book[b] = (a.get("sex") or "?").upper()
            author_of_book[b] = a["name"]

    def group(b: str) -> str | None:
        s = sex_of_book.get(b)
        if s == "M":
            return "men"
        if s == "F":
            return "women"
        return None  # 'F?', joint attributions and unmatched books sit out

    rows = [(m, group(m["book_id"])) for m in meta]
    texts = {"men": [], "women": []}
    for m, g in rows:
        if g:
            texts[g].append(m.get("raw_text") or "")
    n_men, n_women = len(texts["men"]), len(texts["women"])
    print(f"  passages: men {n_men:,}  women {n_women:,}")

    # ---- confounds, stated before the result
    def span(g):
        ys = []
        for m, gg in rows:
            if gg != g:
                continue
            b = m["book_id"]
            y = C.book_year(b) or (rec.get(b) or {}).get("year")
            if y:
                ys.append(y)
        ys.sort()
        return {"dated_passages": len(ys), "median_year": ys[len(ys) // 2] if ys else None,
                "p10": ys[len(ys) // 10] if ys else None,
                "p90": ys[9 * len(ys) // 10] if ys else None}

    confounds = {
        "men": {"books": len({m["book_id"] for m, g in rows if g == "men"}),
                "authors": len({author_of_book[m["book_id"]] for m, g in rows if g == "men"}),
                "passages": n_men, **span("men")},
        "women": {"books": len({m["book_id"] for m, g in rows if g == "women"}),
                  "authors": len({author_of_book[m["book_id"]] for m, g in rows if g == "women"}),
                  "passages": n_women, **span("women")},
        "excluded": {"passages": sum(1 for _, g in rows if g is None),
                     "reason": "uncertain or joint attribution, or author not in the registry"},
    }

    # ---- concept rates, off the cached concept-to-passage index
    support = build_support()
    grp = [group(m["book_id"]) for m in meta]
    out_rows = []
    for n in nodes:
        idx = support.get(n["id"], ())
        cm = cw = 0
        bm_set, bw_set = set(), set()
        for i in idx:
            g = grp[i]
            if g == "men":
                cm += 1; bm_set.add(meta[i]["book_id"])
            elif g == "women":
                cw += 1; bw_set.add(meta[i]["book_id"])
        if cm + cw < MIN_TOTAL:
            continue
        rm, rw = 1000 * cm / n_men, 1000 * cw / n_women
        # log2 ratio with add-one smoothing, so a zero on one side is finite
        lr = math.log2(((cw + 1) / (n_women + 1)) / ((cm + 1) / (n_men + 1)))
        bm, bw = len(bm_set), len(bw_set)
        out_rows.append({
            "concept": n["label"], "id": n["id"],
            "category": (n.get("category") or ["?"])[0],
            "men_per_1000": round(rm, 2), "women_per_1000": round(rw, 2),
            "log2_ratio": round(lr, 3),
            "men_hits": cm, "women_hits": cw,
            "men_books": bm, "women_books": bw,
        })

    out_rows.sort(key=lambda r: -r["log2_ratio"])
    # Only report a lean that shows up across several books on the leaning side.
    robust = [r for r in out_rows if (r["women_books"] >= 5 if r["log2_ratio"] > 0 else r["men_books"] >= 5)]

    out = {
        "confounds": confounds,
        "concepts_ranked": len(out_rows),
        "min_total_hits": MIN_TOTAL,
        "women_lean": robust[:15],
        "men_lean": robust[-15:][::-1],
        "all": out_rows,
    }
    C.save("a6_authorship.json", out)

    plt = C.style()
    top = robust[:12] + robust[-12:]
    labels = [r["concept"] for r in top]
    vals = [r["log2_ratio"] for r in top]
    fig, ax = plt.subplots(figsize=(5.4, 3.4))
    ax.barh(labels[::-1], vals[::-1], height=0.74)
    ax.axvline(0, lw=0.8, color="0.3")
    ax.set_xlabel("log$_2$ rate ratio  (left: more in books by men — right: more in books by women)")
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", labelsize=6)
    fig.savefig(C.FIGS / "authorship.pdf")
    print(f"  wrote {(C.FIGS / 'authorship.pdf').relative_to(C.REPO)}")

    print("  confounds:", json.dumps(confounds, indent=None)[:300])
    print("  women lean:", [(r["concept"], r["log2_ratio"]) for r in out["women_lean"][:6]])
    print("  men lean:  ", [(r["concept"], r["log2_ratio"]) for r in out["men_lean"][:6]])


if __name__ == "__main__":
    main()
