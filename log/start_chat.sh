#!/bin/bash
# Concept Atlas chat / accounts / session store.
# Talks to the local vLLM server; the UI reaches it through :8788.
cd /store/shuvam/BMoral
export UV_CACHE_DIR=/store/shuvam/uv-cache
exec .venv/bin/python tools/atlas_chat_server.py \
  --port 8793 \
  --vllm "${ATLAS_VLLM:-http://localhost:8000/v1}" \
  --model "${ATLAS_MODEL:-Qwen3.8-27B-TURBO}"
