# 05 — Audit Log

| Time | Audit | Result |
|------|-------|--------|
| 2026-08-13 | Micro: clone verified (log, status, size) | PASS |
| 2026-08-13 | Micro: all 10 repo files read (7 text + 3 assets) | PASS |
| 2026-08-13 | Micro: paper fully extracted + read (736 lines) | PASS |
| 2026-08-13 | Micro: wheel code read (model 464 lines, config, logit processor, evict floor) | PASS |
| 2026-08-13 | Micro: external claims verified (GitHub API, HF API, HF config.json, arXiv API) | PASS |
| 2026-08-13 | Macro: todo audit — 5/5 items done; no silent drops | PASS |
| 2026-08-13 | Macro: [HYPOTHESIS]/[UNKNOWN] inventory — 2 open items flagged (O1, O2), none papered over | PASS |
| 2026-08-13 | Macro: nothing deleted anywhere; wheel unpack in /tmp/opencode (permitted tempdir) | PASS |

## Verification waves
- Wave 1 (after last change): re-read of key files not needed — no files were modified after study; final summary written from verified notes. PASS| 2026-08-13 | Micro: GLM-OCR clone verified (log/status/size/commits) | PASS |
| 2026-08-13 | Micro: SDK core modules read (api, pipeline, ocr_client, layout, config) | PASS |
| 2026-08-13 | Micro: external claims verified (GitHub, HF API, HF config.json, arXiv) | PASS |
| 2026-08-13 | Macro: todo audit — clone+study complete; no silent drops | PASS |
| 2026-08-13 | Micro: GLM-OCR model download verified — sha256 == HF LFS oid (a16eb0de...), size byte-exact (2,650,579,464), 526 BF16 tensors parse | PASS |
| 2026-08-13 | Micro: config.json identical to pre-download fetch; tokenizer parses (59,282 vocab) | PASS |
| 2026-08-13 | Macro: param count 1,325,258,240 (1.33B) — README "0.9B" = text-side only (decoder 582M + MTP 218M + head 91M = 891M); vision 434M excluded. MTP module present in weights (layers.16 + shared_head). | PASS (O3/F10 resolved) |
| 2026-08-13 | Flag: runtime load requires transformers>=5.3.0 (local 4.57.6 too old; glm_ocr not natively recognized). Not upgraded without user consent. | OPEN |
| 2026-08-13 | Micro: zip inspected — 182 entries: 61 PDFs (29 author dirs, 21 non-empty) + 91 __MACOSX junk; 2,124,825,279 B | PASS |
| 2026-08-13 | Micro: extracted BMoral_pdf_collection/* to data/ (61 files, 2.0 GB); __MACOSX excluded (zip untouched) | PASS |
| 2026-08-13 | Micro: per-file size check vs zip entries — 61/61 exact; all files %PDF- magic; no extras/dupes | PASS (script encoding bug found+fixed: zip lacks UTF-8 flag → cp437 decode; verified via cp437→utf8 round-trip) |
| 2026-08-13 | Micro: manifest built (data/MANIFEST.csv: author, filename, size_bytes, pages via PyMuPDF) — 11,064 pages total | PASS |
| 2026-08-13 | Note: 8 author dirs empty in source zip (Hume, Locke, Smith, Berkeley, Butler, Gay, Clarke, Balguy) — source truth, not extraction loss | FLAGGED |
| 2026-08-13 | Micro: env verified (vllm 0.27.1 / transformers 5.15.0 / torch 2.13.0+cu130 / glmocr 0.1.5, CUDA on A100) | PASS |
| 2026-08-13 | Micro: server fails diagnosed & fixed (MTP key mismatch → disabled; nvcc 11.5 → CUDA_HOME 13.3) | PASS |
| 2026-08-13 | Micro: raw API + SDK pipeline smoke tests both produce correct 18th-c OCR | PASS |
| 2026-08-13 | Note: batch parse running detached; ETA ~2h51m; monitor log/corpus.log; restart recipe in log/run_server.sh + log/parse_corpus.sh | OPEN (running) |
| 2026-08-13 | Macro: no silent scope changes — MTP speedup dropped explicitly w/ reason; Unlimited-OCR deferred explicitly (needs own weights) | PASS |
| 2026-08-13 | Micro: audit 24 parsed books — 7.07M chars, 4 truncated regions, 2-up interleave bug found | PASS |
| 2026-08-13 | Micro: fixes verified on King Origin of Evil 1st ed — 201 JSONL lines, 0 fails, 68 two-up pages, printed "XV"→15 extracted | PASS |
| 2026-08-13 | Micro: corpus relaunched at 300 dpi with fixes; monitor log/corpus.log | RUNNING |
| 2026-08-14 | Micro: outputs quarantined (5.4G → .rigor-trash/outputs-20260814), GPU freed, batch stopped | PASS |
| 2026-08-14 | Micro: paddle/paddleocr removed from venv (superseded by docTR) | PASS |
| 2026-08-14 | Micro: ruff F/E7/E9 = 0; fitz→pymupdf everywhere; -W error clean | PASS |
| 2026-08-14 | Micro: JSONL v3 verified on Warburton (8p) + King (201p, two_up) — schema/zones/numbers/sanitizer OK | PASS |
| 2026-08-14 | Micro: word_map bugs found+fixed: RGB channels, sort tuple, assign break (1-word/block), double-predict perf, sanitizer KeyError, clamp spill | PASS |
| 2026-08-14 | Micro: validator OK on Warburton (0 problems, 61% coverage); 'Cumaean' highlight verified from mappings | PASS |
| 2026-08-14 | OPEN: King full word-map test running (log/test_king_v3.log); then fresh full corpus run | RUNNING |
| 2026-08-14 | Micro: King two-up word map + validate OK (0 problems, 58.2% cov); Warburton single OK (0 problems, 61% cov) | PASS |
| 2026-08-14 | Micro: 'Cumaean' phrase highlight verified from mappings alone (fitz draw, within page rect) | PASS |
| 2026-08-14 | Micro: sanitizer two-up KeyError fixed; _is_wide_single tightened | PASS |
| 2026-08-14 | Macro: full corpus pipeline running (log/run_all.log); monitor corpus.log/word_map.log/validate.log | RUNNING |
| 2026-08-14 | Open: word coverage ~57-61% (docTR reco limits on 18th-c print); unmatched words fall back to block box | FLAGGED (documented, acceptable) |
| 2026-08-14 | Micro: parse completed — 61/61 books, 11,064 pages, 0 "Failed:" in log | PASS |
| 2026-08-14 | Micro: audit_corpus.py built (PDF→JSONL→page-count→schema→words); ran on partial set — caught Meditations race (mid-write, resolved) + Masham title-page gap (EEBO footer-only page, minor, documented) | PASS (2 findings, 1 resolved, 1 documented) |
| 2026-08-14 | Micro: word map running 21/61; final_check.sh + watch_and_finalize.sh automated (audit --require-words + validate --strict after completion) | RUNNING |
| 2026-08-14 | Micro: quality_checks.py built — 11 independent check modules | PASS |
| 2026-08-14 | Micro: Q1-Q6,Q9 PASS on 61 books (all pages, perfect word tiling 681k→544k, geometry valid, 0 garbage pages, 0 truncation, monotone numbering) | PASS |
| 2026-08-14 | Micro: Q7 found REAL issue — ~2% mis-paired word boxes (DP alignment); fixed via filter_word_order (never emit out-of-order geometry); refilter dropped 137k mis-paired words; Q7 now PASS | PASS |
| 2026-08-14 | Micro: Q11 cross-engine (docTR) — len-ratio p50=1.01 (no content loss); sim 0.36 = docTR rec noise on 18th-c print (documented); 1 content-mismatch/122 pages | PASS (documented) |
| 2026-08-14 | Open: word map 24/61 running; Q7/Q8 mid-run churn resolved by final_check refilter+requality at completion | RUNNING |
| 2026-08-16 | MAJOR: machine rebooted (uptime 4:27) — word map (24/61) + vLLM server killed. Parse outputs intact on disk. | RESOLVED |
| 2026-08-16 | Micro: word_map.py gained --resume mode (skips enriched books); resumed 37 pending books in background (log/word_map_resume.log); vLLM server restarted (health 200) | RUNNING |
| 2026-08-16 | Micro: watch_and_finalize.sh re-armed — runs final_check.sh (refilter + audit + validate + quality) on word-map completion | ARMED |
| 2026-08-22 | INCIDENT: cleanup script over-deleted word_mapping.py (del lines[start:None] removed sort_words_reading_order + trailing content) | FIXED |
| 2026-08-22 | Micro: restored sort_words_reading_order; 13 functions verified; functional smoke tests pass (tiling/align/paragraphs/filter/enrich) | PASS |
| 2026-08-16 | Paragraph pass: 91,673 paragraphs, validate 0 problems | PASS |
| 2026-08-22 | INCIDENT: over-deletion in word_mapping.py (cleanup script `del lines[start:None]` removed sort_words_reading_order + trailing content) | FIXED |
| 2026-08-22 | Recovery: restored sort_words_reading_order (band-clustering version); verified 13 functions present; functional smoke tests pass (tiling, alignment, paragraphs, filter, enrich) | PASS |
| 2026-08-16 | Paragraph pass applied: 91,673 paragraphs, 565 blocks split; validate strict 0 problems | PASS |
| 2026-08-16 | gdown full-set download running: ~11/140 files (786MB); dedup vs existing corpus needed before OCR | RUNNING |
| 2026-08-16 | run_full_set.sh prepared: low-VRAM vLLM (0.10 util = 8GB) → parse → add_paragraphs → word_map --resume → validate/audit (10GB VRAM cap respected) | READY |
| 2026-08-22 | Micro: Q10 flag investigated — Hutcheson p41 'Page 15' block = in-text cross-reference mislabeled by layout model; text captured correctly; noise, documented | CLOSED |
| 2026-08-22 | Micro: parseq GPU re-benchmark interrupted by user; word map stays on crnn_mobilenet_v3_small config (58-61% coverage) | DOCUMENTED |
| 2026-08-22 | Status: download 12/~140 files (834MB); watcher armed; run_full_set.sh ready; corpus complete | STABLE |
| 2026-08-25 | Full-set QA (first run): Q1-Q10 over outputs/full_set — Q1,Q2,Q3,Q5,Q6,Q7,Q9,Q10 PASS; Q5/Q6 perfect tiling+geometry on 1,743,599 words | PASS (8/10) |
| 2026-08-25 | Q4 finding: 2/16,041 pages flagged garbage (CLARKE_1712 p544, CLARKE_1714 p326) — both are scripture INDEX pages (verse refs "1 Pet.I, 2. 41. 212"); text correctly OCR'd; heuristic false positive by content type | DOCUMENTED |
| 2026-08-25 | Q8 finding: full-set coverage 41.3% (corpus ~50-60%); worst ASTELL_1704 26%, TURNBULL 27%/31%. Diagnosis: 99% of blocks still carry words; gap is docTR reco divergence on poorer scans vs align threshold 0.4. Unmatched GLM words fall back to block box | DOCUMENTED (known limitation) |
| 2026-08-25 | audit_corpus --require-words full set: 66/68 → GWINNETT x2 flagged "empty text with text-bearing blocks" = frontispiece plates with engraved captions labeled footer zone → FIXED checker plate rule (allow chrome zones alongside figure zones) → re-run: 68/68 OK, exit 0 | PASS |
| 2026-08-25 | Clean archive rebuilt: full_set_ocr.tar.xz 55MB (272 files = 68 books × pages.jsonl/json/_model.json/md); old 74MB archive (with 28 stale dupes) quarantined .rigor-trash/20260825-045531 + INDEX entry | PASS |
| 2026-08-25 | gdown Drive TXT folder: 68 clean transcriptions → data/txt_books (Gutenberg-style, Title/Author headers) — ground-truth candidates for OCR eval / search index | DONE |
| 2026-08-25 | ROOT CAUSE (coverage): filter_word_order absolute bands (8y/5x normalized) merged tightly-leaded verse/small-type lines (pitch ~6u, h~5-9u) into one false "line" and dropped every line-initial word as x-regression — ASTELL_1704 stored 26% vs raw match rate 54%; Norris(corpus) 20% vs fresh 51.6%. dropY=0 everywhere; all drops were X | FIXED |
| 2026-08-25 | FIX: height-adaptive bands y_tol=max(4,0.55·med_h), x_tol=max(5,0.60·med_h) in word_mapping.filter_word_order; q7_word_order mirrored (keep-in-sync comment). Unit tests: verse 24/24 kept, body unchanged, y-up intruder still dropped. E2E: same 10 ASTELL pages 54.1% stored-equiv vs 26.2% before — full recovery. parseq bench: +0.8pts only → reco model NOT the bottleneck (negative result closes parseq next-step) | PASS |
| 2026-08-25 | Q4 fix: digit-dominated pages (>0.35 ratio; measured indexes 0.35-0.86 vs prose max 0.03) classified as index/reference pages, exempt from garbage FAIL | DONE |
| 2026-08-25 | Re-enrichment launched: log/run_reenrich_fullset.sh (68 books, docTR fp16 det16/reco64, ~2.4s/page ≈10h) then auto-chained corpus chain via watcher (~7h). Stale nested tree quarantined .rigor-trash/<ts>-stale-collection-tree so rglob sees canonical 68 only | RUNNING |
| 2026-08-25 | FULLSET v2 chain DONE 14:11 (68/68): Q1-Q7,Q9,Q10 PASS; Q4 PASS (index exemption works); validate 0 problems; tiling perfect on 1,906,851 words (+163k vs v1); Q8 45.1% agg | PASS* |
| 2026-08-25 | ROOT CAUSE #2 (residual gap): transitions dump shows X-drops WITHIN correctly-separated verse lines → provider-side sort_words_reading_order used ABSOLUTE line_tol=8 which interleaved tight verse lines (pitch 6.7 < 8) into z-order BEFORE alignment; monotone DP then paired tokens to zigzag boxes. Mixed-height hypothesis REJECTED by data (0 drops in mixed blocks, 441 in uniform) | FIXED |
| 2026-08-25 | FIX #2: sort_words_reading_order adaptive band max(4,0.55·med_h); unit tests verse-no-interleave PASS + body PASS. ASTELL residual: raw match 54.3% → v1-filter retained only 73% (441/1638 dropped on sample) due to sorter interleave | FIXED |
| 2026-08-25 | Corpus v2 chain died silently ~15:44 after 4 books (no OOM, no reboot — uptime since 01:31; cause unknown). Response: v3 SUPERVISOR built — single script runs fullset→corpus→finalize with --older-than TS crash-resume (word_map patched); cron @reboot auto-resume armed; launched 16:25 (TS=16:25:55). Full set gets third pass with both fixes | RUNNING |

## Post-OCR era (Sep 4 – Sep 8): retrieval quality → Concept Atlas UI → Ask/Debate agent layer
| Time | Audit | Result |
|------|-------|--------|
| 2026-09-04 | v2 semantic index built: 90,975 noise-filtered, title-prefixed passages with raw_text (`models/jasper_index_v2/`, gitignored/rebuildable); v2 server with query-chrome stripping, work-key dedup, core-window near-dup filter | PASS |
| 2026-09-04 | Eval harness `tools/eval_retrieval.py` (8 complex queries, graded 0/1/2): v1→v2 nDCG@10 0.837→0.890, MRR 0.533→0.802; per-work dedup raised top-8 author diversity to 5+ | PASS |
| 2026-09-04 | CPU/GPU switcher (settings bar, `POST /device`), pure-semantic mode, panel stacking manager — Playwright 7/7 each | PASS |
| 2026-09-04 | GitHub repo `Shuvam-Banerji-Seal/BMoral` (PRIVATE) created; txt_books (68 works, 44MB) + Concept Maps/final + UI + 20 tools committed; bootstrap.sh fresh-clone audit 16/16 | PASS |
| 2026-09-06 | v21 search UX overhaul: query-embedding LRU cache (~30s→40ms); `POST /concepts` semantic concept search; BM25 rewritten on postings lists (was UnboundLocalError, silently fell back to lexical); lexical_overlap IDF-weighted + proximity bonus (flat coverage saturated at 1.00 before); parse_book_id + make_snippet (term-cluster-centred, word-boundary); cite.js; refine rail with live counts; j/k nav; score bars scaled across set; settings popover; landing boards; concept-map search; dark-mode token completion; serve.py proxy consolidation | PASS (Playwright 12/12 results, 13/13 stacking, 10/10 modes; eval nDCG@10 0.977 · MRR 1.000) |
| 2026-09-06 | v22: reader stale-response race fixed via `Reader.seq` generation token + per-fetch book/page re-check; highlights cleared per passage; ResizeObserver on #stage (oval-node stretch); TWO query graphs (Concept/Semantic/Overlay — `POST /semantic_graph` passage-embedding network, 4 cosine bands, label-propagation communities); concept cards carry relations; author registry `data/authors.csv` (37 authors, sex+dates, joined to all 197 sources) + Written-by facet + Authors panel (women 16% of text, 13 concepts attested only by women); global dark mode via single theme.js store (migrates old key, OS-follow); 3D label halos follow theme, fewer labels, double camera fit | PASS |
| 2026-09-06 | v23: reader toolbar rebuilt (one 47px row, segmented nav/zoom, `⋯` overflow menu, page number IS the jump input); synchronous loading veil; notes pane proportional ≤34% + closeable + stacked on mobile; Compare real (`POST /compare`: pairwise cosine re-normalised — bf16 rounding had 1.0064 self-score, map relations between items, strongest passages, shared ground by min-score; concepts OR free text, up to 4 items, autocomplete); Ask the corpus (`tools/atlas_chat_server.py` :8793 proxied via :8788) — user-assembled context (book/page-range/concept/passage/search/note with token sizes, trim drops largest first), reasoning/answer separated, accounts (pbkdf2-sha256 200k, 30-day tokens, username-or-email, password change invalidates others, single-use 1h reset codes), sessions as gzipped JSONL + SQLite index, export/import; mobile reader+chat layouts | PASS |
| 2026-09-06 | Agent tools (`tools/atlas_tools.py`): 12 corpus tools (hybrid/semantic/lexical search, read_source, concept lookup + 1–2 hop walk, compare, argued-together passages, list books, query network, author registry, verify_quote) + optional web_search (ddgs pinned backends, pagination, site:, recency) + web_fetch; ~30 tool rounds/question with repeat-call memo, stall detection, wall clock | PASS |
| 2026-09-06 | One app bar + router (Search/Concept map/Ask), Authors + Docs in the bar; accounts moved out of chat panel; signposted escalation; honest degradation when a backend is down + rewritten help card | PASS |
| 2026-09-06 | Self-check loop: model re-reads draft with tools in hand, answer stands or is replaced, panel says which; citations registered per turn, clickable (web→page, corpus→reader, concept→map) | PASS |
| 2026-09-07 | Debate: two agents argue a motion, adjudicator verifies quotations and reports real disagreement vs corpus verdict; shared live citation table; pause/resume at exact turn; moderator notes; resumed debate restores its citations | PASS |
| 2026-09-07 | Prunable history (dropped turns struck through, stop being sent); docs readable without leaving the app (docs-panel.js); reader keeps reading while the agent writes; tool-budget exhaustion still answers; author filter on corpus+map+both query graphs | PASS |
| 2026-09-07 | Final commits: 911612e "A resumed debate restored its citations six times over" — 37 commits total, HEAD == origin/main, tree clean | PASS |
| 2026-09-08 | Re-check session (this one): git==GitHub verified (fetch, HEAD==origin/main==58a69a2 after cleanup); 4 services verified running current code (8788 UI, 8790 Jasper cuda, 8793 chat 7 users/31 sessions, 8000 vLLM Qwen3.8-27B-TURBO); semantic+BM25 proxies answer with facets; UI renders 0 console errors; stray tracked 0-byte `Concept` file quarantined to .rigor-trash + INDEX entry + commit 58a69a2; CONTINUATION_STATE.md rewritten to current reality | PASS |
| 2026-09-08 | Deep-read audit (rigorous pass over every layer, this session): serve.py 1187 lines, jasper_search_server_v2.py 1585, atlas_chat_server.py 1944, atlas_tools.py 1268, nav.js, theme.js, index.html, settings.js, cite.js in full; chat.js/search.js/reader.js/app.js/dyngraph.js/authors.js/compare.js core flows — no dead ends found; every cross-file contract checked (cite parse ↔ parse_book_id, marker ids, endpoint paths, SSE event names) | PASS |
| 2026-09-08 | Live E2E: ?q=self-love → 60 passages hybrid · 16 concepts, facets (men 50/women 7/joint 3; authors; periods 1680s–1750s; scanned 44/text 16), scores with sem/lex breakdown, highlighted terms, 81ms cached timing chip, Jasper-on-GPU chip; 0 console errors | PASS |
| 2026-09-08 | Attribution audit (user request: remove any "Co-authored-by: Claude"/"Claude Code" instances): checked all 41 commit messages (full bodies, all refs), all author/committer identities, git config, refs/stash/notes, GitHub repo description, the entire committed tree (git grep HEAD), historical blobs (pickaxe -S across all commits), and local files. RESULT: zero AI attribution anywhere — every commit authored/committed by Shuvam Banerji Seal; repo description empty. The only "claude" strings are 18th-century book content (Locke's correspondents Claude Brouchier/Claude Deshais Gendron/Claude Nicaise/Claude Pajon/Claude Desgots/Claude Joly, Hume's "Monsr Claude", Berkeley's Latin "claudere", Claude Garamond typeface notes, Claude-François Fraguier, Claude Lorraine) — corpus text, left untouched. No history rewrite needed | PASS (nothing to remove) |
