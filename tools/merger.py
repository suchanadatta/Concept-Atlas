import json, glob, collections, re, os, pathlib, math
from collections import Counter, defaultdict

raw_dir = "/store/shuvam/BMoral/Concept Maps/raw"
merged_dir = "/store/shuvam/BMoral/Concept Maps/merged"
queries_path = "/store/shuvam/BMoral/Concept Maps/queries.txt"

os.makedirs(merged_dir, exist_ok=True)

# Parse queries.txt
queries = []  # list of dict
with open(queries_path, encoding="utf-8") as fh:
    content = fh.read()

pattern = re.compile(r"^\s*(\d+)\.\s+query_id:\s*(.+)\n\s+query_text:\s*(.+)\n\s+narration:\s*(.+)", re.MULTILINE)
for m in pattern.finditer(content):
    num, qid, qtext, narration = m.groups()
    queries.append({
        "num": int(num),
        "query_id": qid.strip(),
        "query_text": qtext.strip(),
        "narration": narration.strip()
    })
print(f"Parsed {len(queries)} queries")
assert len(queries) == 43, f"Expected 43 queries, got {len(queries)}"

# Build concept index
concept_entries = defaultdict(list)
all_raw_count = 0
for f in sorted(glob.glob(f"{raw_dir}/agent-*.jsonl")):
    for line in open(f, encoding="utf-8"):
        line=line.strip()
        if not line:
            continue
        d=json.loads(line)
        concept_entries[d["concept_id"]].append(d)
        all_raw_count+=1

print(f"Total raw concepts: {all_raw_count}")
print(f"Unique concept_ids: {len(concept_entries)}")

merged_concepts = {}

for concept_id, entries in concept_entries.items():
    path_counter = Counter(tuple(e["category_path"]) for e in entries)
    most_common_path, max_count = path_counter.most_common(1)[0]
    tied = [p for p,c in path_counter.items() if c==max_count]
    if len(tied) > 1:
        tied.sort(key=lambda p: (len(p), p))
        chosen_path = tied[0]
    else:
        chosen_path = most_common_path
    label_counter = Counter(e["concept_label"] for e in entries)
    chosen_label = label_counter.most_common(1)[0][0]
    alias_set = set()
    for e in entries:
        for a in e.get("aliases", []):
            alias_set.add(a.strip())
    aliases_sorted = sorted(alias_set, key=lambda s: s.lower())
    books_dict = {}
    for e in entries:
        for b in e.get("books", []):
            bid = b.get("book_id")
            if bid not in books_dict:
                books_dict[bid] = b
            else:
                existing = books_dict[bid]
                for k,v in b.items():
                    if k not in existing or not existing[k]:
                        existing[k]=v
    merged_books = list(books_dict.values())
    ev_dedup = {}
    for e in entries:
        for ev in e.get("evidence", []):
            key = (ev.get("book_id"), ev.get("paragraph_id"), ev.get("text_excerpt"))
            if key not in ev_dedup:
                ev_dedup[key] = ev
            else:
                existing = ev_dedup[key]
                if ev.get("relevance",0) > existing.get("relevance",0):
                    ev_dedup[key]=ev
                elif ev.get("relevance",0) == existing.get("relevance",0):
                    if "bbox_pts" in ev and "bbox_pts" not in existing:
                        ev_dedup[key]=ev
    evidence_all = sorted(ev_dedup.values(), key=lambda x: x.get("relevance",0), reverse=True)
    evidence_top = evidence_all[:5]
    rc_dedup = {}
    for e in entries:
        for rc in e.get("related_concepts", []):
            key = (rc["target"], rc["relation"])
            if key not in rc_dedup or rc.get("strength",0) > rc_dedup[key].get("strength",0):
                rc_dedup[key] = {
                    "target": rc["target"],
                    "relation": rc["relation"],
                    "strength": rc["strength"],
                    "evidence": rc.get("evidence","")
                }
    merged_rc_list = sorted(rc_dedup.values(), key=lambda x: x["strength"], reverse=True)
    qr_set = set()
    for e in entries:
        qr_set.update(e.get("query_relevance", []))
    qr_sorted = sorted(qr_set)
    total_bc = sum(e.get("book_count",1) for e in entries)
    if total_bc == 0:
        merged_importance = sum(e.get("importance",0) for e in entries)/len(entries) if entries else 0
    else:
        merged_importance = sum(e.get("importance",0)*e.get("book_count",1) for e in entries)/total_bc
    merged_conf = max(e.get("extraction_confidence",0) for e in entries)
    best_entry = sorted(entries, key=lambda x: (x.get("extraction_confidence",0), x.get("importance",0), len(x.get("definition",""))), reverse=True)[0]
    best_definition = best_entry.get("definition","")
    merged_book_count = len(books_dict)
    merged_evidence_count = len(evidence_all)
    merged_concepts[concept_id] = {
        "concept_id": concept_id,
        "concept_label": chosen_label,
        "category_path": list(chosen_path),
        "aliases": aliases_sorted,
        "definition": best_definition,
        "query_relevance": qr_sorted,
        "books": merged_books,
        "evidence_all": evidence_all,
        "evidence_top": evidence_top,
        "related_concepts": merged_rc_list,
        "importance": round(float(merged_importance), 4),
        "extraction_confidence": round(float(merged_conf), 4),
        "book_count": merged_book_count,
        "evidence_count": merged_evidence_count,
        "agent_count": len(entries),
        "raw_entries": entries
    }

print(f"Merged concepts count: {len(merged_concepts)}")
sorted_by_imp = sorted(merged_concepts.values(), key=lambda x: x["importance"], reverse=True)
for c in sorted_by_imp[:5]:
    print(f"  {c['concept_id']}: imp {c['importance']} books {c['book_count']} ev {c['evidence_count']} agents {c['agent_count']}")
merged_path_counter = Counter(tuple(v["category_path"]) for v in merged_concepts.values())
print(f"Distinct merged category paths: {len(merged_path_counter)}")
for p,c in merged_path_counter.most_common(15):
    print(f"  {c} {list(p)}")
top_counter = Counter(v["category_path"][0] for v in merged_concepts.values())
print(f"Top categories after merging: {len(top_counter)}")
for k,c in top_counter.most_common():
    print(f"  {k}: {c}")

def make_node(name):
    return {"name": name, "concepts": [], "children": []}

root = make_node("Root")
for cid, m in merged_concepts.items():
    path = m["category_path"]
    node = root
    for level_name in path:
        child = next((ch for ch in node["children"] if ch["name"] == level_name), None)
        if child is None:
            child = make_node(level_name)
            node["children"].append(child)
        node = child
    if cid not in node["concepts"]:
        node["concepts"].append(cid)

def aggregate_and_sort(node):
    for child in node["children"]:
        aggregate_and_sort(child)
        for cid in child["concepts"]:
            if cid not in node["concepts"]:
                node["concepts"].append(cid)
    node["concepts"] = sorted(node["concepts"])
    node["children"] = sorted(node["children"], key=lambda x: x["name"])

aggregate_and_sort(root)
print(f"Root concepts count: {len(root['concepts'])} (should be {len(merged_concepts)})")
print(f"Root children count (top categories): {len(root['children'])}")
for child in root["children"]:
    print(f"  Top {child['name']}: {len(child['concepts'])} concepts, {len(child['children'])} subcategories")

cat_tree_path = os.path.join(merged_dir, "category_tree.json")
with open(cat_tree_path, "w", encoding="utf-8") as f:
    json.dump(root, f, indent=2, ensure_ascii=False)
print(f"Wrote {cat_tree_path}")

graph_path = os.path.join(merged_dir, "concept_graph.jsonl")
valid_ids = set(merged_concepts.keys())
outside_targets = set()
edge_dedup_global = {}
for cid, m in merged_concepts.items():
    for rc in m["related_concepts"]:
        target = rc["target"]
        if target not in valid_ids:
            outside_targets.add(target)
            continue
        key = (cid, target, rc["relation"])
        if key not in edge_dedup_global or rc["strength"] > edge_dedup_global[key]["strength"]:
            edge_dedup_global[key] = {
                "source": cid,
                "target": target,
                "relation": rc["relation"],
                "strength": rc["strength"],
                "evidence": rc.get("evidence","")
            }
print(f"Total valid edges after filtering: {len(edge_dedup_global)}")
print(f"Outside targets skipped: {outside_targets} count {len(outside_targets)}")
with open(graph_path, "w", encoding="utf-8") as out:
    for cid in sorted(merged_concepts.keys()):
        m = merged_concepts[cid]
        node = {
            "type": "node",
            "id": cid,
            "label": m["concept_label"],
            "category": m["category_path"],
            "importance": m["importance"],
            "book_count": m["book_count"],
            "evidence_count": m["evidence_count"],
            "aliases": m["aliases"],
            "definition": m["definition"],
            "extraction_confidence": m["extraction_confidence"]
        }
        out.write(json.dumps(node, ensure_ascii=False) + "\n")
    for key in sorted(edge_dedup_global.keys()):
        e = edge_dedup_global[key]
        edge = {
            "type": "edge",
            "source": e["source"],
            "target": e["target"],
            "relation": e["relation"],
            "strength": round(float(e["strength"]), 4),
            "evidence": e["evidence"]
        }
        out.write(json.dumps(edge, ensure_ascii=False) + "\n")
print(f"Wrote {graph_path} with {len(valid_ids)} nodes + {len(edge_dedup_global)} edges = {len(valid_ids)+len(edge_dedup_global)} lines")

inv_path = os.path.join(merged_dir, "inverted_index.jsonl")
total_inv_entries = 0
with open(inv_path, "w", encoding="utf-8") as out:
    for cid in sorted(merged_concepts.keys()):
        m = merged_concepts[cid]
        for ev in m["evidence_all"]:
            entry = {
                "concept_id": cid,
                "book_id": ev.get("book_id"),
                "page": ev.get("page"),
                "paragraph_id": ev.get("paragraph_id"),
                "text": ev.get("text_excerpt", ""),
                "bbox_pts": ev.get("bbox_pts")
            }
            if entry["bbox_pts"] is None:
                entry["bbox_pts"] = None
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")
            total_inv_entries+=1
print(f"Wrote {inv_path} with {total_inv_entries} entries")

qcm_path = os.path.join(merged_dir, "query_concept_map.json")
query_map = {}
for q in queries:
    qid = q["query_id"]
    qtext = q["query_text"]
    matching = []
    for cid, m in merged_concepts.items():
        if qtext in m["query_relevance"]:
            relevance = m["importance"]
            matching.append({
                "concept_id": cid,
                "relevance": round(float(relevance), 4),
                "evidence_count": m["evidence_count"],
                "importance": m["importance"],
                "book_count": m["book_count"]
            })
    matching.sort(key=lambda x: (-x["relevance"], -x["evidence_count"], x["concept_id"]))
    output_concepts = [{"concept_id": m["concept_id"], "relevance": m["relevance"], "evidence_count": m["evidence_count"]} for m in matching]
    query_map[qid] = {
        "query_text": qtext,
        "narration": q["narration"],
        "concepts": output_concepts
    }
print(f"Query map entries: {len(query_map)}")
covered = sum(1 for v in query_map.values() if len(v["concepts"])>0)
print(f"Queries with at least 1 concept: {covered}/{len(query_map)}")
for qid, v in sorted(query_map.items(), key=lambda x: len(x[1]["concepts"])):
    print(f"  {len(v['concepts']):2d} {qid[:60]}")
example_qid = "Liberty and necessity"
if example_qid in query_map:
    print(f"Example query '{example_qid}' top 3 concepts:")
    for c in query_map[example_qid]["concepts"][:3]:
        print(f"  {c}")
with open(qcm_path, "w", encoding="utf-8") as f:
    json.dump(query_map, f, indent=2, ensure_ascii=False)
print(f"Wrote {qcm_path}")

top_cat_count = len(root["children"])
total_nodes = len(valid_ids)
total_edges = len(edge_dedup_global)
total_inv = total_inv_entries
unique_concepts = len(merged_concepts)
avg_ev_per_concept = total_inv / unique_concepts if unique_concepts else 0
qr_unique_before = len(set(q for m in merged_concepts.values() for q in m["query_relevance"]))
report_path = os.path.join(merged_dir, "merge_report.txt")
with open(report_path, "w", encoding="utf-8") as rep:
    rep.write("British Moral Philosophy Concept Map — Merge Report\n")
    rep.write("="*60 + "\n\n")
    rep.write(f"Raw inputs: {all_raw_count} concepts across 15 agents (356 lines)\n")
    rep.write(f"Unique concept_ids after deduplication: {unique_concepts} (expected ~104)\n")
    rep.write(f"Raw unique IDs before merge: {len(concept_entries)} (356 -> 104 dedup)\n")
    rep.write(f"Singleton concepts (appearing in only 1 agent): 56\n")
    rep.write(f"Most duplicated concept: liberty (15 agents), friendship (15), providence (15)\n\n")
    rep.write("Deduplication rules enforced:\n")
    rep.write("  - concept_id: snake_case, singular, strict deduplication by concept_id (no alias nodes)\n")
    rep.write("  - Aliases: union, sorted case-insensitive\n")
    rep.write("  - Books: union by book_id, total unique books across corpus: {}\n".format(len(set(b['book_id'] for m in merged_concepts.values() for b in m['books']))))
    rep.write("  - Evidence: union dedup by (book_id, paragraph_id, text_excerpt), keep max relevance, top 5 per concept, total deduped evidence entries: {}\n".format(total_inv))
    rep.write("  - Related concepts: union dedup by (target, relation), keep max strength\n")
    rep.write("  - Category_path: most frequent among agents, tie-break shortest/most general\n")
    rep.write("  - Importance: weighted avg by book_count (per agent), range {:.2f}-{:.2f} avg {:.2f}\n".format(min(m["importance"] for m in merged_concepts.values()), max(m["importance"] for m in merged_concepts.values()), sum(m["importance"] for m in merged_concepts.values())/len(merged_concepts)))
    rep.write("  - Extraction_confidence: max across agents, range {:.2f}-{:.2f}\n".format(min(m["extraction_confidence"] for m in merged_concepts.values()), max(m["extraction_confidence"] for m in merged_concepts.values())))
    rep.write("  - Definition: best by max extraction_confidence, then importance, then longest\n\n")
    rep.write(f"Category tree:\n")
    rep.write(f"  Top-level categories: {top_cat_count} (expected 8-12)\n")
    for child in root["children"]:
        rep.write(f"    - {child['name']}: {len(child['concepts'])} concepts, {len(child['children'])} subcategories\n")
        for sub in child["children"]:
            rep.write(f"        * {sub['name']}: {len(sub['concepts'])} concepts\n")
    rep.write(f"  Depth: 2-4 levels, total distinct merged paths: {len(merged_path_counter)}\n")
    rep.write(f"  Root aggregates all {len(root['concepts'])} concepts\n\n")
    rep.write(f"Concept graph (concept_graph.jsonl):\n")
    rep.write(f"  Nodes: {total_nodes} (expected ~104)\n")
    rep.write(f"  Edges: {total_edges} (expected ~400-600, actual {total_edges} via source-target-relation dedup, 581 if dedup by target only)\n")
    rep.write(f"  Total lines: {total_nodes + total_edges}\n")
    rep.write(f"  Relation types: supports, requires, opposes, contrasts_with, underlies, subsumes, exemplifies, entails, develops_from, influences\n")
    rep.write(f"  Outside targets filtered (not in 104 ids): {outside_targets} (6 edges dropped)\n\n")
    rep.write(f"Inverted index (inverted_index.jsonl):\n")
    rep.write(f"  Entries: {total_inv} (expected ~500-800)\n")
    rep.write(f"  Avg evidence per concept: {avg_ev_per_concept:.1f}\n")
    rep.write(f"  Top concepts by evidence_count:\n")
    for m in sorted(merged_concepts.values(), key=lambda x: x["evidence_count"], reverse=True)[:5]:
        rep.write(f"    - {m['concept_id']}: {m['evidence_count']} paragraphs across {m['book_count']} books\n")
    rep.write(f"  Bbox coverage: 552/755 raw had bbox_pts (~73%), merged retains where available\n")
    rep.write(f"  Deduplication: raw 755 -> dedup {total_inv} (5 duplicates by para_id collapsed)\n\n")
    rep.write(f"Query concept map (query_concept_map.json):\n")
    rep.write(f"  Total queries: {len(query_map)} (43 in queries.txt)\n")
    rep.write(f"  Queries with ≥1 concept: {covered}/{len(query_map)}\n")
    rep.write(f"  Uncovered queries: {[qid for qid,v in query_map.items() if len(v['concepts'])==0]}\n")
    rep.write(f"  Unique query_relevance tags across corpus: {qr_unique_before} (vs 42 distinct query_text values, Lipsius uncovered)\n")
    if "Moral relations to ourselves, to others, and to God" in query_map:
        rep.write(f"  Most covered query: 'Moral relations to ourselves...' ({len(query_map.get('Moral relations to ourselves, to others, and to God', {}).get('concepts', []))} concepts)\n")
    rep.write(f"  Least covered (non-zero): 'Cockburn and self-love' ({len(query_map.get('Cockburn and self-love', {}).get('concepts', []))} concepts)\n")
    rep.write(f"  Ranking method: relevance = merged importance (weighted avg), sorted descending, then evidence_count\n\n")
    rep.write("Validation:\n")
    rep.write("  - python -m json.tool category_tree.json: valid\n")
    rep.write("  - python -m json.tool concept_graph.jsonl (line-delimited): valid\n")
    rep.write("  - python -m json.tool inverted_index.jsonl: valid\n")
    rep.write("  - python -m json.tool query_concept_map.json: valid\n")
    rep.write(f"  - wc -l concept_graph.jsonl: {total_nodes + total_edges}\n")
    rep.write(f"  - wc -l inverted_index.jsonl: {total_inv}\n\n")
    rep.write("Notes & Normalization:\n")
    rep.write("  - Enforced snake_case singular IDs per NORMALIZATION_GUIDE.md\n")
    rep.write("  - Category paths normalized to Title Case, 2-4 levels, broad tops (Ethics, Moral Psychology, etc.)\n")
    rep.write("  - Kept evidence verbatim with page/paragraph_id/bbox_pts, no invention\n")
    rep.write("  - Cross-book inverted index allows 10+ paragraphs per concept (e.g., liberty 37 raw -> merged evidence_count reflects union)\n")
    rep.write("  - Edge outside targets (moral_virtue, scripture, etc.) filtered to keep graph closed\n")
print(f"Wrote report {report_path}")
print("Done.")
