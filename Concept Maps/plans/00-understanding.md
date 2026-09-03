# 00 — Understanding

## Task
Build a **graph view UI** for the Concept Maps corpus and **host it on the intranet**.

## Data (verified this session)
Source of truth: `Concept Maps/final/` (double-audited, Sep 1 21:34 — newest; supersedes `merged/`).

| File | Content | Verified shape |
|---|---|---|
| `concept_graph.jsonl` | 1310 lines = **203 nodes + 1107 edges** | node: `{type,id,label,category[],importance,book_count,evidence_count,aliases[],definition}`; edge: `{type,source,target,relation,strength}` |
| `category_tree.json` | 9 top cats (Aesthetics, Epistemology, Ethics, Intellectual History, Metaphysics, Moral Philosophy, Moral Psychology, Political Philosophy, Theology), depth 2–3, concepts at leaves | `{name,concepts[],children[]}` |
| `inverted_index.jsonl` | 2275 paragraph entries | `{concept_id,book_id,page,paragraph_id,text,bbox_pts}` |
| `query_concept_map.json` | 43 queries → ranked concepts | `{qid: {query_text, concepts:[{concept_id,relevance,evidence_count}]}}` |

Edge relations (counts): supports 370, requires 278, opposes 121, contrasts_with 108, underlies 88, entails 43, exemplifies 42, subsumes 38, develops_from 16, influences 3.

## Environment (verified)
- Host `iierserver`, intranet IP **10.20.113.88** (+ docker bridges 172.17/18.0.1)
- Ports busy: 80 (Vite dev), 8080, 5000, 5173, 8123, 5318, 4174, 8765… **Free candidates: 8788, 8899, 7331, 9090**
- node v24.18.0, python 3.10.12 present; **no sudo** (no system systemd units, no firewall changes)
- Internet reachable from host (jsdelivr 200 OK) — vendoring libs locally so intranet clients need no internet

## Success criteria
1. UI loads at `http://10.20.113.88:<port>/` from the intranet (bind 0.0.0.0, verified via curl on that IP)
2. Force-directed graph of all 203 concepts renders; pan/zoom/drag works
3. Search (label+alias), category filters, importance filter work
4. Click node → detail panel: definition, aliases, category path, stats, related concepts (navigable), evidence quotes
5. Query mode: 43 queries highlight ranked concepts
6. Zero external CDN dependencies at page load (fully offline intranet)
7. Server survives; start/stop scripts + README documented

## Open questions
- Firewall state for chosen port (no sudo to change; other 0.0.0.0 services listen freely, so likely open) [HYPOTHESIS → verify by curl on 10.20.113.88]
