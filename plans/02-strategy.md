# 02 — Strategy

## Chosen strategy (study-only task)
1. Clone repo (full clone; 181 MB working tree).
2. Read all repo files (README, infer.py, LICENSE, CONTRIBUTING, .gitignore).
3. Extract paper text via pdftotext (model cannot ingest PDF binary) and read fully.
4. Unzip wheel to /tmp/opencode/sglang-wheel/ and read the Unlimited-OCR-specific code:
   - sglang/srt/models/unlimited_ocr.py (model)
   - sglang/srt/configs/unlimited_ocr.py (processor + configs)
   - sglang/srt/sampling/custom_logit_processor.py (no-repeat-ngram)
   - swa_evict_floor usage across scheduler/chunk_cache/schedule_batch
5. Verify external claims live: GitHub API, HF model API, HF config.json, arXiv API.
6. Write findings to plans/ + present summary.

## Alternatives rejected
- Shallow clone: rejected — full clone cheap (181 MB) and more faithful to "clone this repo".
- Downloading HF weights (6 GB) to inspect modeling_unlimitedocr.py: rejected — beyond "study the repo" scope; HF-side implementation noted as open item.
- Skipping wheel analysis: rejected — the wheel is the only actual model code in the repo.
