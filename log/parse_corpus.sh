#!/bin/bash
export UV_CACHE_DIR=/store/shuvam/uv-cache UV_PYTHON_INSTALL_DIR=/store/shuvam/uv-python
export CUDA_HOME=/usr/local/cuda-13.3
export PATH=$CUDA_HOME/bin:$PATH
cd /store/shuvam/BMoral
exec .venv/bin/glmocr parse data/BMoral_pdf_collection \
    --output outputs/corpus \
    --config config.yaml \
    --log-level INFO
