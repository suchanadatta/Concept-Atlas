#!/bin/bash
# Waits for parallel_download.py (PID passed as $1) to exit, then runs ingest.
WPID="$1"
LOG=log/watch_download.log
[ -z "$WPID" ] && { echo "usage: watch_download.sh <pid>" >> "$LOG"; exit 1; }
while kill -0 "$WPID" 2>/dev/null; do sleep 120; done
sleep 30
echo "=== downloader finished $(date); launching run_full_set.sh ===" >> "$LOG"
setsid nohup ./log/run_full_set.sh >> "$LOG" 2>&1 < /dev/null &
