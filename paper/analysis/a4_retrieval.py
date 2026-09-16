"""A4 — where lexical and semantic retrieval part company.

The site offers both: BM25 over the OCR text, and cosine over Jasper vectors.
For most queries they broadly agree. The interesting queries are the ones where
they do not, because a term whose semantic neighbourhood is nowhere near its
lexical matches is a term that eighteenth-century writers used in a way the
word alone does not reveal.

Both halves are asked of the running service -- the same endpoints the website
calls -- so this measures the deployed system, not a reimplementation of it.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common as C

K = 20

QUERIES = [
    "moral sense", "benevolence", "sympathy", "self-love", "conscience",
    "virtue", "utility", "obligation", "the passions", "reason",
    "the impartial spectator", "natural affection", "divine law", "happiness",
    "interest", "duty", "pleasure", "the will", "habit", "education",
    "friendship", "liberty", "custom", "beauty", "justice",
    "the deity", "human nature", "public good", "private vice", "approbation",
]


def key(hit: dict) -> tuple:
    """Compare at page level.

    The two indexes are not built to the same unit: BM25 returns a page with a
    match count, Jasper returns an individual text block within a page. A page
    is the finest thing both can name, so that is what is compared -- which is
    also what a reader follows when they click a result.
    """
    page = hit.get("page")
    try:
        page = int(page)
    except (TypeError, ValueError):
        pass
    return (hit.get("book_id"), page)


def main():
    rows = []
    for q in QUERIES:
        try:
            lex = C.post("/bm25", {"query": q, "k": K})
            sem = C.post("/semantic", {"query": q, "k": K})
        except Exception as e:
            print(f"  !! {q}: {e}")
            continue
        L = [key(h) for h in lex.get("results", [])][:K]
        S = [key(h) for h in sem.get("results", [])][:K]
        sl, ss = set(L), set(S)
        inter = sl & ss
        jac = len(inter) / len(sl | ss) if (sl | ss) else 0.0
        lb = {h.get("book_id") for h in lex.get("results", [])}
        sb = {h.get("book_id") for h in sem.get("results", [])}
        rows.append({
            "query": q,
            "lexical_hits": len(L), "semantic_hits": len(S),
            "overlap": len(inter),
            "jaccard": round(jac, 4),
            "books_lexical": len(lb), "books_semantic": len(sb),
            "book_jaccard": round(len(lb & sb) / len(lb | sb), 4) if (lb | sb) else 0.0,
        })
        print(f"  {q:26} overlap {len(inter):2}/{K}  J={jac:.3f}  books {len(lb)}/{len(sb)}")
        time.sleep(0.05)

    rows.sort(key=lambda r: r["jaccard"])
    import statistics as st
    out = {
        "k": K,
        "queries": len(rows),
        "mean_jaccard": round(st.mean(r["jaccard"] for r in rows), 4),
        "median_jaccard": round(st.median(r["jaccard"] for r in rows), 4),
        "mean_book_jaccard": round(st.mean(r["book_jaccard"] for r in rows), 4),
        "zero_overlap": [r["query"] for r in rows if r["overlap"] == 0],
        "most_divergent": rows[:10],
        "most_agreed": rows[-10:][::-1],
        "all": rows,
    }
    C.save("a4_retrieval.json", out)

    plt = C.style()
    fig, ax = plt.subplots(figsize=(5.6, 3.0))
    labels = [r["query"] for r in rows]
    ax.barh(labels[::-1], [r["jaccard"] for r in rows][::-1], height=0.72)
    ax.axvline(out["mean_jaccard"], ls="--", lw=0.9, color="0.35")
    ax.set_xlabel(f"Jaccard overlap of top-{K} passages (BM25 vs. Jasper)")
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", labelsize=6)
    fig.savefig(C.FIGS / "retrieval_divergence.pdf")
    print(f"  wrote {(C.FIGS / 'retrieval_divergence.pdf').relative_to(C.REPO)}")
    print(f"  mean J={out['mean_jaccard']}  median={out['median_jaccard']}  zero-overlap={out['zero_overlap']}")


if __name__ == "__main__":
    main()
