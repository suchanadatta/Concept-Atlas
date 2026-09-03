#!/bin/bash
# Full pipeline: parse ALL 68 books → paragraphs → word map → validate
set -e
export UV_CACHE_DIR=/store/shuvam/uv-cache UV_PYTHON_INSTALL_DIR=/store/shuvam/uv-python
export CUDA_HOME=/usr/local/cuda-13.3 PATH=/usr/local/cuda-13.3/bin:$PATH
export DOCTR_CACHE_DIR=/store/shuvam/BMoral/models/doctr
cd /store/shuvam/BMoral

DATA=data/full_set_pdfs/pdf
OUT=outputs/full_set

echo "=== [0/5] starting vLLM (gpu-mem-util 0.08 for training coexistence) $(date) ==="
.venv/bin/vllm serve /store/shuvam/BMoral/models/GLM-OCR \
    --port 8080 --served-model-name glm-ocr \
    --max-model-len 16384 --gpu-memory-utilization 0.08 \
    --host 127.0.0.1 > log/vllm_fullset.log 2>&1 &
VLLM_PID=$!
for i in $(seq 1 90); do sleep 10; c=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/health || true); [ "$c" = "200" ] && break; done
curl -s -o /dev/null -w "vLLM health: %{http_code}\n" http://127.0.0.1:8080/health

echo "=== [1/5] PARSE all 68 books $(date) ==="
.venv/bin/glmocr parse $DATA --output $OUT --config config.yaml --log-level INFO \
    > log/full_set_parse.log 2>&1
N=$(find $OUT -name "*.pages.jsonl" | wc -l)
echo "parsed: $N jsonl files"

echo "=== [2/5] stop vLLM $(date) ==="
kill $VLLM_PID 2>/dev/null || true; sleep 10

echo "=== [3/5] PARAGRAPH PASS $(date) ==="
.venv/bin/python tools/add_paragraphs.py --output $OUT

echo "=== [4/5] WORD MAP $(date) ==="
.venv/bin/python tools/word_map.py --jsonl $OUT --batch-size 16 --log-level INFO \
    > log/full_set_wordmap.log 2>&1

echo "=== [5/5] REFILTER + VALIDATE $(date) ==="
.venv/bin/python tools/refilter_words.py --output $OUT || true
.venv/bin/python tools/validate_jsonl.py --jsonl $OUT --strict > log/full_set_validate.log 2>&1 || true
tail -3 log/full_set_validate.log

echo "=== FULL SET DONE $(date): $N books, $(find $OUT -name '*.pages.jsonl' | wc -l) jsonl ==="
