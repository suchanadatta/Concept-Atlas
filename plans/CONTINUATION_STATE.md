# CONTINUATION_STATE.md
(rewritten Tue Sep 8 2026 — supersedes the Aug 25 v3-supervisor state; the OCR
pipeline finished and the project moved on to retrieval quality, the concept
atlas UI, and the Ask/Debate agent layer. Prior content is in git history.)

## Session Summary
| Field | Value |
|-------|-------|
| Phase | STABILIZED — v23 feature-complete; all work committed; all four services running |
| What I did | Full re-read of the repo after ~3 weeks of changes (37 commits); verified git==GitHub, verified deployed services run the committed code, quarantined a stray tracked empty file (`Concept`), refreshed this state file and the audit log |
| What worked | Everything verified: clean tree, HEAD==origin/main, UI/chat/Jasper/vLLM healthy, semantic+BM25 proxies answer with facets |
| What failed | nothing this session |
| Errors remaining | none known |
| Next priorities | user's iterative requests (see below); nothing blocking |
| Audit status | FIRST_PASS (this re-check) — see plans/05-audit-log.md |

## The corpus (final numbers)
- **197 indexed sources** = 129 scanned volumes (61 `outputs/corpus/` author-named
  dirs + 68 `outputs/full_set/<BOOK_ID>/` dirs) + 68 clean-text editions
  (`data/txt_books/`). 27,105 pages, ~1.9M word boxes (v3 word-map).
- **90,975 passages** in the Jasper v2 index (`models/jasper_index_v2/`,
  gitignored, rebuildable via `tools/build_jasper_index_v2.py`).
- **202 concepts / 1,099 relations / 2,072 verbatim evidence paragraphs / 42
  research queries** in `Concept Maps/final/` (15 extractors → 20 verifiers →
  20 double-auditors → 25 independent auditors).
- **37 authors** in `data/authors.csv` (sex + life dates, joined to all 197
  sources by `tools/build_author_stats.py`). Women: 10 authors, 38 sources,
  16% of indexed text; 13 concepts attested only by women.
- OCR pipeline root causes fixed (Aug 25): `filter_word_order` + provider
  sorter now height-adaptive (`y_tol=max(4,0.55·med_h)`, `x_tol=max(5,0.60·med_h)`,
  `line_tol=max(4,0.55·med_h)`); canary ASTELL_1704 25.5%→54.3%.

## Retrieval quality (v2 index + server)
- `tools/jasper_search_server_v2.py` (:8790, device switchable) — hybrid
  (0.6·cosine + 0.4·IDF-weighted lexical w/ proximity bonus), pure semantic,
  BM25 (postings-list numpy, 2–10ms), keyword; query-embedding LRU cache;
  work-key per-work cap + 100-char core-window near-dup filter; `parse_book_id`
  → author/title/year/cite; `make_snippet` term-cluster-centred.
- `tools/eval_retrieval.py` — latest documented: **nDCG@10 0.977 · MRR 1.000**
  (v21, after the lexical-overlap + BM25 fixes). `tools/audit_retrieval_quality.py`
  for index audits.
- `POST /concepts` (semantic concept-map search), `POST /semantic_graph`
  (embedding passage network), `POST /compare` (pairwise cosine + shared ground
  by min-score), `POST /query_graph` (concept + bridge + docs radial).

## The UI — "Concept Atlas" (`Concept Maps/graph-ui/`, :8788)
One app bar + router (Search / Concept map / Ask), Authors, Docs, dark mode.
- **Search**: 4 ranking modes; refine rail (author / period / source facets
  with live counts); `j`/`k` keyboard nav; citations not filenames; landing
  boards (central concepts, 42 queries, corpus facts, top authors — all run
  real searches); concept-map search in the header box.
- **Reader**: PDF (pdf.js) at exact page with bbox flash + amber outlines;
  TXT paragraph mode; word-selection annotation; toolbar rebuilt v23 (one
  47px row, segmented nav/zoom groups, `⋯` overflow for downloads); loading
  veil; notes pane proportional ≤34%, closeable; `Reader.seq` generation
  token kills the stale-response race; highlights cleared per passage.
- **Two query graphs**: Concept | Semantic | Overlay; radial rings (query →
  concepts → bridges → docs), relation-colored edges, legend, badges; any
  node opens the reader at that passage.
- **Explore**: category toggles, importance/relation sliders (data-driven
  ranges), cluster toggle, label density, fit/re-run, per-relation legend.
- **Compare**: real corpus answer — pairwise cosine, map relations between
  items, strongest passages, shared ground (min-score ranking); concepts or
  free text, up to 4 items.
- **Authors panel**: 37 creators, sex/life dates, per-author stats.
- Playwright-verified at each round (v21: 12/12 results, 13/13 stacking,
  10/10 ranking modes).

## Ask + Debate (agent layer)
- `tools/atlas_chat_server.py` (:8793, proxied via :8788 `/book/api/chat/*`)
  over local vLLM (:8000, `Qwen3.8-27B-TURBO`, 550k ctx).
- **Context you assemble**: whole book / page range / concept (def+aliases+
  relations+quotes) / passage / full search / free note; token sizes shown;
  trim drops largest item first.
- **12 tools** (`tools/atlas_tools.py`): hybrid/semantic/lexical search, read
  page range, concept lookup + 1–2 hop walk, compare ideas, find argued-
  together passages, list books/shelf, query network, author registry,
  `verify_quote`, optional `web_search` (ddgs, pinned backends) + `web_fetch`.
  ~30 tool rounds/question, repeat-call memo + stall detection + wall clock.
- **Self-check**: the model re-reads its draft with tools in hand; answer
  stands or is replaced; panel says which. Citations registered per turn,
  clickable (web→page, corpus→reader, concept→map).
- **Debate**: two agents argue a motion, adjudicator checks quotations and
  reports real disagreement vs corpus verdict; shared live citation table;
  pause/resume at the exact turn; moderator notes to either side.
- **Accounts**: pbkdf2-sha256 (200k iters), 30-day tokens, username-or-email
  login, password change invalidates other sessions, single-use 1h reset
  codes (shown, no mail server). Sessions = gzipped JSONL under
  `data/atlas_chat/` + SQLite index; export/import full transcripts.
- **Conversation panel**: enumerated turns, any droppable (struck through,
  stops being sent) — prunable history.

## Deployed services (all running, all current code)
| Port | Process | Started | Notes |
|------|---------|---------|-------|
| 8788 | `Concept Maps/graph-ui/serve.py` (pid 2271829) | Sep 7 03:20 | static+API+proxies; healthz `concept-atlas` |
| 8790 | `tools/jasper_search_server_v2.py --device cuda` (pid 3633650) | Sep 6 17:15 | 90,975 passages, 197 books, 202 concepts, cache 242 |
| 8793 | `tools/atlas_chat_server.py` (pid 2323181) | — | 7 users, 31 sessions, model Qwen3.8-27B-TURBO |
| 8000 | vLLM `Qwen3.8-27B-TURBO-Heretic` (pid 2547214) | Sep 4 16:26 | 550k ctx, fp8 kv, prefix caching, auto tool choice |

GPU note: Jasper now runs on **cuda** (user's training no longer holds the
GPU). If training returns, switch via settings bar (`POST /device`) or
relaunch with `--device cpu`.

## GitHub
- Repo `Shuvam-Banerji-Seal/BMoral` (PRIVATE), branch `main`.
- HEAD == origin/main == `58a69a2` (after this session's cleanup commit),
  38 commits. Working tree clean.
- 758 tracked files: 276 outputs/full_set + 240 outputs/corpus (git-quoted
  author dirs), 97 Concept Maps, 71 data, 31 log, 23 tools, 12 plans.
- Gitignored (rebuildable/per-deployment): models weights+embeddings,
  `models/jasper_index_v2/`, PDFs/zips, logs, `.rigor-trash/`, chat store
  `data/atlas_chat/`, session notes.
- Fresh-clone path: `scripts/bootstrap.sh` (uv + deps + model + index build).

## Continuation Prompt Hints
User's standing directive: keep improving semantic-search quality/indexing
and iterate on UI/UX. Next moves when work resumes: (1) re-run
`tools/eval_retrieval.py` and push retrieval quality further (query expansion
/ reranking); (2) any UI/UX request the user brings; (3) re-verify with
Playwright after each change; (4) commit + push each round.