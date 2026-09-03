# CONTINUATION_STATE.md
(updated Tue Aug 25 16:30 IST)

## Session Summary
| Field | Value |
|-------|-------|
| Phase | V3 SUPERVISOR RUNNING — two root causes fixed (filter + sorter), full pipeline re-running crash-resumably |
| Done | Fullset v2 complete (all checks pass except Q8 45.1%); root cause #2 found+fixed; supervisor + cron auto-resume |
| Errors remaining | none blocking — v3 pass will lift verse-heavy books to full recovery |
| Audit status | fixes unit+e2e verified; v3 in flight |

## TWO root causes fixed (both = absolute thresholds vs tight leading)
1. filter_word_order (FIXED earlier): adaptive y_tol/x_tol from median box height
2. sort_words_reading_order (FOUND via transitions dump, FIXED now): provider-side
   sorter's absolute line_tol=8 INTERLEAVED adjacent verse lines (pitch ~6.7 < 8)
   into z-order BEFORE alignment → monotone DP paired tokens to zigzag boxes →
   filter then correctly dropped them (~27% of matches on verse-heavy books).
   Fix: line_tol = max(4, 0.55*med_h). Unit tests: verse-no-interleave PASS.
   Evidence: drops were 100% X-REG within correctly-separated lines; mixed-height
   hypothesis REJECTED (0 drops in mixed blocks).

## V3 SUPERVISOR (running since 16:25, TS=2026-08-25 16:25:55)
log/run_v3_supervisor.sh: fullset wordmap(v3)→paragraphs→refilter→validate+quality
→ corpus same → finalize(archive rebuild). Crash-resume: word_map --older-than TS
skips books with fresh mtimes; state in plans/v3_state.txt.
CRON @REBOOT ARMED: relaunches supervisor 2min after boot automatically.
Progress: grep -c coverage= log/full_set_wordmap_v3.log (/68) then corpus_wordmap_v3.log (/61)
Supervisor log: log/v3_supervisor.log

## Fullset v2 results (superseded by v3 but instructive)
Q1-Q7,Q9,Q10 PASS · Q4 PASS (index exemption) · validate 68 files 0 problems ·
tiling perfect 1,906,851 words (+163k vs v1) · Q8 45.1% agg (worst TURNBULL 37,
ASTELL 38 — limited by sorter bug #2, v3 will lift to ~54-62%)

## Also done this session
- Q4 fix verified live: "0 flagged | 2 index/reference pages (correct OCR, exempt)"
- parseq negative result (+0.8pts); bench_reco.py + diag tools kept in tools/
- TXT matching honest artifact (2 exact pairs; content-matching needed)
- Text-completeness audit: 27,105 pages, 99.4% carry text; empties = blank scans
  (148 corpus pages all zero-block) + 15 plates

## GPU constraint
v3 owns GPU. If user training returns: kill word_map pid; cron/supervisor resumes.

## Next steps after V3 completes
1. Verify v3 logs: both VERDICTs ALL PASS (Q8 should clear 50% bar)
2. python tools/coverage_diff.py (full set); extend for corpus
3. Archive rebuilt by finalize stage automatically
4. Optional: search demo / content-based TXT pairing

## Continuation Prompt Hints
Check tail log/v3_supervisor.log for current stage. When "V3 SUPERVISOR ALL DONE"
appears: verify quality_v3 verdicts both trees + finalize.log archive rebuild +
coverage_diff numbers, update this file.

## ROOT CAUSE + FIX (the big one, 2026-08-25)
filter_word_order used absolute bands (8y/5x normalized units). Tightly-leaded
verse/small-type sections (word h≈5-9u, line pitch ≈6u) merged into one false
"line" → every line-initial word dropped as x-regression (~50% loss on
verse-heavy books). Evidence: drops were 100% X-type (dropY=0); ASTELL_1704
stored 26% vs raw match 54%; Norris(corpus) stored 20% vs fresh 51.6%.
FIX in GLM-OCR/glmocr/utils/word_mapping.py:
  y_tol = max(4, 0.55*med_h); x_tol = max(5, 0.60*med_h)   # median box height
MIRRORED in tools/quality_checks.py q7_word_order (keep-in-sync).
VERIFIED: verse fixture 24/24 kept (was ~50% dropped); body unchanged; y-up
intruder dropped; E2E same-10-pages stored-equiv 54.1% vs 26.2%.

## Also this session
- Q4: digit-dominated pages (>0.25; indexes measure 0.35-0.86, prose max 0.03)
  classified index/reference → exempt from garbage FAIL
- parseq bench: +0.8pts vs crnn_small → reco NOT the bottleneck (closes step)
- audit_corpus plate rule: chrome-zone captions OK (GWINNETT frontispiece)
- full_set_ocr.tar.xz rebuilt CLEAN: 55MB = 68 books × {pages.jsonl,json,
  _model.json,md}; old 74MB archive quarantined .rigor-trash/20260825-045531
- Stale nested tree outputs/full_set/collection/ quarantined .rigor-trash
  (<ts>-stale-collection-tree) — rglob now sees exactly the canonical 68
- data/txt_books/: 68 TXT transcriptions (Drive folder) for ground truth

## RUNNING NOW (GPU was free at launch; ~10h + ~7h chained)
1. log/run_reenrich_fullset.sh: word_map v2 over canonical 68 (fp16 det16/
   reco64, ~2.4s/page) → add_paragraphs → refilter → validate_v2 → quality_v2.
   Logs: log/run_reenrich.log, log/full_set_wordmap_v2.log
2. Watcher then runs log/run_reenrich_corpus.sh automatically (~+7h)
3. Second watcher runs log/finalize_after_reenrich.sh after corpus completes:
   verifies v2 validate+quality verdicts and REBUILDS full_set_ocr.tar.xz
   from refreshed data → log/finalize.log
4. If interrupted: RESUME=1 ./log/run_reenrich_fullset.sh  (and/or corpus;
   resume skips files already re-enriched)
5. If user training returns and memory pressure appears: kill word_map pid,
   resume later — per-file atomic writes keep state consistent

## Expected when chains finish
Full set aggregate coverage ~41% → ~55%+ (floors rise: ASTELL 26→~54,
TURNBULL 27→~50s). Corpus 44.9% → ~55%+. Q1-Q10 expected ALL PASS.
CANARY CONFIRMED 06:05: ASTELL_1704 re-enriched coverage=54.3% (was 25.5%
stored) — production-scale proof of the filter fix. Early books: ANON 60.6%,
ASTELL-and-NORRIS 60.9%.

## Next steps after chains complete
1. Check validate_v2 = 0 problems; quality_v2 verdict ALL PASS; spot-check a
   verse page's words[] density vs old
2. Regenerate full_set_ocr.tar.xz from re-enriched JSONLs
3. Search-engine / paragraph-highlight demo (TXT ground truth ready)

## Verification tooling ready (prepped 06:20)
- plans/coverage_snapshot_fullset.json  — BEFORE snapshot, all 68 books
- plans/coverage_snapshot_corpus.json   — BEFORE snapshot, all 61 books
- tools/coverage_diff.py                — before/after table + mean delta
  Run when chains finish: python tools/coverage_diff.py (full set)
  (corpus diff: point glob at outputs/corpus or extend arg)

## TXT ground truth (finding, 06:40)
Name-based TXT<->JSONL matching is UNRELIABLE (different edition/collected-
works naming; cross-author false pairs). plans/txt_jsonl_pairs.json now holds
only 2 exact-name matches + explicit warning. Real pairing needs CONTENT
matching (first-paragraph similarity) at eval time — do not trust name pairs.

## Continuation Prompt Hints
Check `grep -c coverage= log/full_set_wordmap_v2.log` (progress /68) and tail
log/run_reenrich.log for stage. When "CORPUS RE-ENRICH DONE" appears in
log/run_reenrich_corpus_wrapper.log: verify v2 validate+quality logs, rebuild
archive, update this file, then build the search demo.
