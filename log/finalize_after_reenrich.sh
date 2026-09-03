#!/bin/bash
# Post-re-enrichment finalization:
#  1. verify v2 validate + quality logs are green
#  2. rebuild clean archives from refreshed JSONLs
# Run ONLY after both chains print their DONE markers.
cd /store/shuvam/BMoral

echo "=== stage markers ==="
grep -c "RE-ENRICH DONE" log/run_reenrich.log 2>/dev/null || true
grep -c "CORPUS RE-ENRICH DONE" log/run_reenrich_corpus_wrapper.log 2>/dev/null || true

echo "=== v2 validate tails ==="
tail -2 log/full_set_validate_v2.log 2>/dev/null
tail -2 log/corpus_validate_v2.log 2>/dev/null

echo "=== v2 quality verdicts ==="
grep VERDICT log/fullset_quality_v2.log 2>/dev/null
grep "Q8\|Q4\|Q7" log/fullset_quality_v2.log 2>/dev/null
grep VERDICT log/corpus_quality_v2.log 2>/dev/null
grep "Q8\|Q4\|Q7" log/corpus_quality_v2.log 2>/dev/null

echo "=== rebuild clean full-set archive ==="
find outputs/full_set -maxdepth 2 -type f \( -name "*.pages.jsonl" -o -name "*.json" -o -name "*.md" \) | sort > /tmp/opencode/ocr_files_v2.txt
wc -l < /tmp/opencode/ocr_files_v2.txt
TS=$(date +%Y%m%d-%H%M%S)
mkdir -p ".rigor-trash/${TS}-full_set_ocr.tar.xz"
mv full_set_ocr.tar.xz ".rigor-trash/${TS}-full_set_ocr.tar.xz/"
echo "| $TS | full_set_ocr.tar.xz | superseded by re-enriched words (filter fix); replaced | move back |" >> .rigor-trash/INDEX.md
tar -c -I "xz -9 -T0" -f full_set_ocr.tar.xz -T /tmp/opencode/ocr_files_v2.txt && ls -lh full_set_ocr.tar.xz
echo "=== FINALIZE DONE $(date) ==="
