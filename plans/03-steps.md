# 03 — Steps (all completed 2026-08-13)

STEP 1: Inspect workspace
  Input: /store/shuvam/BMoral — Output: env facts (2.1 GB zip present, 488G free)
  Test: ls -la + df — PASS

STEP 2: Create plans/ skeleton
  Test: files written — PASS

STEP 3: Clone repo
  Input: https://github.com/baidu/Unlimited-OCR.git → /store/shuvam/BMoral/Unlimited-OCR
  Test: git log (13 commits), git status (clean, up-to-date), du -sh (181M) — PASS

STEP 4: Read repo files (README, infer.py, CONTRIBUTING, LICENSE, .gitignore)
  Test: full reads — PASS

STEP 5: Extract + read paper (pdftotext → /tmp/opencode/Unlimited-OCR-paper.txt, 736 lines)
  Test: wc -l, full read — PASS (model cannot read PDF binary; text extraction used)

STEP 6: Unpack wheel + read Unlimited-OCR code (model, config, logit processor, swa_evict_floor)
  Test: unzip OK (3073 files); grep/sed reads — PASS

STEP 7: Verify external claims (GitHub API, HF API, HF config.json, arXiv)
  Test: curl responses parsed — PASS (sliding_window_size=128 confirmed on deployed model)

STEP 8: Write plans/ + final summary
  Test: files exist, todo audit — PASS

## Rev 0 — initial plan, executed as specified with no reversals.
## Rev 1 — GLM-OCR clone + study (2026-08-13)
STEP 9: Verify zai-org/GLM-OCR via GitHub API — PASS (Apache-2.0, 100 MB, 7.3k★)
STEP 10: Clone → /store/shuvam/BMoral/GLM-OCR — PASS (210 MB, 360 files, 110 commits, v0.1.5)
STEP 11: Read README (en/zh), pyproject.toml — PASS
STEP 12: Read glmocr/ package (api.py, pipeline.py, ocr_client.py, layout_detector.py, structure) — PASS
STEP 13: Verify HF model + config.json + arXiv 2603.10910 — PASS (sliding/architecture facts confirmed)
STEP 14: Survey examples/, skills/, apps/, CI — PASS
STEP 15: Append findings to plans/ — PASS

## Rev 2 — OCR setup + corpus parse (2026-08-13)
STEP 16: Strategy validation — Unlimited-OCR+GLM-OCR incompatible (architectures/tokenizers differ); adopted GLM-OCR self-hosted path | PASS
STEP 17: Hardware check — A100 80GB, driver 610/CUDA 13.3, 24 CPU, 125GB RAM | PASS
STEP 18: uv venv (Python 3.12.8, .venv) — blocked once by /store/uv perms (gautam-owned); fixed via UV_CACHE_DIR/UV_PYTHON_INSTALL_DIR redirect | PASS
STEP 19: Background install: vllm 0.27.1, transformers 5.15.0, torch 2.13.0+cu130, glmocr 0.1.5 (local -e GLM-OCR[all]) | PASS (log/uv-install.log)
STEP 20: vLLM server launch — FAIL 1: MTP spec-config → eagle loader key mismatch (model.layers.16.* vs model.language_model.layers.16.*); dropped MTP. FAIL 2: flashinfer JIT nvcc CUDA 11.5 → set CUDA_HOME=/usr/local/cuda-13.3 + PATH; quarantined stale flashinfer cache to /tmp/opencode/. Server UP on :8080 (~220s boot) | PASS
STEP 21: Raw smoke test — Warburton page 1 via /v1/chat/completions, 200, 387 tokens, correct 18th-c OCR | PASS
STEP 22: SDK pipeline test — full parse of 8-page Warburton PDF (layout+region OCR+format), 7.87s, markdown+json+layout_vis | PASS
STEP 23: Corpus batch launched (setsid nohup log/parse_corpus.sh → log/corpus.log), 61 files, ETA ~2h51m, 2,203 requests by t+3.5min | RUNNING

## Rev 3 — JSONL page-level output + highlight-ready mapping (2026-08-13)
DESIGN (JSONL, one line per page, per book):
  book_id, book_title, source, format_version
  page_index (0-based), page_number (1-based), total_pages
  dpi, page_size_px, page_rect_pts (PDF points via fitz)
  blocks[]: id, label, text, bbox_2d (normalized 0-1000, model-native),
            bbox_pts (PDF points, computed: norm/1000 * page_rect), polygon_2d
  text: page text in reading order (for retrieval/embedding)
HIGHLIGHT MAPPING (for later software): phrase -> block.text match ->
  block.bbox_pts -> fitz page.draw_rect (points == PDF units). Verified programmatically.
NOTE: granularity is block-level (GLM-OCR outputs region boxes, not word boxes).

## Rev 4 — Output audit, OCR improvements, 300 dpi (2026-08-13)
AUDIT (24 pre-parsed books, 7.07M chars): truncation ~0 (4 regions); found 2-up interleaving bug.
FIX 1: two-up reading order — layout_postprocess_utils.py reorders regions left-half-first (75% cluster rule), fixing markdown/json/jsonl together (verified: King p.15 reads left page then right page).
FIX 2: JSONL v2 — sheet_layout/sheet_half/book_page_number_estimate/printed_page_number (arabic+roman from running heads; verified: right half of King p.15 → "XV"/15).
FIX 3: null-content crash ('NoneType' .strip) — region.get("content") or "".
FIX 4: convention formula corrected to left_odd_1based (left=2i+1, right=2i+2).
DPI: 200→300 per user (A/B test showed no diff on one page; quality-first choice).
RELAUNCHED full corpus (61 books, 300 dpi) in background — ETA ~4-6h.
OPEN: long-s (ſ) renders as "f" (model-level); word-level boxes not available (block-level only).

## Rev 5 — Codebase overhaul + JSONL v3 + word mapping (2026-08-14)
- Quarantined all old outputs to .rigor-trash/outputs-20260814 (5.4G), fresh outputs/; GPU free
- Removed abandoned paddle/paddleocr stack from venv
- ruff F/E7/E9 on SDK: 0 real bugs; style rules (UP/RUF/I) left to upstream typing
- Deprecated `fitz` import replaced with `pymupdf` across glmocr SDK + apps/backend (verified -W error clean)
- JSONL v3: per-page sheet_layout (resolve_sheet_modes: strict/loose/none evidence + book mode single/two_up/mixed + running book-page counter + _is_wide_single for full-width pages in two-up books)
- Zones: header/footer/footnote/page_number/title/reference/table/formula/figure/body; config label_task_mapping now OCRs header/footer/footnote/number/aside_text/reference (abandon only images)
- printed_page_number extraction: number-zone blocks (digits/roman) + leading/trailing folio in running heads; _sanitize_printed_numbers outlier rejection via consistent-offset model (verified: Warburton 182/184/185/186 kept, 1888/2023 rejected)
- Word mapping: glmocr/utils/word_mapping.py (tokenize, visual-confusion edit distance f/s+1/l/I+0/O+vowel+rn+mn+un+vy+ij+ce+dt+bh, global DP alignment with fragment concatenation 1-3, box clamp to block)
- Geometry provider: docTR fast_base + crnn_mobilenet_v3_small (word boxes), DOCTR_CACHE_DIR=models/doctr, weights md5-verified... (md5 not published; sizes match, loaded OK)
- tools/word_map.py: additive JSONL enrichment (words[] with bbox_pts + char offsets + word_coverage), batched docTR predict (fixed double-predict bug)
- tools/validate_jsonl.py: schema/geometry/offsets/page-number/monotonicity checks
- Verified: Warburton parse+wordmap+validate = 0 problems, 61% word coverage; phrase 'Cumaean' highlighted on PDF from mappings alone
- King v3: writer fixed (sanitizer KeyError on sheet_pages), 201 lines mode=two_up monotone numbering
- Word-pass throughput: ~4.9s/page batched (fast_base+mobilenet) => ~15h for 11k pages (background)

## Rev 6 — Full validation + corpus launch (2026-08-14)
- King two-up end-to-end test: parse + wordmap + validate ALL GREEN (201 pages, 57,471 words, 58.2% coverage, 0 problems)
- Fixed: _sanitize_printed_numbers KeyError (two-up seq tuple bug); _is_wide_single tightened (>850 width for full-width singles in two-up books)
- Word-map perf: length-band pruning of DP candidates; tool ~3.9s/page single, ~7.9s/page two-up
- tools/word_map.py single-predict fix (was double-inferencing)
- log/run_all.sh orchestration created (parse -> word map -> validate)
- FULL CORPUS PIPELINE LAUNCHED 14:49 IST: 61 books parse (300dpi JSONL v3) -> docTR word map -> validate; ETA word pass ~15-24h background

## Rev 7 — Paragraph pass + full-set download (2026-08-22)
- glmocr/utils/word_mapping.py: split_block_paragraphs() — blank-line split, word rebasing, bbox union
- tools/add_paragraphs.py applied to all 61 books: 91,673 paragraphs, 565 blocks split; validate 0 problems
- gdown installed; Drive folder downloading in background → data/drive_pdfs/collection/pdf/ (AUTHOR_YEAR_TITLE naming; includes books beyond current corpus e.g. BALFOUR_1753); 9 PDFs/686MB so far
- Pending: OCR of new set under 10GB VRAM cap (vLLM gpu-mem-util ≤0.10 or sequenced runs)
