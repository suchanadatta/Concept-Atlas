#!/bin/bash
export UV_CACHE_DIR=/store/shuvam/uv-cache UV_PYTHON_INSTALL_DIR=/store/shuvam/uv-python
export DOCTR_CACHE_DIR=/store/shuvam/BMoral/models/doctr
cd /store/shuvam/BMoral
.venv/bin/python tools/word_map.py --jsonl outputs/corpus --resume --batch-size 16 --log-level INFO
echo "=== WORD MAP RESUME DONE $(date) ==="
