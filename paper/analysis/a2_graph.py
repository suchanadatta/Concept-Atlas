"""A2 — the shape of the hand-built concept map.

202 concepts, 1099 typed relations, arranged in a three-level category tree.
This asks what the curators actually built: which relations they reached for,
which concepts hold the thing together, and whether the categories are
self-contained or bridged.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common as C


def main():
    nodes, edges = C.load_graph()
    import networkx as nx

    by_id = {n["id"]: n for n in nodes}
    top_cat = {n["id"]: (n.get("category") or ["?"])[0] for n in nodes}

    G = nx.Graph()
    for n in nodes:
        G.add_node(n["id"], **{k: n.get(k) for k in ("label", "importance", "book_count")})
    for e in edges:
        if e["source"] in by_id and e["target"] in by_id:
            G.add_edge(e["source"], e["target"], relation=e["relation"], strength=e.get("strength", 0))

    rel = Counter(e["relation"] for e in edges)
    deg = dict(G.degree())
    btw = nx.betweenness_centrality(G)

    # A bridge here is an edge whose ends sit in different top-level categories.
    cross = Counter()
    crossing_edges = 0
    for u, v in G.edges():
        a, b = top_cat[u], top_cat[v]
        if a != b:
            crossing_edges += 1
            cross[tuple(sorted((a, b)))] += 1

    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    communities = nx.community.greedy_modularity_communities(G)

    out = {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "density": nx.density(G),
        "components": len(comps),
        "largest_component": len(comps[0]),
        "isolates": sum(1 for n, d in deg.items() if d == 0),
        "mean_degree": sum(deg.values()) / len(deg),
        "median_degree": sorted(deg.values())[len(deg) // 2],
        "max_degree": max(deg.values()),
        "relations": dict(rel.most_common()),
        "relation_share": {k: round(v / len(edges), 4) for k, v in rel.most_common()},
        "degree_assortativity": nx.degree_assortativity_coefficient(G),
        "category_assortativity": nx.attribute_assortativity_coefficient(
            nx.Graph([(u, v) for u, v in G.edges()]), "cat")
        if False else None,
        "top_categories": dict(Counter(top_cat.values()).most_common()),
        "cross_category_edges": crossing_edges,
        "cross_category_share": round(crossing_edges / G.number_of_edges(), 4),
        "top_category_pairs": {f"{a} <-> {b}": n for (a, b), n in cross.most_common(10)},
        "hubs_by_degree": [
            {"id": n, "label": by_id[n]["label"], "degree": d,
             "importance": by_id[n].get("importance"), "category": top_cat[n]}
            for n, d in sorted(deg.items(), key=lambda kv: -kv[1])[:12]],
        "bridges_by_betweenness": [
            {"id": n, "label": by_id[n]["label"], "betweenness": round(b, 4),
             "degree": deg[n], "category": top_cat[n]}
            for n, b in sorted(btw.items(), key=lambda kv: -kv[1])[:12]],
        "communities": len(communities),
        "modularity": nx.community.modularity(G, communities),
        "community_sizes": [len(c) for c in communities][:12],
    }

    # 1099 assertions collapse to far fewer pairs: the map often states more
    # than one relation about the same two concepts. What it states twice is
    # as revealing as what it states once.
    pair_rels: dict[tuple[str, str], list[str]] = defaultdict(list)
    directed = set()
    for e in edges:
        a, b = e["source"], e["target"]
        if a not in by_id or b not in by_id:
            continue
        directed.add((a, b))
        pair_rels[tuple(sorted((a, b)))].append(e["relation"])
    multi = {k: v for k, v in pair_rels.items() if len(v) > 1}
    combos = Counter(" + ".join(sorted(set(v))) for v in multi.values() if len(set(v)) > 1)
    reciprocal = sum(1 for a, b in directed if (b, a) in directed) // 2
    out["assertions"] = len(edges)
    out["distinct_pairs"] = len(pair_rels)
    out["assertions_per_pair"] = round(len(edges) / len(pair_rels), 3)
    out["pairs_with_multiple_assertions"] = len(multi)
    out["pairs_with_conflicting_kinds"] = sum(1 for v in multi.values() if len(set(v)) > 1)
    out["top_relation_combinations"] = dict(combos.most_common(10))
    out["reciprocal_pairs"] = reciprocal

    # Is a concept's curated importance related to how connected it is?
    import numpy as np
    from scipy.stats import spearmanr
    ids = [n["id"] for n in nodes if n.get("importance") is not None]
    r, p = spearmanr([by_id[i]["importance"] for i in ids], [deg[i] for i in ids])
    out["importance_vs_degree_spearman"] = {"rho": round(float(r), 4), "p": float(p), "n": len(ids)}
    ids2 = [n["id"] for n in nodes if n.get("book_count") is not None]
    r2, p2 = spearmanr([by_id[i]["book_count"] for i in ids2], [deg[i] for i in ids2])
    out["bookcount_vs_degree_spearman"] = {"rho": round(float(r2), 4), "p": float(p2), "n": len(ids2)}

    C.save("a2_graph.json", out)

    # ---- figure: which relations the curators used, and the degree profile
    plt = C.style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(5.6, 2.3))
    items = rel.most_common(8)
    ax1.barh([k.replace("_", " ") for k, _ in items][::-1], [v for _, v in items][::-1], height=0.7)
    ax1.set_xlabel("edges")
    ax1.set_title("relation types")
    ax1.grid(axis="y", visible=False)

    ds = sorted(deg.values())
    ax2.hist(ds, bins=range(0, max(ds) + 3, 2), edgecolor="white", linewidth=0.4)
    ax2.set_xlabel("degree")
    ax2.set_ylabel("concepts")
    ax2.set_title("how connected concepts are")
    fig.savefig(C.FIGS / "graph_anatomy.pdf")
    print(f"  wrote {(C.FIGS / 'graph_anatomy.pdf').relative_to(C.REPO)}")

    for k in ("nodes", "edges", "density", "components", "mean_degree", "max_degree",
              "cross_category_share", "communities", "modularity",
              "importance_vs_degree_spearman", "bookcount_vs_degree_spearman"):
        print(f"  {k}: {out[k]}")
    print("  relations:", dict(rel.most_common(6)))
    print("  hubs:", [h["label"] for h in out["hubs_by_degree"][:6]])


if __name__ == "__main__":
    main()
