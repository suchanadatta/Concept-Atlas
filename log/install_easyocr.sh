#!/bin/bash
export UV_CACHE_DIR=/store/shuvam/uv-cache UV_PYTHON_INSTALL_DIR=/store/shuvam/uv-python
cd /store/shuvam/BMoral
uv pip install --python .venv/bin/python easyocr
echo "=== EASYOCR INSTALL DONE ==="
