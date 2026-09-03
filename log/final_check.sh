#!/bin/bash
# Final verification: run AFTER log/run_all.sh completes.
# Proves: every PDF -> every page -> JSONL with block+word geometry.
export UV_CACHE_DIR=/store/shuvam/uv-cache UV_PYTHON_INSTALL_DIR=/store/shuvam/uv-python
cd /store/shuvam/BMoral
echo "=== FINAL AUDIT (all PDFs, all pages, words required) $(date) ==="
.venv/bin/python tools/audit_corpus.py \
    --data data/BMoral_pdf_collection \
    --output outputs/corpus \
    --require-words \
    --parse-log log/corpus.log \
    > log/final_audit.log 2>&1
echo "audit exit: $?"
echo "=== FINAL VALIDATE (strict) $(date) ==="
.venv/bin/python tools/validate_jsonl.py --jsonl outputs/corpus --strict \
    > log/final_validate.log 2>&1
echo "validate exit: $?"
tail -5 log/final_audit.log
echo "---"
tail -5 log/final_validate.log
echo "=== FINAL CHECK DONE $(date) ==="

echo "=== REFILTER (drop out-of-order word boxes) $(date) ==="
.venv/bin/python tools/refilter_words.py --output outputs/corpus >> log/final_audit.log 2>&1

echo "=== QUALITY CHECKS (11 modules) $(date) ==="
.venv/bin/python tools/quality_checks.py --output outputs/corpus \
    --books data/BMoral_pdf_collection --sample 2 \
    > log/final_quality.log 2>&1
echo "quality exit: $?"
tail -16 log/final_quality.log
echo "=== FINAL CHECK DONE $(date) ==="
