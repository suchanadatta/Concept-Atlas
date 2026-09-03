#!/bin/bash
export UV_CACHE_DIR=/store/shuvam/uv-cache UV_PYTHON_INSTALL_DIR=/store/shuvam/uv-python
cd /store/shuvam/BMoral
uv pip install --python .venv/bin/python paddlepaddle-gpu paddleocr 2>&1 || {
  echo "GPU paddle failed, falling back to CPU"
  uv pip install --python .venv/bin/python paddlepaddle paddleocr
}
echo "=== PADDLE INSTALL DONE ==="
