#!/bin/bash
# v3 SUPERVISOR: full-set pass -> corpus pass -> finalize. Crash-resumable.
#
# Uses word_map --older-than $TS: TS is fixed in plans/v3_state.txt on first
# launch; every completed book gets a fresh mtime and is skipped on relaunch
# with the same TS. If the machine reboots, cron @reboot relaunches this
# script; it picks up exactly where it left off.
#
# Manual ops:
#   start/resume :  ./log/run_v3_supervisor.sh
#   fresh restart:  rm plans/v3_state.txt && ./log/run_v3_supervisor.sh
set -u
export UV_CACHE_DIR=/store/shuvam/uv-cache UV_PYTHON_INSTALL_DIR=/store/shuvam/uv-python
export CUDA_HOME=/usr/local/cuda-13.3 PATH=/usr/local/cuda-13.3/bin:$PATH
export DOCTR_CACHE_DIR=/store/shuvam/BMoral/models/doctr
cd /store/shuvam/BMoral

STATE=plans/v3_state.txt
if [ -f "$STATE" ]; then
    TS=$(cat "$STATE")
else
    TS=$(date '+%Y-%m-%d %H:%M:%S')
    echo "$TS" > "$STATE"
fi
echo "=== V3 SUPERVISOR START (TS=$TS) $(date) ===" >> log/v3_supervisor.log

FS=outputs/full_set
CO=outputs/corpus

echo "=== [V3 1/8] FULLSET word map $(date) ===" >> log/v3_supervisor.log
.venv/bin/python tools/word_map.py --jsonl $FS --older-than "$TS" \
    --batch-size 16 --log-level INFO >> log/full_set_wordmap_v3.log 2>&1
tail -2 log/full_set_wordmap_v3.log >> log/v3_supervisor.log

echo "=== [V3 2/8] FULLSET paragraphs $(date) ===" >> log/v3_supervisor.log
.venv/bin/python tools/add_paragraphs.py --output $FS >> log/v3_supervisor.log 2>&1

echo "=== [V3 3/8] FULLSET refilter $(date) ===" >> log/v3_supervisor.log
.venv/bin/python tools/refilter_words.py --output $FS >> log/v3_supervisor.log 2>&1

echo "=== [V3 4/8] FULLSET validate+quality $(date) ===" >> log/v3_supervisor.log
.venv/bin/python tools/validate_jsonl.py --jsonl $FS --strict > log/full_set_validate_v3.log 2>&1 || true
.venv/bin/python tools/quality_checks.py --output $FS --books data/full_set_pdfs/pdf \
    > log/fullset_quality_v3.log 2>&1 || true
grep VERDICT log/fullset_quality_v3.log >> log/v3_supervisor.log

echo "=== [V3 5/8] CORPUS word map $(date) ===" >> log/v3_supervisor.log
.venv/bin/python tools/word_map.py --jsonl $CO --older-than "$TS" \
    --batch-size 16 --log-level INFO >> log/corpus_wordmap_v3.log 2>&1
tail -2 log/corpus_wordmap_v3.log >> log/v3_supervisor.log

echo "=== [V3 6/8] CORPUS paragraphs $(date) ===" >> log/v3_supervisor.log
.venv/bin/python tools/add_paragraphs.py --output $CO >> log/v3_supervisor.log 2>&1

echo "=== [V3 7/8] CORPUS refilter+validate+quality $(date) ===" >> log/v3_supervisor.log
.venv/bin/python tools/refilter_words.py --output $CO >> log/v3_supervisor.log 2>&1
.venv/bin/python tools/validate_jsonl.py --jsonl $CO --strict > log/corpus_validate_v3.log 2>&1 || true
.venv/bin/python tools/quality_checks.py --output $CO --books data/BMoral_pdf_collection \
    > log/corpus_quality_v3.log 2>&1 || true
grep VERDICT log/corpus_quality_v3.log >> log/v3_supervisor.log

echo "=== [V3 8/8] FINALIZE (archive rebuild) $(date) ===" >> log/v3_supervisor.log
./log/finalize_after_reenrich.sh > log/finalize.log 2>&1 || true

echo "=== V3 SUPERVISOR ALL DONE $(date) ===" >> log/v3_supervisor.log
