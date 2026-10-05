#!/usr/bin/env bash
# Stop the Concept Atlas server.
set -euo pipefail
cd "$(dirname "$0")"
PIDFILE="atlas.pid"
if [ -f "$PIDFILE" ]; then
  PID=$(cat "$PIDFILE")
  if kill -0 "$PID" 2>/dev/null; then
    kill -- -"$PID" 2>/dev/null || kill "$PID" 2>/dev/null || true
    sleep 0.5
    kill -0 "$PID" 2>/dev/null && kill -9 "$PID" 2>/dev/null || true
    echo "Stopped (pid $PID)"
  else
    echo "Not running (stale pidfile)"
  fi
  rm -f "$PIDFILE"
else
  echo "No pidfile — nothing to stop"
fi
