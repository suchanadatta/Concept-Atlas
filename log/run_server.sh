#!/bin/bash
# vLLM server launcher for GLM-OCR (self-hosted)
# MTP speculative disabled (vllm 0.27.1 eagle loader key mismatch: model.layers.16.* vs model.language_model.layers.16.*)
# CUDA_HOME forced to 13.3: /usr/bin/nvcc is CUDA 11.5 -> flashinfer JIT fails ("CUDA below 12 not supported")
export UV_CACHE_DIR=/store/shuvam/uv-cache UV_PYTHON_INSTALL_DIR=/store/shuvam/uv-python
export CUDA_HOME=/usr/local/cuda-13.3
export PATH=$CUDA_HOME/bin:$PATH
cd /store/shuvam/BMoral

exec .venv/bin/vllm serve /store/shuvam/BMoral/models/GLM-OCR \
    --port 8080 \
    --served-model-name glm-ocr \
    --max-model-len 32768 \
    --gpu-memory-utilization 0.85 \
    --host 0.0.0.0
