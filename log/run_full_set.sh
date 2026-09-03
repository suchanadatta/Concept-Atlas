#!/bin/bash
# Ingest pipeline for the newly downloaded Drive PDF set.
# Respects the 10GB VRAM cap while user training runs:
#   vLLM gpu-memory-utilization=0.10 (8GB: ~3GB weights + ~5GB KV)
#   docTR word map (~2GB) runs AFTER parse completes (sequenced, not parallel)
# Usage: setsid nohup ./log/run_full_set.sh > log/run_full_set.log 2>&1 &
set -e
export UV_CACHE_DIR=/store/shuvam/uv-cache UV_PYTHON_INSTALL_DIR=/store/shuvam/uv-python
export CUDA_HOME=/usr/local/cuda-13.3 PATH=/usr/local/cuda-13.3/bin:$PATH
export DOCTR_CACHE_DIR=/store/shuvam/BMoral/models/doctr
cd /store/shuvam/BMoral

DATA=data/drive_pdfs
OUT=outputs/full_set

echo "=== [0/4] waiting for gdown to finish $(date) ==="
while pgrep -f "gdown" > /dev/null 2>&1; do sleep 120; done
N_PDF=$(find $DATA -name "*.pdf" | wc -l)
echo "downloaded PDFs: $N_PDF"

echo "=== [1/4] PARSE full set (300dpi, JSONL v3, LOW-VRAM server) $(date) ==="
# low-memory vLLM: 8GB cap (fits the 10GB budget beside training)
.venv/bin/vllm serve /store/shuvam/BMoral/models/GLM-OCR \
    --port 8080 \
    --served-model-name glm-ocr \
    --max-model-len 16384 \
    --gpu-memory-utilization 0.10 \
    --host 127.0.0.1 > log/vllm_lowmem.log 2>&1 &
VLLM_PID=$!
for i in $(seq 1 60); do sleep 10; c=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/health || true); [ "$c" = "200" ] && break; done
curl -s -o /dev/null -w "server health: %{http_code}\n" http://127.0.0.1:8080/health

.venv/bin/glmocr parse $DATA --output $OUT --config config.yaml --log-level INFO \
    > log/full_set_parse.log 2>&1
echo "parse done: $(find $OUT -name '*.pages.jsonl' | wc -l) jsonl"

kill $VLLM_PID 2>/dev/null || true
sleep 15

echo "=== [2/4] PARAGRAPH PASS $(date) ==="
.venv/bin/python tools/add_paragraphs.py --output $OUT

echo "=== [3/4] WORD MAP (docTR, GPU now free of vLLM) $(date) ==="
.venv/bin/python tools/word_map.py --jsonl $OUT --resume --batch-size 16 \
    --log-level INFO > log/full_set_wordmap.log 2>&1

echo "=== [4/4] VALIDATE + AUDIT $(date) ==="
.venv/bin/python tools/refilter_words.py --output $OUT || true
.venv/bin/python tools/validate_jsonl.py --jsonl $OUT --strict > log/full_set_validate.log 2>&1 || true
tail -5 log/full_set_validate.log
echo "=== FULL SET INGEST DONE $(date) ==="
