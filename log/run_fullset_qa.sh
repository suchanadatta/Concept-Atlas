#!/bin/bash
# Full-set QA: quality_checks (Q1-Q10, CPU-only; Q11 skipped — docTR needs GPU
# which is shared with user training) + audit_corpus --require-words.
export UV_CACHE_DIR=/store/shuvam/uv-cache UV_PYTHON_INSTALL_DIR=/store/shuvam/uv-python
cd /store/shuvam/BMoral

echo "=== FULLSET QUALITY CHECKS (Q1-Q10) $(date) ==="
.venv/bin/python tools/quality_checks.py \
    --output outputs/full_set \
    --books data/full_set_pdfs/pdf \
    > log/fullset_quality.log 2>&1
echo "quality exit: $?"
tail -14 log/fullset_quality.log

echo "=== FULLSET AUDIT (--require-words) $(date) ==="
.venv/bin/python tools/audit_corpus.py \
    --data data/full_set_pdfs/pdf \
    --output outputs/full_set \
    --require-words \
    --parse-log log/full_set_parse.log \
    > log/fullset_audit.log 2>&1
echo "audit exit: $?"
tail -4 log/fullset_audit.log

echo "=== FULLSET QA DONE $(date) ==="
