"""One .env for the whole system.

Every service was configured somewhere different — a dict literal in the chat
server, constants in serve.py, command-line flags nobody passed. This reads a
single file at the repo root so the endpoint, the model and the ports are
stated once, in one place, and nothing has to be edited in Python to move a
deployment.

Real environment variables win over the file, so a container or a systemd unit
can still override it without editing anything.

No dependency: python-dotenv would do this, but it is thirty lines and the
project already asks for enough.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENV_FILE = REPO / ".env"


def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def load_env(path: Path | None = None) -> dict[str, str]:
    """Read .env into os.environ without clobbering what is already set."""
    f = path or ENV_FILE
    found: dict[str, str] = {}
    if not f.exists():
        return found
    for raw in f.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not key:
            continue
        val = _unquote(val.split(" #")[0] if " #" in val else val)
        found[key] = val
        os.environ.setdefault(key, val)
    return found


def env(name: str, default=None, cast=None):
    """One setting, with the type you meant."""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    if cast is None:
        return raw
    if cast is bool:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    try:
        return cast(raw)
    except (TypeError, ValueError):
        return default


load_env()
