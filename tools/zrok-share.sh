#!/usr/bin/env bash
#
# Put Concept Atlas on a public URL that does not change.
#
# zrok v2 splits the two halves apart: a *name* is the durable thing (it is
# reserved to the account and survives everything), while a *share* is the
# live tunnel and is torn down when the process exits. So the URL is stable
# as long as every run binds to the same reserved name.
#
# One wrinkle: a share only unbinds itself on a clean SIGTERM. A crash, a
# kill -9, a reboot — any of those leave a share still holding the name, and
# the next start dies with a 409. That is what the sweep below is for.
#
# Everything is read from .env, so the port and the name are stated once.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO/.env"

# Read one key without sourcing the file: values may hold anything.
envval() {
  [ -f "$ENV_FILE" ] || return 0
  sed -n "s/^[[:space:]]*\(export[[:space:]]\+\)\?$1=//p" "$ENV_FILE" \
    | tail -1 | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/"
}

PORT="$(envval ATLAS_UI_PORT)";        PORT="${PORT:-8788}"
NAME="$(envval ATLAS_ZROK_NAME)";      NAME="${NAME:-concept-atlas}"
NS="$(envval ATLAS_ZROK_NAMESPACE)";   NS="${NS:-public}"

ZROK="${ZROK_BIN:-$(command -v zrok || true)}"
[ -x "$ZROK" ] || ZROK="$HOME/.local/bin/zrok"
if [ ! -x "$ZROK" ]; then
  echo "zrok not found; install it or set ZROK_BIN" >&2
  exit 1
fi

# The account must be enabled on this machine (zrok enable <token>).
if ! "$ZROK" status >/dev/null 2>&1; then
  echo "zrok environment is not enabled here; run: zrok enable <account-token>" >&2
  exit 1
fi

# Reserve the name once. Already-exists is the normal case, not a failure.
if ! "$ZROK" list names --json 2>/dev/null \
     | python3 -c "import sys,json;n=sys.argv[1];t=sys.argv[2];sys.exit(0 if any(x.get('name')==n and x.get('namespaceToken')==t for x in json.load(sys.stdin)) else 1)" "$NAME" "$NS"; then
  echo "reserving name '$NAME' in namespace '$NS'"
  "$ZROK" create name "$NAME" -n "$NS" || true
fi

# Sweep a share left behind by an unclean exit, or the name stays occupied.
stale="$("$ZROK" list names --json 2>/dev/null \
  | python3 -c "import sys,json;n=sys.argv[1];t=sys.argv[2];print(next((x.get('shareToken','') for x in json.load(sys.stdin) if x.get('name')==n and x.get('namespaceToken')==t), ''))" "$NAME" "$NS" || true)"
if [ -n "$stale" ]; then
  echo "clearing stale share $stale still bound to '$NAME'"
  "$ZROK" delete share "$stale" || true
fi

echo "sharing localhost:$PORT as https://$NAME.shares.zrok.io"
exec "$ZROK" share public "localhost:$PORT" -n "$NS:$NAME" --headless
