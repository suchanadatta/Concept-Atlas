#!/bin/bash
# Corpus re-enrichment chain (same fix as full set): fixed height-adaptive
# filter_word_order recovers verse/small-type words the old absolute bands
# mass-dropped (Norris Spiritual Counsel: stored 20% -> fresh 51.6%).
# Run AFTER log/run_reenrich_fullset.sh completes.
set -e
export UV_CACHE_DIR=/store/shuvam/uv-cache UV_PYTHON_INSTALL_DIR=/store/shuvam/uv-python
export CUDA_HOME=/usr/local/cuda-13.3 PATH=/usr/local/cuda-13.3/bin:$PATH
export DOCTR_CACHE_DIR=/store/shuvam/BMoral/models/doctr
cd /store/shuvam/BMoral

OUT=outputs/corpus
RESUME_FLAG=""
if [ "$RESUME" = "1" ]; then RESUME_FLAG="--resume"; fi

echo "=== [1/5] CORPUS WORD MAP re-run (fixed filter) $(date) ==="
.venv/bin/python tools/word_map.py --jsonl $OUT $RESUME_FLAG --batch-size 16 \
    --log-level INFO > log/corpus_wordmap_v2.log 2>&1
tail -2 log/corpus_wordmap_v2.log

echo "=== [2/5] PARAGRAPH PASS $(date) ==="
.venv/bin/python tools/add_paragraphs.py --output $OUT

echo "=== [3/5] REFILTER $(date) ==="
.venv/bin/python tools/refilter_words.py --output $OUT

echo "=== [4/5] VALIDATE strict $(date) ==="
.venv/bin/python tools/validate_jsonl.py --jsonl $OUT --strict \
    > log/corpus_validate_v2.log 2>&1 || true
tail -3 log/corpus_validate_v2.log

echo "=== [5/5] QUALITY CHECKS $(date) ==="
.venv/bin/python tools/quality_checks.py --output $OUT \
    --books data/BMoral_pdf_collection > log/corpus_quality_v2.log 2>&1 || true
tail -14 log/corpus_quality_v2.log

echo "=== CORPUS RE-ENRICH DONE $(date) ==="
