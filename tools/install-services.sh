#!/usr/bin/env bash
# Put the whole stack under systemd: index, chat, UI, public endpoint.
#
# These are user services, so no root is involved — with one exception noted at
# the end. The ordering is real rather than hopeful: the chat service and the
# UI wait for the index to answer /healthz, and the tunnel waits for the UI.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$HOME/.config/systemd/user"
UNITS=(concept-atlas-jasper concept-atlas-chat concept-atlas-ui concept-atlas-zrok)

mkdir -p "$DEST"
for u in "${UNITS[@]}"; do
  install -m 0644 "$HERE/$u.service" "$DEST/$u.service"
done
systemctl --user daemon-reload

# Stop anything we already manage, then clear whatever was started by hand and
# is still sitting on the ports. Without this the new units lose the bind.
systemctl --user stop "${UNITS[@]/%/.service}" 2>/dev/null || true
for port in 8790 8793 8788; do
  pid="$(ss -tlnpH "sport = :$port" 2>/dev/null | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2 || true)"
  if [ -n "${pid:-}" ]; then
    echo "port $port still held by pid $pid — stopping it"
    kill "$pid" 2>/dev/null || true
  fi
done
pkill -f "public:concept-atlas" 2>/dev/null || true
sleep 2

for u in "${UNITS[@]}"; do
  systemctl --user enable --now "$u.service"
done

systemctl --user --no-pager --lines=0 status "${UNITS[@]/%/.service}" 2>/dev/null \
  | grep -E "^●|Active:" || true

cat <<'MSG'

Done. One thing systemd cannot arrange for itself:

  sudo loginctl enable-linger "$USER"

Without it these stop when you log out and do not come back after a reboot.
MSG
