#!/bin/bash
# Wait for GPU to be free (<5GB used), then build the Jasper index.
# Launch: setsid nohup ./log/build_jasper_index_when_gpu_free.sh > log/jasper_index_build.log 2>&1 &
export UV_CACHE_DIR=/store/shuvam/uv-cache
cd /store/shuvam/BMoral
while true; do
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)
  if [ "$used" -lt 5000 ]; then
    echo "GPU free (${used}MB) — starting index build $(date)"
    .venv/bin/python tools/build_jasper_index.py --device cuda --batch 128
    echo "INDEX BUILD DONE $(date)"
    # start the semantic search server too
    setsid nohup .venv/bin/python tools/jasper_search_server.py --port 8790 --device cuda > log/jasper_server.log 2>&1 < /dev/null &
    echo "semantic search server launched on :8790"
    exit 0
  fi
  sleep 300
done
