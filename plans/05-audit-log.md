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
