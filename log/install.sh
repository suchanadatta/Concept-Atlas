#!/bin/bash
export UV_CACHE_DIR=/store/shuvam/uv-cache UV_PYTHON_INSTALL_DIR=/store/shuvam/uv-python
cd /store/shuvam/BMoral
echo "=== [1/3] vllm ==="
uv pip install --python .venv/bin/python vllm || exit 1
echo "=== [2/3] transformers >=5.3 ==="
uv pip install --python .venv/bin/python "transformers>=5.3.0" || exit 1
echo "=== [3/3] glmocr[all] from local source ==="
uv pip install --python .venv/bin/python -e "GLM-OCR[all]" || exit 1
echo "=== ALL INSTALLS DONE ==="
