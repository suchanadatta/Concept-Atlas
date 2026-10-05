# 03 — Step Specs

## STEP 1: Data preparation
- Input: `final/concept_graph.jsonl`, `final/inverted_index.jsonl`, `final/query_concept_map.json`, `final/category_tree.json`
- Output: `graph-ui/data/graph-data.json` {meta, categories[9 w/ colors], nodes[], edges[], queries[], evidence{cid:[...]}}
- Method: python script; compute degree; top-5 evidence per concept (text ≤320 chars); parse book_id → author/year/title; fixed palette map
- Test: script exits 0; JSON loads; counts == 203/1107/43; every edge endpoint exists in nodes
- Risk: book_id format variance → tolerant parser, log unparsed

## STEP 2: UI shell (index.html, style.css, fonts, vendor)
- Output: layout skeleton (header/sidebar/canvas/panel), vendored d3 + fonts
- Test: page loads with zero console errors, zero network 404s (playwright)

## STEP 3: Graph engine (app.js core)
- Method: canvas renderer, d3-force with category-cluster centroids (toggle), quadtree hover/click, zoom/pan/drag, LOD labels
- Test: playwright — nodes visible, hover highlights, click selects, drag moves, zoom works

## STEP 4: Panels & interactions
- Method: sidebar filters (category toggles, importance slider, search w/ suggestions), detail panel (definition/aliases/stats/related/evidence), query mode
- Test: playwright — search "self-love" finds node; click related concept navigates; filter hides nodes; query highlights ranked set

## STEP 5: Server + hosting
- Output: serve.py, start.sh, stop.sh, README.md; running on 0.0.0.0:8788
- Test: curl localhost + curl 10.20.113.88:8788 (intranet bind proof); /healthz 200; playwright loads via intranet IP

## STEP 6: Verification waves + audit
- Method: full playwright pass (screenshots), console error check, data integrity re-check, restart server and re-verify (persistence), 3× reload stability
- Test: macro-audit checklist; CONTINUATION_STATE.md
