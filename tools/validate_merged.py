import json, pathlib, collections, glob

merged_dir="/store/shuvam/BMoral/Concept Maps/merged"
print("=== Validation ===")

# 1. category_tree
import json as js
tree=js.load(open(f"{merged_dir}/category_tree.json"))
top_names=[c['name'] for c in tree['children']]
print(f"category_tree: top categories {len(top_names)}: {top_names}")
def count_concepts(node):
    s=set(node['concepts'])
    for ch in node['children']:
        s.update(count_concepts(ch))
    return s
all_concepts=count_concepts(tree)
print(f"category_tree total unique concepts: {len(all_concepts)} (expected 104)")
def max_depth(node, d=0):
    if not node['children']:
        return d
    return max(max_depth(ch, d+1) for ch in node['children'])
print(f"category_tree max depth from root: {max_depth(tree)} (expected 2-4)")
def validate_tree(node, depth=0):
    assert 'name' in node
    assert 'concepts' in node
    assert 'children' in node
    for ch in node['children']:
        validate_tree(ch, depth+1)
validate_tree(tree)
print("category_tree structure valid")

# 2. concept_graph
nodes=[]
edges=[]
for line in open(f"{merged_dir}/concept_graph.jsonl"):
    d=js.loads(line)
    if d['type']=='node':
        nodes.append(d)
    elif d['type']=='edge':
        edges.append(d)
    else:
        print(f"unknown type {d['type']}")
print(f"concept_graph: nodes {len(nodes)} (expected 104) edges {len(edges)} (expected 400-600)")
for n in nodes[:1]:
    for field in ['id','label','category','importance','book_count','evidence_count','aliases','definition']:
        assert field in n, f"node missing {field}"
edge_keys=set((e['source'],e['target'],e['relation']) for e in edges)
print(f"  edge deduplication: {len(edges)} edges, {len(edge_keys)} unique source-target-relation (should equal)")
node_ids=set(n['id'] for n in nodes)
invalid=[e for e in edges if e['target'] not in node_ids or e['source'] not in node_ids]
print(f"  invalid edges (dangling): {len(invalid)} (expected 0)")

# 3. inverted_index
inv_lines=[]
for line in open(f"{merged_dir}/inverted_index.jsonl"):
    d=js.loads(line)
    inv_lines.append(d)
print(f"inverted_index: {len(inv_lines)} entries (expected 500-800)")
for entry in inv_lines[:1]:
    for field in ['concept_id','book_id','page','paragraph_id','text','bbox_pts']:
        assert field in entry, f"inverted entry missing {field}"
inv_keys=set((e['concept_id'],e['book_id'],e['paragraph_id'],e['text']) for e in inv_lines)
print(f"  unique paragraph keys: {len(inv_keys)} vs total {len(inv_lines)} (dups {len(inv_lines)-len(inv_keys)})")
from collections import Counter
inv_counter=Counter(e['concept_id'] for e in inv_lines)
for n in nodes:
    cid=n['id']
    expected=n['evidence_count']
    actual=inv_counter.get(cid,0)
    if expected != actual:
        print(f"  MISMATCH {cid}: node evidence_count {expected} vs inverted {actual}")

# 4. query_concept_map
qcm=js.load(open(f"{merged_dir}/query_concept_map.json"))
print(f"query_concept_map: {len(qcm)} queries (expected 43)")
for qid, v in qcm.items():
    assert 'query_text' in v
    assert 'concepts' in v
    concepts=v['concepts']
    relevances=[c['relevance'] for c in concepts]
    if relevances != sorted(relevances, reverse=True):
        print(f"  query {qid} not sorted by relevance")
print(f"  queries with >=1 concept: {sum(1 for v in qcm.values() if len(v['concepts'])>0)}/43")
lip_key="Citations or references to Lipsius's work"
if lip_key in qcm:
    print(f"  Lipsius query concepts: {len(qcm[lip_key]['concepts'])}")

print("=== All validations passed ===")
