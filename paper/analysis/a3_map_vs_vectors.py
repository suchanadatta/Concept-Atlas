"""A3 — the curated map against the vector space.

Two descriptions of the same 202 concepts exist in this system and were built
independently. One is the concept map: a person decided that benevolence
supports approbation and that self-love opposes it. The other is the Jasper
index: 90,975 passages in 2048 dimensions, which knows nothing about relations
and only records which words keep company with which.

We give every concept two vectors. Its *definition* vector is the embedding of
the label and the curator's gloss, and is what the live query graph already
uses. Its *usage* vector is new here: the mean embedding of every passage in
the corpus in which one of the concept's aliases actually occurs. The first is
what the map says a concept means; the second is how the concept behaves in the
books.

Then we ask three things. Do concepts the map joins sit closer together than
concepts it does not? Does that hold for relations of opposition, where the
distributional hypothesis is known to fail? And where the two disagree most
sharply, what is being disagreed about?
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common as C
from a_support import build as build_support

MIN_SUPPORT = 20          # passages needed before a usage centroid is trusted
TOP_NEIGHBOURS = 5        # nearest neighbours reported per concept


def alias_pattern(node: dict) -> re.Pattern:
    words = {node["label"].lower()} | {a.lower() for a in (node.get("aliases") or [])}
    words = {w for w in words if len(w) > 3}
    if not words:
        words = {node["label"].lower()}
    alts = "|".join(sorted((re.escape(w) for w in words), key=len, reverse=True))
    return re.compile(rf"(?<![a-z]){alts}(?![a-z])", re.I)


def main():
    import numpy as np

    nodes, edges = C.load_graph()
    by_id = {n["id"]: n for n in nodes}
    meta = C.load_meta()
    emb = np.asarray(C.load_embeddings(), dtype=np.float32)
    emb /= np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9
    # Every passage in this corpus is eighteenth-century moral philosophy, and
    # that shared subject is by far the largest direction in the space: raw
    # cosines between concept centroids all sit above 0.9 and differences that
    # matter are buried under it. Subtracting the corpus mean removes the
    # direction every passage has in common and leaves the ones that separate
    # them. Both are reported below; the centred space is the one read.
    centre = emb.mean(axis=0)
    embc = emb - centre
    embc /= np.linalg.norm(embc, axis=1, keepdims=True) + 1e-9
    texts = [m.get("raw_text") or "" for m in meta]
    print(f"  {len(nodes)} concepts, {len(texts):,} passages, {emb.shape[1]}-d")

    # ---- usage vectors: where does each concept actually appear?
    raw = build_support()          # cached; see a_support.py
    support: dict[str, np.ndarray] = {}
    usage: dict[str, np.ndarray] = {}
    usage_c: dict[str, np.ndarray] = {}
    for n in nodes:
        idx = np.asarray(raw.get(n["id"], ()), dtype=np.int64)
        support[n["id"]] = idx
        if len(idx) >= MIN_SUPPORT:
            v = emb[idx].mean(axis=0)
            usage[n["id"]] = v / (np.linalg.norm(v) + 1e-9)
            w = embc[idx].mean(axis=0)
            usage_c[n["id"]] = w / (np.linalg.norm(w) + 1e-9)
    print(f"  usage vectors for {len(usage)}/{len(nodes)} concepts (>= {MIN_SUPPORT} passages)")

    # ---- definition vectors, as shipped to the live query graph
    dv = np.load(C.REPO / "models" / "jasper_index" / "concepts.npy").astype(np.float32)
    dids = json.loads((C.REPO / "models" / "jasper_index" / "concepts_meta.json").read_text())
    dv /= np.linalg.norm(dv, axis=1, keepdims=True) + 1e-9
    defn = {cid: dv[i] for i, cid in enumerate(dids) if cid in by_id}

    shared = [c for c in by_id if c in usage and c in defn]
    shared.sort()
    U = np.stack([usage_c[c] for c in shared])       # centred: the space we read
    Uraw = np.stack([usage[c] for c in shared])      # uncentred, for comparison
    D = np.stack([defn[c] for c in shared])
    pos = {c: i for i, c in enumerate(shared)}
    simU, simUraw, simD = U @ U.T, Uraw @ Uraw.T, D @ D.T
    print(f"  {len(shared)} concepts have both vectors")

    # ---- the map, as pairs
    pair_rel: dict[tuple[str, str], set[str]] = defaultdict(set)
    for e in edges:
        a, b = e["source"], e["target"]
        if a in pos and b in pos and a != b:
            pair_rel[tuple(sorted((a, b)))].add(e["relation"])

    iu = np.triu_indices(len(shared), k=1)
    all_pairs = [(shared[i], shared[j]) for i, j in zip(*iu)]
    linked = np.array([tuple(sorted(p)) in pair_rel for p in all_pairs])
    cu, craw, cd = simU[iu], simUraw[iu], simD[iu]

    def stats(mask, vals):
        v = vals[mask]
        return {"n": int(mask.sum()), "mean": round(float(v.mean()), 4),
                "median": round(float(np.median(v)), 4), "sd": round(float(v.std()), 4)}

    from scipy.stats import mannwhitneyu, spearmanr
    uU = mannwhitneyu(cu[linked], cu[~linked], alternative="greater")
    uD = mannwhitneyu(cd[linked], cd[~linked], alternative="greater")
    rho_ud = spearmanr(cu, cd)

    out = {
        "concepts_with_both_vectors": len(shared),
        "min_support": MIN_SUPPORT,
        "pairs_compared": len(all_pairs),
        "linked_pairs": int(linked.sum()),
        "usage": {"linked": stats(linked, cu), "unlinked": stats(~linked, cu),
                  "mannwhitney_p": float(uU.pvalue)},
        "usage_uncentred": {"linked": stats(linked, craw), "unlinked": stats(~linked, craw)},
        "definition": {"linked": stats(linked, cd), "unlinked": stats(~linked, cd),
                       "mannwhitney_p": float(uD.pvalue)},
        "usage_vs_definition_spearman": {"rho": round(float(rho_ud.statistic), 4),
                                         "p": float(rho_ud.pvalue)},
    }

    # ---- does agreement depend on what kind of relation is asserted?
    per_rel = {}
    for rel in sorted({r for rs in pair_rel.values() for r in rs}):
        vals_u, vals_d = [], []
        for (a, b), rs in pair_rel.items():
            if rel in rs:
                vals_u.append(simU[pos[a], pos[b]]); vals_d.append(simD[pos[a], pos[b]])
        if len(vals_u) >= 10:
            per_rel[rel] = {
                "n": len(vals_u),
                "usage_mean": round(float(np.mean(vals_u)), 4),
                "usage_sd": round(float(np.std(vals_u)), 4),
                "definition_mean": round(float(np.mean(vals_d)), 4),
                "usage_vs_baseline": round(float(np.mean(vals_u) - cu[~linked].mean()), 4),
                "z_vs_unlinked": round(float((np.mean(vals_u) - cu[~linked].mean())
                                             / (cu[~linked].std() + 1e-9)), 3),
            }
    out["by_relation"] = dict(sorted(per_rel.items(), key=lambda kv: -kv[1]["usage_mean"]))

    # ---- where the two disagree
    neigh_missing, weakest = [], []
    for i, a in enumerate(shared):
        order = np.argsort(-simU[i])
        for j in order[1:TOP_NEIGHBOURS + 1]:
            b = shared[j]
            if tuple(sorted((a, b))) not in pair_rel:
                neigh_missing.append({"a": by_id[a]["label"], "b": by_id[b]["label"],
                                      "usage_cos": round(float(simU[i, j]), 4),
                                      "definition_cos": round(float(simD[i, j]), 4),
                                      "support_a": int(len(support[a])), "support_b": int(len(support[b]))})
    seen = set(); dedup = []
    for r in sorted(neigh_missing, key=lambda r: -r["usage_cos"]):
        k = tuple(sorted((r["a"], r["b"])))
        if k not in seen:
            seen.add(k); dedup.append(r)
    out["nearest_but_unlinked"] = dedup[:25]

    for (a, b), rs in pair_rel.items():
        weakest.append({"a": by_id[a]["label"], "b": by_id[b]["label"],
                        "relations": sorted(rs),
                        "usage_cos": round(float(simU[pos[a], pos[b]]), 4),
                        "definition_cos": round(float(simD[pos[a], pos[b]]), 4)})
    out["linked_but_distant"] = sorted(weakest, key=lambda r: r["usage_cos"])[:25]

    out["support_profile"] = {
        "median_passages_per_concept": int(np.median([len(v) for v in support.values()])),
        "largest": sorted(((by_id[c]["label"], int(len(v))) for c, v in support.items()),
                          key=lambda kv: -kv[1])[:10],
        "below_threshold": sorted(by_id[c]["label"] for c, v in support.items() if len(v) < MIN_SUPPORT),
    }
    C.save("a3_map_vs_vectors.json", out)

    # ---- figure
    plt = C.style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(5.6, 2.4))
    bins = np.linspace(min(cu.min(), 0.0), 1.0, 60)
    ax1.hist(cu[~linked], bins=bins, density=True, alpha=0.55, label="not joined in the map")
    ax1.hist(cu[linked], bins=bins, density=True, alpha=0.75, label="joined in the map")
    ax1.set_xlabel("cosine between usage vectors")
    ax1.set_ylabel("density")
    ax1.legend(loc="upper left")
    ax1.set_title("map adjacency vs. corpus geometry")

    rels = list(out["by_relation"])
    xs = [out["by_relation"][r]["usage_mean"] for r in rels]
    ax2.barh([r.replace("_", " ") for r in rels][::-1], xs[::-1], height=0.7)
    ax2.axvline(cu[~linked].mean(), ls="--", lw=0.9, color="0.35")
    ax2.annotate("unrelated pairs", xy=(cu[~linked].mean(), -0.4), fontsize=6,
                 ha="center", color="0.35")
    ax2.set_xlabel("mean cosine (usage)")
    ax2.set_title("by asserted relation")
    ax2.grid(axis="y", visible=False)
    fig.savefig(C.FIGS / "map_vs_vectors.pdf")
    print(f"  wrote {(C.FIGS / 'map_vs_vectors.pdf').relative_to(C.REPO)}")

    print(f"  linked mean {out['usage']['linked']['mean']} vs unlinked {out['usage']['unlinked']['mean']}")
    print(f"  usage~definition rho {out['usage_vs_definition_spearman']['rho']}")
    for r, v in out["by_relation"].items():
        print(f"    {r:16} n={v['n']:4} usage {v['usage_mean']:.3f}  (+{v['usage_vs_baseline']:.3f})")


if __name__ == "__main__":
    main()
