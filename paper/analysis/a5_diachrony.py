"""A5 — the vocabulary moves.

Eighteenth-century British moral philosophy is usually told as a sequence: the
moral sense of Hutcheson gives way to Hume's sympathy, and sympathy in turn to
the calculating language of utility and interest. The corpus can be asked
whether it shows that, by counting how often each term is used per thousand
passages in each quarter-century.

Rates, not counts: the corpus is wildly uneven across time, and a raw count
would only redraw figure 1. Dates come from A0 -- the id where it carries one,
the title page where it does not -- and every book without a date is excluded
rather than guessed at.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common as C

BIN = 25          # years per bin
MIN_PASSAGES = 400  # a bin thinner than this is too noisy to plot

TERMS = {
    "moral sense": [r"moral sense", r"moral senses"],
    "sympathy": [r"sympath\w*"],
    "benevolence": [r"benevolen\w*"],
    "self-love": [r"self[-\s]?love", r"selfishness"],
    "conscience": [r"conscience\w*"],
    "utility": [r"utility", r"usefulness"],
    "interest": [r"interest", r"interests"],
    "obligation": [r"obligation\w*"],
    "the passions": [r"passions?"],
    "reason": [r"reason", r"reasons", r"reasoning"],
    "virtue": [r"virtue\w*"],
    "duty": [r"dut(?:y|ies)"],
}


def main():
    meta = C.load_meta()
    rec = json.loads((C.DATA / "a0_dates.json").read_text())["recovered"]

    year_of: dict[str, int] = {}
    for m in meta:
        b = m["book_id"]
        if b in year_of:
            continue
        y = C.book_year(b) or (rec.get(b) or {}).get("year")
        if y:
            year_of[b] = y

    pats = {k: re.compile("|".join(rf"(?<![a-z]){p}(?![a-z])" for p in v), re.I)
            for k, v in TERMS.items()}

    per_bin_total = Counter()
    per_bin_term: dict[str, Counter] = {k: Counter() for k in TERMS}
    per_bin_books: dict[int, set] = defaultdict(set)
    for m in meta:
        y = year_of.get(m["book_id"])
        if not y:
            continue
        b = (y // BIN) * BIN
        per_bin_total[b] += 1
        per_bin_books[b].add(m["book_id"])
        t = m.get("raw_text") or ""
        for k, pat in pats.items():
            if pat.search(t):
                per_bin_term[k][b] += 1

    bins = sorted(b for b in per_bin_total if per_bin_total[b] >= MIN_PASSAGES)
    rates = {k: {b: round(1000 * per_bin_term[k][b] / per_bin_total[b], 2) for b in bins}
             for k in TERMS}

    # Where does each term peak, and is it rising or falling across the span?
    profile = {}
    for k, r in rates.items():
        vals = [r[b] for b in bins]
        peak = bins[max(range(len(bins)), key=lambda i: vals[i])]
        first, last = vals[0], vals[-1]
        profile[k] = {
            "peak_bin": peak, "peak_rate": max(vals),
            "first_bin_rate": first, "last_bin_rate": last,
            "change": round(last - first, 2),
            "ratio": round(last / first, 2) if first else None,
        }

    out = {
        "bin_years": BIN,
        "bins": bins,
        "passages_per_bin": {b: per_bin_total[b] for b in bins},
        "books_per_bin": {b: len(per_bin_books[b]) for b in bins},
        "dated_passages": sum(per_bin_total.values()),
        "dated_books": len(year_of),
        "rates_per_1000_passages": rates,
        "profile": profile,
    }
    C.save("a5_diachrony.json", out)

    plt = C.style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(5.8, 2.5), sharex=True)
    focus1 = ["moral sense", "sympathy", "benevolence", "self-love"]
    focus2 = ["virtue", "reason", "duty", "utility"]
    for ax, focus, title in ((ax1, focus1, "the sentimental vocabulary"),
                             (ax2, focus2, "the older vocabulary")):
        for k in focus:
            ax.plot(bins, [rates[k][b] for b in bins], marker="o", ms=3, lw=1.2, label=k)
        ax.set_title(title)
        ax.set_xlabel("quarter-century")
        ax.legend(fontsize=6)
    ax1.set_ylabel("passages per 1,000 mentioning the term")
    fig.savefig(C.FIGS / "diachrony.pdf")
    print(f"  wrote {(C.FIGS / 'diachrony.pdf').relative_to(C.REPO)}")

    print(f"  bins: {bins}  dated passages {out['dated_passages']:,}")
    for k, v in sorted(profile.items(), key=lambda kv: -kv[1]["peak_rate"]):
        print(f"    {k:14} peak {v['peak_bin']} @ {v['peak_rate']:6.2f}   "
              f"{v['first_bin_rate']:6.2f} -> {v['last_bin_rate']:6.2f}")


if __name__ == "__main__":
    main()
