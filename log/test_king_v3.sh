#!/bin/bash
export UV_CACHE_DIR=/store/shuvam/uv-cache UV_PYTHON_INSTALL_DIR=/store/shuvam/uv-python
export CUDA_HOME=/usr/local/cuda-13.3 PATH=/usr/local/cuda-13.3/bin:$PATH
export DOCTR_CACHE_DIR=/store/shuvam/BMoral/models/doctr
cd /store/shuvam/BMoral
echo "=== parse King 1st ed (201 pages, 300dpi, JSONL v3) ==="
.venv/bin/glmocr parse "data/BMoral_pdf_collection/King, William (1650–1729)/King An Essay on the Origin of Evil 1st ed 1731 (part 1).pdf" --output outputs/test_king_v3 --config config.yaml 2>&1 | tail -1
echo "=== word map ==="
.venv/bin/python tools/word_map.py --jsonl outputs/test_king_v3 --log-level INFO 2>&1 | grep -E "pages|DONE" | tail -2
echo "=== validate ==="
.venv/bin/python tools/validate_jsonl.py --jsonl outputs/test_king_v3 2>&1 | grep -vE "FutureWarning|warnings.warn" | tail -3
echo "=== KING TEST DONE ==="
