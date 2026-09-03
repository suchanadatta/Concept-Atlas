#!/bin/bash
# Re-enrichment chain after filter_word_order fix (height-adaptive bands).
# The old absolute thresholds mass-dropped line-initial words on tightly-
# leaded verse/small-type sections (~50% loss on affected books). This chain
# re-runs docTR + alignment + paragraphs + filters over the CANONICAL 68
# books (stale nested tree already quarantined), then validates.
# If interrupted: relaunch with RESUME=1 to skip already-re-enriched files.
set -e
export UV_CACHE_DIR=/store/shuvam/uv-cache UV_PYTHON_INSTALL_DIR=/store/shuvam/uv-python
export CUDA_HOME=/usr/local/cuda-13.3 PATH=/usr/local/cuda-13.3/bin:$PATH
export DOCTR_CACHE_DIR=/store/shuvam/BMoral/models/doctr
cd /store/shuvam/BMoral

OUT=outputs/full_set
RESUME_FLAG=""
if [ "$RESUME" = "1" ]; then RESUME_FLAG="--resume"; fi

echo "=== [1/5] WORD MAP re-run (fixed filter) $(date) ==="
.venv/bin/python tools/word_map.py --jsonl $OUT $RESUME_FLAG --batch-size 16 \
    --log-level INFO > log/full_set_wordmap_v2.log 2>&1
tail -2 log/full_set_wordmap_v2.log

echo "=== [2/5] PARAGRAPH PASS (rebuild from new words) $(date) ==="
.venv/bin/python tools/add_paragraphs.py --output $OUT

echo "=== [3/5] REFILTER $(date) ==="
.venv/bin/python tools/refilter_words.py --output $OUT

echo "=== [4/5] VALIDATE strict $(date) ==="
.venv/bin/python tools/validate_jsonl.py --jsonl $OUT --strict \
    > log/full_set_validate_v2.log 2>&1 || true
tail -3 log/full_set_validate_v2.log

echo "=== [5/5] QUALITY CHECKS Q1-Q10 $(date) ==="
.venv/bin/python tools/quality_checks.py --output $OUT \
    --books data/full_set_pdfs/pdf > log/fullset_quality_v2.log 2>&1 || true
tail -14 log/fullset_quality_v2.log

echo "=== RE-ENRICH DONE $(date) ==="
