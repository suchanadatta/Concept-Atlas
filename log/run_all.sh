#!/bin/bash
# Full corpus pipeline: parse (JSONL v3) -> word map (docTR) -> validate.
# Usage: setsid nohup ./log/run_all.sh > log/run_all.log 2>&1 &
set -e
export UV_CACHE_DIR=/store/shuvam/uv-cache UV_PYTHON_INSTALL_DIR=/store/shuvam/uv-python
export CUDA_HOME=/usr/local/cuda-13.3 PATH=/usr/local/cuda-13.3/bin:$PATH
export DOCTR_CACHE_DIR=/store/shuvam/BMoral/models/doctr
cd /store/shuvam/BMoral

echo "=== [1/3] PARSE corpus (61 books, 300dpi, JSONL v3) $(date) ==="
.venv/bin/glmocr parse data/BMoral_pdf_collection \
    --output outputs/corpus --config config.yaml --log-level INFO \
    > log/corpus.log 2>&1
echo "=== parse done $(date); jsonl count: $(find outputs/corpus -name '*.pages.jsonl' | wc -l) ==="

echo "=== [2/3] WORD MAP (docTR word geometry) $(date) ==="
.venv/bin/python tools/word_map.py --jsonl outputs/corpus --batch-size 16 \
    --log-level INFO > log/word_map.log 2>&1

echo "=== [3/3] VALIDATE $(date) ==="
.venv/bin/python tools/validate_jsonl.py --jsonl outputs/corpus --strict \
    > log/validate.log 2>&1 || true

echo "=== ALL DONE $(date) ==="
tail -30 log/validate.log
