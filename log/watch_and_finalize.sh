#!/bin/bash
# Waits for the word map to finish, then runs the final checks (refilter +
# audit + validate + quality). Robust to reboots: --resume makes reruns cheap.
LOG=log/watch_and_finalize.log
while pgrep -f "word_map.py" > /dev/null 2>&1; do sleep 300; done
sleep 20
echo "=== word map done, running final checks $(date) ===" >> "$LOG"
setsid nohup ./log/final_check.sh >> "$LOG" 2>&1 < /dev/null &
