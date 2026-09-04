#!/usr/bin/env bash
# Bootstrap a fresh clone into a working search engine.
#
#   bash scripts/bootstrap.sh
#
# Downloads the Jasper embedding model, builds the semantic index from the
# committed OCR text, and starts both servers.
set -e
cd "$(dirname "$0")/.."
echo "=== 1/4 Python env (uv) ==="
if [ ! -d .venv ]; then
  uv venv --python 3.12
fi
uv pip install -r pyproject.toml --python .venv/bin/python

echo "=== 2/4 Jasper model weights (~1.2 GB, one-time) ==="
if [ ! -f models/Jasper-Token-Compression-600M/model.safetensors ]; then
  .venv/bin/python - << 'EOF'
from huggingface_hub import snapshot_download
snapshot_download(
    "infgrad/Jasper-Token-Compression-600M",
    local_dir="models/Jasper-Token-Compression-600M",
    allow_patterns=["*.json", "*.txt", "*.safetensors", "*.py", "*.md"],
)
print("model downloaded")
EOF
else
  echo "already present"
fi

echo "=== 3/4 Semantic index (embeds 132k paragraphs; needs GPU ~10 min) ==="
if [ ! -f models/jasper_index/embeddings.npy ]; then
  .venv/bin/python tools/build_jasper_index.py --device "${BMORAL_DEVICE:-cuda}" --batch 128
else
  echo "embeddings already built"
fi
if [ ! -f models/jasper_index/concepts.npy ]; then
  .venv/bin/python tools/build_concept_vectors.py "${BMORAL_DEVICE:-cuda}"
else
  echo "concept vectors already built"
fi

echo "=== 4/4 Start servers ==="
echo "  semantic backend (:8790)  — .venv/bin/python tools/jasper_search_server.py --device cuda"
echo "  UI (:8788)               — cd 'Concept Maps/graph-ui' && ./start.sh"
echo ""
echo "Done. Open http://localhost:8788"
