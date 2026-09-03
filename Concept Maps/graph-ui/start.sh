#!/usr/bin/env bash
# Start the Concept Atlas server on the intranet (0.0.0.0:8788 by default).
# Usage: ./start.sh [port]
set -euo pipefail
cd "$(dirname "$0")"
PORT="${1:-8788}"
PIDFILE="atlas.pid"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "Already running (pid $(cat "$PIDFILE")) at http://$(hostname -I | awk '{print $1}'):$PORT"
  exit 0
fi

setsid nohup python3 serve.py "$PORT" >> atlas.log 2>&1 &
echo $! > "$PIDFILE"
sleep 1
if kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  IP=$(hostname -I | awk '{print $1}')
  echo "Started (pid $(cat "$PIDFILE")):  http://$IP:$PORT"
  curl -fs -o /dev/null "http://127.0.0.1:$PORT/healthz" && echo "healthz: OK" || { echo "healthz: FAILED — see atlas.log"; exit 1; }
else
  echo "Failed to start — see atlas.log"; exit 1
fi
