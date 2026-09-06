# Concept Atlas — graph view UI

A scholar's search system over the **British Moral Philosophy corpus**:
129 scanned volumes plus 68 clean-text editions (197 indexed sources,
90,975 passages, 37 authors) mapped to 202 concepts and 1,099 relations,
built from `Concept Maps/final/` (the double-audited merge) and searched
with a Jasper embedding index.

**Live on the intranet:** `http://10.20.113.88:8788`

## Features

- **2D canvas view** — force-directed layout, category-clustered, LOD labels,
  hover neighborhood highlighting, drag/zoom/pan
- **3D WebGL view** (`3D` button) — same data via Three.js force layout in 3D,
  orbit controls, label sprites, click/hover/search/query all wired
- **Search** — four ranking modes (hybrid, pure semantic, BM25, keyword) over
  90,975 passages, with a refine rail (author, written-by, period, source),
  citations rather than filenames, and `j`/`k` navigation
- **Two query graphs** — the curated concept map, an embedding-induced passage
  network, and an overlay of both; any node opens the reader at that passage
- **Authors** — 37 creators with sex and life dates, joined to every source
- **Concept search** — semantic over the concept embeddings, so a question
  with no literal overlap still finds the right concepts
- **Explore tab** — category toggles, importance & relation-strength sliders
  (ranges follow the actual data), cluster toggle, label density, fit/re-run
- **Queries tab** — the 42 corpus queries; selecting one highlights its
  top-ranked concepts (rank badges in 2D, accent coloring in 3D), and
  "search the corpus" runs it against the passages
- **Detail panel** — definition, aliases, category path, stats, related
  concepts grouped by relation (click to navigate), verbatim evidence quotes
  with citations (author · year · page · book)

## Run

```bash
cd "Concept Maps/graph-ui"
./start.sh            # serves on 0.0.0.0:8788 (pid in atlas.pid, log in atlas.log)
./start.sh 9000       # custom port
./stop.sh
curl localhost:8788/healthz
```

Regenerate data after the corpus merge changes:

```bash
python3 prepare_data.py        # final/*.jsonl -> data/graph-data.json
```

## Architecture

```
graph-ui/
├── index.html            # shell: header, sidebar, stage, detail panel
├── style.css             # "scholarly atlas" theme (parchment, EB Garamond, Inter)
├── app.js                # 2D canvas engine (d3-force) + 3D mode (ForceGraph3D)
├── labels3d.mjs          # ES module: label sprites (vendored three r179 via import map)
├── prepare_data.py       # final/*.jsonl -> data/graph-data.json
├── serve.py              # threaded static server: gzip, 304 revalidation, /healthz
├── start.sh / stop.sh    # process management (setsid + pidfile)
├── data/graph-data.json  # generated (nodes, edges, queries, evidence, colors)
└── vendor/               # d3 v7.9.0, 3d-force-graph v1.80.0, three r179, fonts
```

**Zero CDN dependencies** — everything vendored; works on an offline intranet.

## Notes

- Data source of truth is `../final/` (double-audited). 5 of the 1107 source
  edges reference node ids that no longer exist after dedup; they are dropped
  at data-prep time (source files untouched).
- The 3D view requires WebGL + import-map support (any modern browser).
- Boot persistence: `@reboot` crontab entry (see below) or re-run `start.sh`.

## Book Reader & Scholar Tools (v2)

Every evidence passage is now a **portal into the actual book**:

- **📖 Open in PDF** — any evidence in the detail panel opens a full PDF reader
  (pdf.js, vendored) at that exact page, with the passage's `bbox_pts` rectangle
  **flashed on the scan** (green fade) and all concept passages for that page
  outlined in amber.
- **Jump to book** — the reader is a full book viewer: prev/next, page jump,
  zoom, printed-vs-sequential page numbers, OCR text side panel per page.
- **Annotations** — toggle ✎ and drag on the page to draw boxes with notes;
  stored per book+page server-side (`data/annotations/`), reload on return.
- **Downloads** — ⬇ PDF / TXT / MD / OCR JSONL for every book, plus direct
  download buttons on each evidence card.
- **Library API** — `/book/api/library` lists all 129 books with OCR/PDF/MD
  availability; `/book/api/page_text?book=ID&page=N` returns blocks with bboxes
  for overlay rendering.

### New endpoints
```
GET  /book/api/library                     129 books + availability flags
GET  /book/pdf/{book_id}                   stream source PDF
GET  /book/txt/{book_id}                   TXT version (corpus text files)
GET  /book/md/{book_id}                    OCR markdown
GET  /book/jsonl/{book_id}                 OCR pages JSONL
GET  /book/api/page_text?book=&page=       blocks + bbox_pts for a page
GET  /book/api/annotations?book=           saved annotations
POST /book/api/annotations?book=&page=     save annotations
```

## v3 — Playwright-audited fixes
- `setStatus` ReferenceError fixed (reader-local definition)
- Keyboard: Esc closes reader, ←/→ pages, +/− zoom
- TXT mode: books without PDF scans open as text (scrolls to passage)
- Ghost book_ids fixed (67+9 entries remapped to real corpus IDs: e.g.
  `HUTCHESON_1725_Inquiry_Beauty_Virtue` → `HUTCHESON_1725_1726_An-Inquiry-...`)
- Evidence coverage: 778/780 (99.7%) entries now open in PDF reader
- Highlight scroll-into-view; annotations render immediately after save

## v4 — Scholar improvements (Playwright-verified)
- **In-book full-text search** with **18th-c spelling variants** (virtue→vertue,
  long-s f↔s, archaic dictionary) — hits show page + snippet + match count,
  click to jump; variant flagged when an archaic form matched
- **Annotation export**: ⬇ notes (JSON) / ⬇ notes.md (Markdown) per book
- **Compare view** (⇄): 2-4 concepts side-by-side — definitions + evidence
  columns, 📖 buttons jump straight into the PDFs
- **Dark mode** (🌙): full theme incl. canvas repaint, persisted in localStorage
- **Keyboard help** (?): shortcut reference card
- **Query-fit ranking**: concepts now sorted by their own query relevance
  (fixes p3 finding that "conscience" ranked 5th on the Conscience query)
- Fixes found via Playwright: export route 404, ghost book_ids (76 remapped),
  dark-canvas repaint, archaic search miss on "vertue"
- Regression: **15/15 checks pass**, console clean

## v5 — Search-engine-first interface
- **Landing page**: Google-scholar-style big search box with example queries
  and links to the concept graph / research queries. The graph is now a
  *feature* reachable from search results (Graph tab), not the entry point.
- **Global passage search** (`/book/api/gsearch`): any query searched across
  ALL 129 books' OCR text with archaic variants (vertue, loue, felf…).
  Multi-word = AND per page. **In-memory page index** → instant (0.01s after
  one-time ~25s build on first search).
- **Results view**: Passages tab (book · page · snippet with <mark> term
  highlighting · hit count) + Concepts tab (fuzzy concept match with
  definition) + Graph tab (jump into the graph at the concept).
- **Word-level PDF highlighting**: clicking a passage opens the reader at
  that page and highlights EVERY matching word with its precise `bbox_pts`
  from the OCR `words[]` geometry (e.g. 18 word-boxes for "marriage and
  slavery", 13 for "self-love"). Hyphenated queries split (self-love →
  self + love).
- **Dark mode fixed**: search input, suggestions dropdown, tooltip, mode
  buttons, sliders, zoom controls, query banner — all verified by computed-
  style luminance checks in Playwright.
- Header search box now falls through to global search when no concept
  suggestion matches.
- URL state: `?q=term` (search results), `?view=graph`, `?view=queries`.

## v6 — Jasper semantic search + scholar UX
- **Jasper-Token-Compression-600M** (infgrad) downloaded to `models/Jasper-Token-Compression-600M/`
  (1.2 GB, sentence-transformers 6.0.1, torch 2.13 cu130, trust_remote_code, 2048-dim,
  compression_ratio 0.3333). Deps tracked in repo-root `pyproject.toml` (uv).
- **tools/build_jasper_index.py** — embeds all ~112k corpus paragraphs →
  `models/jasper_index/{embeddings.npy,meta.jsonl}`. Auto-armed:
  `log/build_jasper_index_when_gpu_free.sh` polls GPU every 5 min; when your
  training frees it (<5 GB), it builds the index on cuda (batch 128, ~minutes)
  and then auto-starts the semantic server.
- **tools/jasper_search_server.py** (:8790) — `POST /semantic {query,top_k}` →
  hybrid ranking: 0.6·cosine(Jasper) + 0.4·archaic-aware lexical overlap,
  max 3 paragraphs/book, snippets centered on first term hit, ~50ms/query.
- **UI**: search tries semantic first (summary shows "· semantic"), falls back
  to the lexical page index when the server is down (e.g. until GPU frees).
- **Side-panel documents**: passage clicks now open the reader DOCKED on the
  right of the results view (no page change); results stay visible beside it.
- **Floating concept-graph window**: movable (drag title bar), resizable
  (corner), mini force-graph over the search results; concept clicks open it
  focused; ⛶ expands to the full graph view.
- **Mobile**: responsive layout at ≤820px — landing, results, reader
  (full-screen), compare, graph all usable on a phone; no horizontal scroll.
- **Fixes**: word-highlight dedup (was doubling), search tab reset per query,
  page-index warmup at server start (search no longer stalls ~25s on first
  query after restart), renderResults null-guard.

## v7 — Graph overhaul + search-engine completions
- **Per-relation visual language**: every one of the 10 relation types has its
  own color + dash pattern + width (2D canvas dashes; 3D colors/widths; red
  `opposes`/`contrasts` links also pulse with directional particles). The
  sidebar Relations legend renders each relation's exact line style.
- **Spherical 3D nodes**: `nodeResolution(24)`/`linkResolution(3)` — no more
  faceted hexagons/cones; `onLinkClick` opens the same edge info panel as 2D.
- **More spacing**: 2D charge −80→−150/−220·importance, link distance
  46+50(1−w)→68+68(1−w), collide radius+9×2iters; 3D charge −130→−230,
  links 50+55(1−w)→74+76(1−w).
- **Neighborhood isolation**: new Layout → Neighborhood control
  (full graph / 1-hop / 2-hop). Clicking a concept re-fits to just its
  neighborhood; works in 2D and 3D; count shown in status bar.
- **Edge clicks everywhere**: 2D segment hit-test + 3D link clicks both open
  the relation panel (endpoints, strength, same-relation links).
- **Concept search**: natural-language queries work ("What is love?" →
  Love/Self-Love/Regulation of Love via stopword-stripped content terms).
- **Search-mode toggle**: 🧠 semantic (Jasper :8790, auto) vs ⌨ keyword-only
  buttons in the results bar; re-runs the query on switch.
- Jasper server healthy (132,444 paragraphs, 2048-dim).

## v8 — Graph overhaul + search completions (Playwright-verified)
- **Per-relation visual language**: 10 relations × distinct color + dash +
  width (green supports, teal requires, forest entails, olive-dash underlies,
  blue long-dash develops-from, light-blue dot influences, gray exemplifies,
  violet dash-dot subsumes, thick red opposes, orange-dash contrasts-with).
  2D canvas dashes, 3D colors + widths (+pulse particles on opposes);
  sidebar legend renders each exact style with tooltips.
- **Spherical 3D nodes**: nodeResolution(24)/linkResolution(3); `onLinkClick`
  opens the relation info panel.
- **Spacing**: 2D charge −80→−150/−220·imp, links +50% longer, collide r+9×2;
  3D charge −230, links stretched, cluster force loosened.
- **Neighborhood isolation**: Layout → Neighborhood (full/1-hop/2-hop);
  selecting a concept re-fits to just its neighborhood with a status count;
  works in 2D and 3D (3D ego-filter confirmed: 26 nodes).
- **Edge clicks**: 2D segment hit-test (±7px) + 3D link clicks → relation
  panel (endpoints with dots, strength, same-relation links). Fixed a real
  bug: sim edges carry source/target (objects), panel now resolves both shapes.
- **"What is love?" fixed**: concept search strips question words/stopwords,
  matches content terms; Love/Self-Love/Regulation-of-Love top the list.
- **Search-mode toggle**: 🧠 semantic / ⌨ keyword buttons re-run the query;
  verified both directions.
- **Passage→docked reader**: result click opens the side-panel PDF at the
  exact page with word-level highlights + synced OCR panel (verified p330
  with 1 block + 23 word boxes).

## v9 — Search UX overhaul
- **IPv6 fix**: Chromium resolves `localhost`→`::1`; Jasper server was IPv4-only
  → every semantic fetch silently hung. Server now dual-stack (`::` with
  V6ONLY=0, falls back to 0.0.0.0); UI fetches `127.0.0.1` directly.
- **Relevance scores on every passage**: semantic mode shows
  `score 0.82 (sem 0.70 · lex 1.00)` — hybrid breakdown; keyword mode shows
  `keyword ×N` counts.
- **Top search bar in results**: re-query without leaving results
  (Enter or Search button; preserves focus).
- **Split reading**: results shrink to the left 46%, reader slides in as
  the right 54% (CSS transition, `body.split-reading`); Esc restores.
  Toolbar wraps (title on its own row) — no more overflow.

## v10 — Scholar UX round (all Playwright-verified)
- **IPv6 semantic-server hang FIXED (root cause)**: Chromium resolves
  `localhost`→`::1`; the Jasper server bound IPv4 only → every semantic
  fetch silently timed out and the UI fell back to keyword. Server now
  dual-stack (`::` + V6ONLY=0, IPv4 fallback); UI hits `127.0.0.1` directly.
- **Relevance scores on all 40 passages**: `score 0.82 (sem 0.70 · lex 1.00)`
  in semantic mode; `keyword ×N` in keyword mode.
- **Top search bar in results**: refine query in place (Enter/Search);
  verified re-query "moral sense" → semantic results.
- **Split reading layout**: results shrink left 46%, reader slides in right
  54% with CSS transition; toolbar wraps (title row) — overflow gone.
- **⤢ spread button**: +40% spacing per click (2D: charge/link/collide ×
  spread; 3D: same via d3 forces; cluster radius too). Measured: 51→58→66px
  avg NN-distance in 2D; 118px in 3D at 2.2×.
- **Evidence expander**: concepts now carry up to 12 passages (data-prep
  raised from 5); UI shows 5 + "show all 12" button (verified 5→12).
- **Docs page** (`docs.html`, "Docs" header link): full usage documentation —
  searching, modes, graph reading (relation line styles), reader, shortcuts,
  floating window, under-the-hood.
- Dark-mode luminance audit across 14 element classes: 0 issues.

## v11 — TXT annotation + result fixes
- **TXT word-annotation fixed**: selection `mouseup` now fires via
  document-level fallback (synthetic + real drags both work); 5-word select
  → blue marks + side-panel entry, persisted per (para_idx, w0, w1).
- **TXT-only search hits skip broken PDF path**: index entries with
  `page=null` open straight in paragraph text mode — no more
  `MissingPDFException` + 404 console errors.
- **Semantic CORS preflight fixed**: `do_OPTIONS` now sends `Content-Length: 0`
  (HTTP/1.1 keep-alive browsers hang otherwise) + dual-stack bind so
  Chromium's `::1` reaches the server.

## v12 — final polish (Playwright 19/21 → verified)
- **Back-to-search button**: visible on graph/queries views, hidden on
  search/landing — logic now runs on every page load (was gated on URL
  params at init only).
- **Evidence → PDF word highlights**: opening evidence from the concept
  detail panel now seeds `Reader.activeTerms` from the concept's label +
  aliases (self_love → self, love, amour, propre, private, interest), so
  matching words are boxed on the scan. Where the OCR `words[]` layer has
  no geometry for that page (coverage ~50%), the block-level amber box
  still shows (verified: hlBox=1).
- Verified page-words API: 368 words on the test page — the 0-match case
  was a publisher book-list page (no self/love words), i.e. correct
  behavior, not a bug.

## v13 — UI polish round (Playwright-verified)
- **Semantic vs keyword genuinely different**: semantic = Jasper hybrid scores
  (40 results, DRAKE on top for "greed and envy"); keyword = 8 lexical hits
  (Turnbull on top) with ×N counts. Toggle re-runs the query both ways.
- **Searching state**: animated spinner + "embedding your query with Jasper ·
  ranking 132,444 passages" during the ~4s semantic round-trip (was a blank
  "Searching…" line).
- **Reader-close layout bug fixed**: closing the split reader (or the dynamic
  graph panel) now restores the results pane to full width — `clearSplit()`
  resets the inline right/left/width styles (was leaving gres at 589px).
- **Dynamic query graph → side panel**: Graph tab now opens a full-featured
  graph panel (like the PDF reader dock) — 2D force canvas AND 3D WebGL
  (ForceGraph3D, spherical nodes), query node center, document nodes sized by
  relevance, concept nodes; click a doc → reader opens that book; click a
  concept → selects it in the main graph. Esc closes.
- **SVG icons**: zoom in/out/fit + page arrows are proper SVG glyphs now.

## v14 — UX fixes (Playwright-verified)
- **Mode-button state fixed**: HTML hardcoded ⌨ keyword as `active` on load,
  so every fresh search LOOKED keyword even when semantic results rendered.
  Now 🧠 semantic is the default active state (matches the actual engine).
- **PDF loading screen**: spinner + "Opening <book>… streaming PDF scan ·
  rendering page N" while large scans stream; page-wrap markup restored
  after load (annotation drag rewired).
- **Main graph zoom-adaptive edges**: zoomed in (k>1.4) edges fade up to
  88% so nodes read clearly; zoomed far out (k<0.7) the mesh thins — no
  more "wall of edges" masking nodes.
- **Dynamic query graph — full camera**: pan (drag background), zoom toward
  cursor (wheel), node drag, hover isolation (non-neighbors dim to 22%,
  incident edges highlight), labels fade in with zoom level, hairline
  strokes under zoom; click doc → reader, click concept → main graph.

## v15 — TXT search + recheck fixes (Playwright-verified)
- **In-book search works for TXT-only books** (BUTLER_1726 etc.): server falls
  back to paragraph-scanning the plain-text file (40 hits for "virtue");
  results show `¶ N` and click-scroll to the paragraph with a flash.
- **PDF flow verified end-to-end**: loading spinner → canvas render (323px
  auto-fit) → 10 word-level highlights + 1 block box on p.255 of Hutcheson.
- Earlier "PDF not rendering" in the sweep was a test-selector artifact —
  the top semantic results for "self-love and benevolence" are TXT-only
  books (correct paragraph-reader behavior), not broken PDFs.

## v16 — recheck round (all Playwright-verified)
- **In-book search for TXT books**: server-side paragraph fallback (40 hits
  for "virtue" in Butler); results show ¶ numbers, click scrolls + flashes.
- **Back-to-search button**: now syncs correctly — visible on graph view,
  hidden on search/landing; clicking returns to search (verified both ways).
- **Mobile reader full-screen**: applySplit detects ≤820px and makes the
  reader cover the whole screen (was 216px sliver); divider hidden on
  mobile; dyngraph full-screen too. Desktop split (54%) re-verified after.
- **PDF flow confirmed**: loading spinner → 323px auto-fit canvas → 10 word
  highlights + block box (Hutcheson p.255). Earlier "PDF not loading" was
  the top results being TXT-only books — correct paragraph-reader routing.
- Console: 0 errors across all sweeps.

## v17 — deep recheck (all Playwright-verified)
- **Three.js duplicate-instance warning root-caused**: `three.module.min.js`
  is a re-export shim (`from"./three.core.min.js"`) + bundled copy inside
  `3d-force-graph.min.js` (UMD, self-contained). Impossible to unify without
  vendoring the ~15-package ESM tree — documented as known-benign in
  `labels3d.mjs` (3D renders correctly, labels attach fine).
- **Mobile dyngraph full-screen fixed**: the v13 media rule lost the
  specificity war (`#dyngraph` base rule wins ties) — now `!important` +
  `left:0`; verified 400px full-width, node tap, compare overlay.
- **Gap sweep re-verified**: compare view (3 cols), help overlay, float graph,
  TXT reader (271 paras), queries tab + select, in-book search, annotations,
  export buttons, keyboard, theme persistence — all green, 0 console errors.

## v18 — semantic that works from ANY machine (root-cause fix)
- **Bug**: the browser fetched `http://127.0.0.1:8790/semantic` directly.
  That loopback resolves on the *server host only* — every intranet client
  (10.20.113.88) got connection-refused and silently fell back to keyword,
  reporting "semantic not working". Undetectable from server-side tests.
- **Fix**: new same-origin proxy `POST /book/api/semantic_proxy` on :8788
  forwards to the Jasper server; UI uses the proxy. Verified: "greed and
  envy" → 40 scored passages, top `score 0.80 (sem 0.67 · lex 1.00)`.

## v20 — retrieval dedup (Playwright-verified)
- **Per-WORK result cap**: `work_key()` normalizes book_ids so editions of
  the same work (Watts 1733/1742, King 1st/2nd) count as ONE work with a
  3-result cap — the top-8 for a liberty/necessity query now spans 5+
  distinct authors instead of 3 editions of the same essays.
- **Core-window near-dup filter**: 100-char normalized window at offset 200
  drops exact reprints across editions.
- Eval after dedup: nDCG@10 0.890 · MRR 0.802 (diversity up, ranking held).

## v21 — citations, facets, and a concept-map search engine

**Backend** (`tools/jasper_search_server_v2.py`)
- **Query-embedding LRU cache.** A single user query hit the model up to
  three times (passages → mode switch → query graph). On CPU that was ~30s
  of re-encoding for one vector; repeats now return in ~40ms. `/healthz`
  reports cache size and hit rate; a device switch clears it.
- **`POST /concepts`** — semantic search over the concept map itself. The 202
  concept vectors were loaded but only `/query_graph` used them, so concept
  lookup was pure string matching. "what makes an action morally right?" now
  returns Moral Obligation, Moral Fitness, Eternal Morality.
- **BM25 was broken and is now fast.** `s, dl, norm = 0.0, len(toks), k1 * (…
  dl …)` reads `dl` while the tuple is still evaluating, so every `/bm25`
  call raised UnboundLocalError and the UI silently fell back to lexical.
  Rewritten on postings lists with numpy scoring: 2–10ms, correct, and the
  results carry citations, snippets and facets like the semantic path.
- **`lexical_overlap` is IDF-weighted with a proximity bonus** and drops
  function words. Flat coverage saturated at 1.00 for every candidate, so the
  0.4 lexical half of the hybrid score carried no discrimination at all.
  `will`/`good`/`right`/`end` stay searchable — moral vocabulary here.
- **`parse_book_id()`** turns raw ids into author/title/year/volume. All 197
  ids in the index parse. **`make_snippet()`** centres on the densest term
  cluster, snaps to word boundaries and strips OCR/LaTeX artifacts; the old
  fixed slice regularly ended mid-word ("…at the grea").
- Responses carry `author`/`title`/`year`/`cite` plus author, period and work
  facets.

**Frontend**
- **`cite.js`** — the same parser for the client-only paths. Results read
  *Clarke, A Discourse Concerning the Unchangeable Obligations of Natural
  Religion (1706)* instead of `CLARKE_1706_1708_A-Discourse-…`.
- **Refine rail** — filter by author, period and source with live counts;
  sort by relevance / year / author. Uses the space left of the results.
- **Score bars scaled across the result set.** An absolute 0–1 bar was full
  for every row, since every good hit sits near 0.85.
- `j`/`k`/`↑↓` + `Enter` keyboard navigation; stopword-aware highlighting
  (every snippet used to paint "and" and "the" yellow); "text edition"
  instead of "page null" for the TXT corpus.
- **Settings popover** replaces the bare bottom strip: device switch, results
  per search, default ranking, refine panel, theme — persisted to
  localStorage — plus live index/cache stats and last-search timing.
- **Landing boards**: central concepts, curated research questions, corpus
  facts and most-represented authors. Every item runs a real search.
- **Concept-map search** — the header box runs a semantic pass after the
  literal one, marked with a diamond.
- 2D graph labels are collision-culled against each other and against node
  circles, in importance order.
- Query graph: passage nodes carry real citations; the legend explains the
  match-% badge and bridge concepts.

**Fixes**
- The fixed settings strip overlapped every full-height panel (results,
  reader, query graph) and the graph status bar. Its height is now reserved.
- Dark mode defined only four of its tokens, so anything using `--paper` /
  `--ink-soft` / `--ink-faint` rendered light-on-light.
- Keyword mode required *every* token including function words, so a real
  research question matched nothing; it now requires content words and
  relaxes to a majority when the strict pass is empty.
- `window.__doGlobalSearch` was only published from inside `doGlobalSearch`,
  so any external trigger before the first search hid the landing page and
  rendered nothing.
- `serve.py`: four near-identical Jasper proxies collapsed into one helper;
  adds `/book/api/concepts_proxy` and `/book/api/engine`.

Verified: Playwright 12/12 results behaviour, 13/13 panel stacking, 10/10
ranking modes; `tools/eval_retrieval.py` nDCG@10 0.977 · MRR 1.000.

## v22 — two query graphs, the author registry, and a reader that lands on the right page

**The reader bug** (reported: "clicking a result takes me to a highlighted page
with completely different text and wrong annotations"). The data was sound —
all 129 OCR book_ids resolve to the right PDF, JSONL record counts match PDF
page counts for all 133 books, and `page_rect_pts` matches the real PDF page
size on all 665 sampled pages, so OCR page N really is PDF page N. The
corruption was a front-end race: five async paths (PDF load, page render, OCR
fetch, word-highlight fetch, annotation fetch) all wrote into one shared
`Reader` object with no guard, so clicking a second result before the first
finished let a stale response land on the new page. Fixed with a `Reader.seq`
generation token that every continuation checks, plus a book/page re-check on
each fetch. `Reader.highlights` was also pushed to and never cleared, so boxes
from every previously opened passage reappeared on unrelated pages; the caller
now hands `openReader` the boxes for *this* passage.

**Oval nodes.** `resize()` ran only on `window.resize`, so opening the detail
panel narrowed the stage without updating the canvas backing store and the
bitmap was stretched non-uniformly. A `ResizeObserver` on `#stage` fixes it.

**Two kinds of query graph.** `POST /semantic_graph` builds a network from the
passage embeddings rather than the concept map, so a query about anything the
map never recorded still produces a real graph. Nodes are passages; edges are
cosine similarity in four bands (near-identical wording → loosely related —
an embedding cannot claim "supports"); communities come from weighted label
propagation, each named by its IDF-weighted distinctive terms. The panel now
offers **Concept | Semantic | Overlay**; overlay draws the curated concepts
inside the passage network, linked to the passages they land on. Any node
click opens the reader at that page with the passage highlighted.

**Concept cards** carry the map: `/concepts` returns each concept's relations,
marking the ones whose other end is also a hit for this query. Chips are
grouped by target concept (the map records several relations between the same
pair) and navigate to that concept's card.

**Author registry.** `data/authors.csv` records each creator's sex and life
dates; `tools/build_author_stats.py` joins it to all 197 indexed sources and
the concept inverted index (all 197 match). Adds a **Written by** search facet
and an **Authors** panel. Women wrote 16% of the indexed text (10 authors, 38
sources); normalised by each group's own concept attestations, the women's
works cluster on devotional practice and the social position of women
(Sacrament, Mortification, Prophecy, Education of Women, Ridicule, Wit) while
the men's cluster on systematic metaethics and political authority (Eternal
Morality, Approbation, Contract, Paternal Authority, Subordination). Several
counts are thin and are shown as counts.

**Dark mode is global.** There were two theme stores — `atlas-theme` (header
button) and `atlas.settings` (settings panel) — which disagreed. `theme.js` is
now the single store, migrates the old key, applies the class before first
paint, follows the OS when nothing is stored, and is loaded on `docs.html`
too (which had dark CSS but nothing to set the class).

**3D readability.** Label sprites baked a hard-coded parchment halo, so every
label in dark mode sat on a bright cream slab. The halo follows the theme, far
fewer nodes are labelled (18 in the concept graph; query + concepts + the
strongest passage per cluster in the query graph), and both views fit the
camera a second time once the layout has actually stopped.
