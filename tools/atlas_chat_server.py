#!/usr/bin/env python3
"""Concept Atlas chat, accounts and session store.

Runs beside the Jasper search server; the UI reaches it through same-origin
proxies on :8788 so it works from any machine on the intranet.

Storage
-------
Sessions live as one gzipped JSONL file each, under
``data/atlas_chat/sessions/<session_id>.jsonl.gz`` — one JSON object per line,
which is the same shape the export/import endpoints speak, so an exported
session is literally the stored file. SQLite holds the index: who owns what,
titles, timestamps, message counts and the context attached to each session.
The transcripts are the bulk and compress ~5-10x as gzip; keeping them out of
the database keeps it small and makes export a file copy rather than a
reconstruction.

Endpoints (all JSON unless noted)
---------------------------------
  POST /auth/register   {username,email,password}      -> {token,user}
  POST /auth/login      {username_or_email,password}   -> {token,user}
  POST /auth/logout     {}                             -> {ok}
  GET  /auth/me                                        -> {user}
  POST /auth/update     {display_name?,email?,password?,current_password}
  POST /auth/forgot     {email}                        -> {reset_token}
  POST /auth/reset      {reset_token,password}         -> {ok}

  GET  /sessions                                       -> [{...}]
  POST /sessions        {title?}                       -> {session}
  GET  /sessions/<id>                                  -> {session, messages, context}
  POST /sessions/<id>/rename  {title}
  POST /sessions/<id>/delete
  GET  /sessions/<id>/export                           -> JSONL download
  POST /sessions/import  {jsonl}                       -> {session}

  POST /sessions/<id>/context/add     {items:[...]}
  POST /sessions/<id>/context/remove  {ids:[...]}

  POST /chat            {session_id,message}           -> SSE stream
  GET  /healthz

Run:
  python tools/atlas_chat_server.py [--port 8793] [--vllm http://localhost:8000/v1]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas_tools  # noqa: E402  (same directory; needs the path above)

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data" / "atlas_chat"
SESSION_DIR = DATA / "sessions"
DB_PATH = DATA / "atlas.db"

# Settings come from .env at the repo root (see .env.example), so the endpoint
# and the model are stated once for every service rather than in three files.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from atlas_env import env as _env   # noqa: E402

CFG = {
    "vllm": _env("ATLAS_VLLM", "http://localhost:8000/v1"),
    "model": _env("ATLAS_MODEL", "Qwen3.8-27B-TURBO"),
    "api_key": _env("ATLAS_API_KEY", ""),
    # None means no cap: the model stops when it is done, not at an arbitrary
    # number of tokens. A long adjudication was being cut off mid-sentence.
    "max_output": _env("ATLAS_MAX_OUTPUT_TOKENS", None, int),
    "max_ctx": _env("ATLAS_MAX_CTX", 550_000, int),
    "jasper": "http://127.0.0.1:8790",
}

# rough chars-per-token for budgeting the context window without tokenising
CHARS_PER_TOKEN = 3.6

_local = threading.local()


# ----------------------------------------------------------------- database
def db() -> sqlite3.Connection:
    """One connection per thread; ThreadingHTTPServer hands each request its own."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        DATA.mkdir(parents=True, exist_ok=True)
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY,
  username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
  email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
  display_name  TEXT NOT NULL DEFAULT '',
  pw_hash       TEXT NOT NULL,
  pw_salt       TEXT NOT NULL,
  created_at    REAL NOT NULL,
  reset_token   TEXT,
  reset_expires REAL
);
-- A reader can point Ask and Debate at their own OpenAI-compatible endpoint
-- instead of this deployment's model. Stored per account, never returned to
-- the browser except masked.
CREATE TABLE IF NOT EXISTS user_providers (
  user_id    INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  base_url   TEXT NOT NULL DEFAULT '',
  api_key    TEXT NOT NULL DEFAULT '',
  model      TEXT NOT NULL DEFAULT '',
  enabled    INTEGER NOT NULL DEFAULT 0,
  checked_at REAL,
  check_ok   INTEGER NOT NULL DEFAULT 0,
  check_note TEXT NOT NULL DEFAULT '',
  updated_at REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS auth_tokens (
  token      TEXT PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at REAL NOT NULL,
  expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  id         TEXT PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title      TEXT NOT NULL DEFAULT 'New conversation',
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  n_messages INTEGER NOT NULL DEFAULT 0,
  model      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_sessions_user ON sessions(user_id, updated_at DESC);
CREATE TABLE IF NOT EXISTS context_items (
  id         TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  kind       TEXT NOT NULL,
  label      TEXT NOT NULL,
  ref        TEXT NOT NULL DEFAULT '',
  payload    TEXT NOT NULL DEFAULT '{}',
  n_chars    INTEGER NOT NULL DEFAULT 0,
  added_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_ctx_session ON context_items(session_id, added_at);

-- Exchanges the reader has taken out of the history. The transcript itself is
-- append-only (it is the export format), so a dropped turn is recorded here
-- rather than rewritten out of the file: it stays readable, stops being sent
-- to the model, and can be put back.
-- A debate is long-running, interruptible and open to a moderator, so its
-- state lives here rather than only in the transcript: which motion, which
-- sides, how far it got, and whether it is running, paused or finished. The
-- turns themselves are appended to the session's JSONL as they complete, so a
-- paused debate can be picked up exactly where it stopped.
CREATE TABLE IF NOT EXISTS debates (
  id         TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  motion     TEXT NOT NULL,
  sides      TEXT NOT NULL DEFAULT '[]',
  rounds     INTEGER NOT NULL DEFAULT 2,
  judge      INTEGER NOT NULL DEFAULT 1,
  allow_web  INTEGER NOT NULL DEFAULT 0,
  status     TEXT NOT NULL DEFAULT 'running',   -- running | paused | done
  done_turns INTEGER NOT NULL DEFAULT 0,        -- how many turns of the schedule are spoken
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_debate_session ON debates(session_id, created_at);

-- What the moderator says. Picked up before the next turn speaks, so it can be
-- added while the debate is running as well as while it is paused.
CREATE TABLE IF NOT EXISTS debate_notes (
  id         INTEGER PRIMARY KEY,
  debate_id  TEXT NOT NULL REFERENCES debates(id) ON DELETE CASCADE,
  addressed  TEXT NOT NULL DEFAULT 'both',      -- a side's name, or 'both'
  text       TEXT NOT NULL,
  after_turn INTEGER NOT NULL DEFAULT 0,        -- how many turns were spoken when it arrived
  used       INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_note_debate ON debate_notes(debate_id, created_at);

CREATE TABLE IF NOT EXISTS dropped_turns (
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  idx        INTEGER NOT NULL,
  dropped_at REAL NOT NULL,
  PRIMARY KEY (session_id, idx)
);
"""


def init_db() -> None:
    db().executescript(SCHEMA)
    db().commit()


# --------------------------------------------------------------------- auth
def hash_pw(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), 200_000
    ).hex()


def check_pw(password: str, salt: str, expect: str) -> bool:
    return hmac.compare_digest(hash_pw(password, salt), expect)


USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def user_public(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "display_name": row["display_name"] or row["username"],
        "created_at": row["created_at"],
    }


def issue_token(user_id: int, days: int = 30) -> str:
    tok = secrets.token_urlsafe(32)
    now = time.time()
    db().execute(
        "INSERT INTO auth_tokens(token,user_id,created_at,expires_at) VALUES(?,?,?,?)",
        (tok, user_id, now, now + days * 86400),
    )
    db().commit()
    return tok


def user_for_token(tok: str):
    if not tok:
        return None
    row = db().execute(
        "SELECT u.* FROM auth_tokens t JOIN users u ON u.id=t.user_id "
        "WHERE t.token=? AND t.expires_at>?",
        (tok, time.time()),
    ).fetchone()
    return row


# ------------------------------------------------------------------ storage
def session_path(sid: str) -> Path:
    return SESSION_DIR / f"{sid}.jsonl.gz"


def append_message(sid: str, obj: dict) -> None:
    """Transcripts are append-only gzip JSONL — the export format is the file."""
    p = session_path(sid)
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "at", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _is_tooling_unsupported(err) -> bool:
    t = str(err).lower()
    return ("tool choice" in t and "requires" in t) or "enable-auto-tool-choice" in t \
        or "tool_call_parser" in t or "tool-call-parser" in t


def probe_context(base, key=None, model=None, timeout=8):
    """What window the endpoint will actually accept.

    ATLAS_MAX_CTX is a claim in a config file; the engine knows the truth, and
    the two drift apart the moment vLLM is restarted with a different
    --max-model-len. Budgeting attached context from the claim then offers the
    reader far more than the model will take, and the turn fails at request
    time with nothing useful said about why.
    """
    base = (base or "").rstrip("/")
    if not base.endswith("/v1") and "/v1" not in base:
        base += "/v1"
    req = urllib.request.Request(
        base + "/models",
        headers={"Authorization": f"Bearer {key}"} if key else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None
    rows = d.get("data") or []
    if model:
        rows = [x for x in rows if x.get("id") == model] or rows
    for x in rows:
        n = x.get("max_model_len") or x.get("context_length") or x.get("context_window")
        if isinstance(n, int) and n > 0:
            return n
    return None


def effective_ctx(pv):
    """The smaller of what is configured and what the endpoint reports."""
    claimed = int(CFG["max_ctx"])
    seen = CTX_SEEN.get(pv["base"] + "|" + pv["model"])
    if seen is None:
        seen = probe_context(pv["base"], pv.get("key"), pv["model"])
        CTX_SEEN[pv["base"] + "|" + pv["model"]] = seen if seen else 0
    return min(claimed, seen) if seen else claimed


CTX_SEEN: dict[str, int] = {}


def provider_for(user_id):
    """The endpoint this reader's requests should go to.

    Their own if they have set one up and switched it on, otherwise the
    deployment's. Returning a dict rather than reading CFG at each call site
    means a per-user endpoint is honoured everywhere without threading it
    through by hand.
    """
    row = db().execute("SELECT * FROM user_providers WHERE user_id=?", (user_id,)).fetchone()
    if row and row["enabled"] and row["base_url"] and row["model"]:
        return {"base": row["base_url"], "key": row["api_key"], "model": row["model"],
                "own": True}
    return {"base": CFG["vllm"], "key": CFG["api_key"], "model": CFG["model"], "own": False}


def mask_key(k: str) -> str:
    if not k:
        return ""
    return (k[:3] + "…" + k[-4:]) if len(k) > 10 else "…"


def check_provider(base, key, model, timeout=30):
    """Actually call the endpoint. A key that is merely stored is not a key
    that works, and the failure people hit is always at the first real
    request — so make that request here, with the parameters a real turn uses,
    and report exactly what came back."""
    base = (base or "").rstrip("/")
    if not base.endswith("/v1") and "/v1" not in base:
        base += "/v1"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with the single word: ready"}],
        # a reasoning model spends its first tokens thinking, so too small a
        # probe comes back with an empty content field and looks like a failure
        "max_tokens": 96,
        "temperature": 0,
        "stream": False,
    }
    req = urllib.request.Request(
        base + "/chat/completions", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {key}"} if key else {})},
        method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            payload = json.loads(e.read() or b"{}")
            err = payload.get("error")
            detail = (err.get("message") if isinstance(err, dict) else str(err)) or ""
        except Exception:
            pass
        hint = {401: "the key was rejected", 403: "the key is not allowed to use this model",
                404: "no such model, or the wrong base URL",
                429: "rate limited — the key works but is over its quota"}.get(e.code, "")
        return {"ok": False, "status": e.code,
                "error": f"HTTP {e.code}: {detail or e.reason}", "hint": hint}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}",
                "hint": "the endpoint could not be reached — check the base URL"}
    choice = (d.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    # some models answer in a separate reasoning field; an empty content field
    # is not evidence that nothing came back
    text = (msg.get("content") or msg.get("reasoning")
            or msg.get("reasoning_content") or "").strip()
    usage = d.get("usage") or {}
    return {
        "ok": True, "took_ms": round((time.time() - t0) * 1000),
        "model": d.get("model") or model,
        "reply": text[:120],
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "finish_reason": choice.get("finish_reason"),
        "supports_tools": None,   # filled in by the tool probe below
    }


def check_provider_tools(base, key, model, timeout=40):
    """The agent is useless without tool calling, so probe that too rather
    than let a reader discover it when an answer silently has no citations."""
    base = (base or "").rstrip("/")
    if not base.endswith("/v1") and "/v1" not in base:
        base += "/v1"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "Look up the weather in Paris."}],
        "tools": [{"type": "function", "function": {
            "name": "get_weather", "description": "Weather for a city.",
            "parameters": {"type": "object",
                           "properties": {"city": {"type": "string"}},
                           "required": ["city"]}}}],
        "tool_choice": "auto", "max_tokens": 64, "temperature": 0, "stream": False,
    }
    req = urllib.request.Request(
        base + "/chat/completions", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {key}"} if key else {})},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        return {"supports_tools": False, "note": f"tool call probe failed ({type(e).__name__})"}
    ch = (d.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    called = bool(msg.get("tool_calls"))
    return {"supports_tools": called,
            "note": ("the model asked for the tool, as it should" if called
                     else "the model answered without calling the tool — citations may be thin")}


def dropped_turns(sid: str) -> set[int]:
    return {r["idx"] for r in db().execute(
        "SELECT idx FROM dropped_turns WHERE session_id=?", (sid,)).fetchall()}


def set_dropped(sid: str, idx: int, drop: bool) -> None:
    if drop:
        db().execute(
            "INSERT OR IGNORE INTO dropped_turns(session_id, idx, dropped_at) VALUES(?,?,?)",
            (sid, int(idx), time.time()))
    else:
        db().execute("DELETE FROM dropped_turns WHERE session_id=? AND idx=?", (sid, int(idx)))
    db().commit()


def read_messages(sid: str) -> list[dict]:
    p = session_path(sid)
    if not p.exists():
        return []
    out = []
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # a truncated tail must not lose the whole transcript
    return out


def touch_session(sid: str, n_delta: int = 0) -> None:
    db().execute(
        "UPDATE sessions SET updated_at=?, n_messages=n_messages+? WHERE id=?",
        (time.time(), n_delta, sid),
    )
    db().commit()


# ------------------------------------------------------------------ context
def jasper(path: str, body: dict, timeout: int = 120):
    req = urllib.request.Request(
        CFG["jasper"] + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def find_book_files(book_id: str):
    """Locate the OCR JSONL / text file backing a book id.

    The OCR record carries the absolute path of the PDF it was made from, so
    the JSONL is the reliable route to a book's text; the flat txt_books
    directory covers the clean-text editions.
    """
    for d in (REPO / "outputs" / "full_set", REPO / "outputs" / "corpus"):
        c = d / book_id / f"{book_id}.pages.jsonl"
        if c.exists():
            return ("ocr", c)
        hits = list(d.rglob(f"{book_id}.pages.jsonl"))
        if hits:
            return ("ocr", hits[0])
    t = REPO / "data" / "txt_books" / f"{book_id}.txt"
    if t.exists():
        return ("txt", t)
    return (None, None)


def book_text(book_id: str, page_from=None, page_to=None, max_chars=400_000):
    """Plain text of a book, optionally a page (or paragraph) range."""
    kind, path = find_book_files(book_id)
    if not path:
        return "", 0
    chunks, n = [], 0
    if kind == "ocr":
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                pn = d.get("page_number")
                if page_from and pn < page_from:
                    continue
                if page_to and pn > page_to:
                    break
                t = (d.get("text") or "").strip()
                if not t:
                    continue
                chunks.append(f"[page {pn}]\n{t}")
                n += 1
                if sum(len(c) for c in chunks) > max_chars:
                    break
    else:
        raw = path.read_text(encoding="utf-8", errors="replace")
        paras = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
        lo = (page_from or 1) - 1
        hi = page_to or len(paras)
        for i, p in enumerate(paras[lo:hi], start=lo):
            chunks.append(f"[¶{i}]\n{p}")
            n += 1
            if sum(len(c) for c in chunks) > max_chars:
                break
    return "\n\n".join(chunks), n


def concept_text(concept_id: str):
    """A concept as prose: definition, category, relations and its evidence."""
    graph = REPO / "Concept Maps" / "final" / "concept_graph.jsonl"
    inv = REPO / "Concept Maps" / "final" / "inverted_index.jsonl"
    nodes, edges = {}, []
    if graph.exists():
        for line in open(graph, encoding="utf-8"):
            d = json.loads(line)
            if d.get("type") == "node":
                nodes[d["id"]] = d
            else:
                edges.append(d)
    n = nodes.get(concept_id)
    if not n:
        return "", 0
    lines = [f"CONCEPT: {n.get('label', concept_id)}"]
    if n.get("category"):
        lines.append("Category: " + " > ".join(n["category"]))
    if n.get("aliases"):
        lines.append("Also called: " + ", ".join(n["aliases"]))
    if n.get("definition"):
        lines.append("Definition: " + n["definition"])
    rel = []
    for e in edges:
        if e.get("source") == concept_id and e.get("target") in nodes:
            rel.append(f"  {n.get('label')} --{e['relation']}--> {nodes[e['target']].get('label')}")
        elif e.get("target") == concept_id and e.get("source") in nodes:
            rel.append(f"  {nodes[e['source']].get('label')} --{e['relation']}--> {n.get('label')}")
    if rel:
        lines.append("Relations in the concept map:")
        lines.extend(sorted(set(rel))[:40])
    ev = []
    if inv.exists():
        for line in open(inv, encoding="utf-8"):
            d = json.loads(line)
            if d.get("concept_id") == concept_id:
                q = (d.get("text") or "").strip()
                if q:
                    ev.append(f"  - \"{q}\" ({d.get('book_id', '')} p.{d.get('page', '?')})")
            if len(ev) >= 25:
                break
    if ev:
        lines.append("Attested by:")
        lines.extend(ev)
    body = "\n".join(lines)
    return body, len(rel)


def build_context_item(it: dict) -> dict:
    """Turn a UI request into a stored context item with its text resolved."""
    kind = it.get("kind")
    now = time.time()
    cid = secrets.token_urlsafe(9)
    if kind == "book":
        bid = it.get("book_id", "")
        pf, pt = it.get("page_from"), it.get("page_to")
        text, n = book_text(bid, pf, pt)
        label = it.get("label") or bid
        if pf or pt:
            label += f" · pp. {pf or 1}–{pt or 'end'}"
        return {
            "id": cid, "kind": "book", "label": label, "ref": bid,
            "payload": {"page_from": pf, "page_to": pt, "n_units": n},
            "text": text, "added_at": now,
        }
    if kind == "concept":
        c = it.get("concept_id", "")
        text, nrel = concept_text(c)
        return {
            "id": cid, "kind": "concept", "label": it.get("label") or c, "ref": c,
            "payload": {"n_relations": nrel}, "text": text, "added_at": now,
        }
    if kind == "passage":
        page = it.get("page")
        loc = "text edition" if page is None else f"p.{page}"
        head = f"[{it.get('cite') or it.get('book_id')} {loc}]"
        return {
            "id": cid, "kind": "passage",
            "label": it.get("label") or (it.get("cite") or "passage"),
            "ref": it.get("book_id", ""),
            "payload": {"page": page},
            "text": head + "\n" + (it.get("text") or it.get("snippet") or ""),
            "added_at": now,
        }
    if kind == "search":
        q = it.get("query", "")
        try:
            d = jasper("/semantic", {"query": q, "top_k": int(it.get("top_k", 20))})
        except Exception:
            d = {"results": []}
        parts = [f"SEARCH RESULTS for: {q}"]
        for r in d.get("results", []):
            loc = "text edition" if r.get("page") is None else f"p.{r['page']}"
            parts.append(f"[{r.get('cite') or r.get('book_id')} {loc}]\n{r.get('text') or r.get('snippet') or ''}")
        return {
            "id": cid, "kind": "search", "label": it.get("label") or f'search: "{q}"',
            "ref": q, "payload": {"n": len(d.get("results", []))},
            "text": "\n\n".join(parts), "added_at": now,
        }
    # free note
    return {
        "id": cid, "kind": "note", "label": it.get("label") or "note", "ref": "",
        "payload": {}, "text": it.get("text", ""), "added_at": now,
    }


def ctx_text_path(sid: str, cid: str) -> Path:
    return SESSION_DIR / f"{sid}.ctx" / f"{cid}.txt.gz"


def save_ctx_text(sid: str, cid: str, text: str) -> int:
    p = ctx_text_path(sid, cid)
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write(text or "")
    return len(text or "")


def load_ctx_text(sid: str, cid: str) -> str:
    p = ctx_text_path(sid, cid)
    if not p.exists():
        return ""
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------------------------- chat
SYSTEM_PROMPT = """You are the research assistant inside Concept Atlas, a search system over a \
corpus of 18th-century British moral philosophy: 129 scanned volumes plus 68 clean-text editions \
(197 indexed sources, 90,975 passages) by 37 named authors, mapped to 202 concepts and 1,099 \
relations between them.

YOU HAVE TOOLS. Use them. Do not answer from memory about what these texts say — look.

How to work
-----------
1. Decide what kind of question it is. About what the texts argue -> search_corpus. About a
   concept's meaning or its place in the map -> find_concept, then concept_detail and
   concept_passages. Broad or vague -> query_network first, to see the territory. About who wrote
   what -> list_authors.
   Two ideas held against each other -> compare_ideas, which finds the passages where they are
   argued TOGETHER. What is on the shelf -> list_books. About to print a quotation -> verify_quote.
2. DO NOT GIVE UP AFTER ONE CALL, OR AFTER FIVE. You have around thirty rounds of tool calls
   per question and you are expected to use as many as the question needs. Searching again with
   better words is cheaper than an answer that is wrong. If hybrid search returns nothing to the
   point:
     * reword in the period's own vocabulary (vertue, felf-love, the paffions);
     * try mode='semantic' for meaning, or 'bm25'/'keyword' for a literal word or rare name;
     * try find_concept — the map may hold the idea under a name you did not guess;
     * try concept_detail with hops=2 to reach it through a neighbouring concept.
   Only after several genuinely different attempts may you say the corpus does not address it.
   The same applies to the web when it is switched on: the first page of results is rarely the
   answer. Go to page 2, pin the domain once you know where the answer lives, reword, and read
   the pages themselves with web_fetch rather than trusting a snippet. Keep going until you can
   answer or can say precisely what you could not establish. You will be told when your rounds
   are running low, and if three rounds in a row turn up nothing new you will be told that too —
   that is the signal to change approach, not to try the same search once more.
3. When a snippet is not enough to settle what an author claims, read_source the page range.
4. Quote sparingly and exactly. Spelling is archaic — read through it and never silently modernise
   a quotation. If you are quoting from memory rather than from a tool result in front of you, run
   verify_quote first. A quotation the tool cannot find must not appear in your answer.
5. Your answer is checked before the reader sees it — by you, with the tools still in hand. Write
   the draft you would defend, not one you hope nobody looks into.

How to lay an answer out
------------------------
Markdown is rendered: headings, **bold**, lists, > quotations, `code`, and real tables. Use a
table when you are setting several authors or positions against each other on the same axes —
it is far easier to read than the same content as prose.

You can also draw. A fenced ```mermaid block is rendered as a diagram, and is worth it when the
shape of something is the point: how concepts hang together, who influenced whom, the branches of
an argument. Keep node labels short, put quotes around any label containing punctuation, and do
not draw for the sake of it — a diagram that restates one sentence is noise.

Citations — this matters most
-----------------------------
Every passage a tool returns carries a "cite_as" value like [S3]. USE IT. Put it inline,
immediately after the claim it supports:

    Norris divides benevolence into self-love and charity [S1], and denies that all
    love reduces to self-love [S3].

    "If to oneself, then tis that special sort of Benevolence which we call self-love" [S1]

Do NOT write the book and page out in prose instead of the marker. "From The Theory and
Regulation of Love (1688), p. 33" is WRONG where "[S1]" is right: the reader clicks the marker to
open that exact page, and prose is not clickable. Naming the author in the sentence is fine and
good — but the marker must still be there.

Use a marker only for a passage you were actually shown. Never invent one, never renumber, never
cite a marker you did not receive. If several passages support a claim, cite them together:
[S2][S5]. If you assert something no tool showed you, say so in words and attach no marker.

Honesty
-------
If the corpus does not settle a question, say so plainly and say what you did look at. Distinguish
what these texts say from what is generally known — and if web tools are available and you use
them, mark that material as coming from outside the corpus. Do not pad; a short grounded answer is
better than a long one that drifts."""



def agent_turn(msgs, *, emit, cites, allow_web=False, max_steps=30, max_tokens=None,
               tag=None, channel="content", tools=True, sink=None, budget_secs=None,
               provider=None):
    """One agent's turn: call tools until it has an answer, then answer.

    The same loop serves the assistant, the self-check pass and every speaker in
    a debate, so they all get the same tool access and the same citation table —
    a marker means the same passage wherever it appears in the transcript.

    `tag` is merged into every event, which is how the client tells one debater
    from another. Returns (reasoning, content, trace).

    `sink` is a dict of lists the caller owns. Everything is appended to it as
    it streams, so a turn interrupted half-way — the reader pressed stop, the
    connection dropped — leaves the caller holding what was actually said
    instead of nothing.
    """
    schemas = atlas_tools.schemas(allow_web=allow_web) if tools else None
    if sink is None:
        sink = {}
    reasoning = sink.setdefault("reasoning", [])
    content = sink.setdefault("content", [])
    trace = sink.setdefault("trace", [])
    # One self-check pass was seen firing 120 verify_quote calls in a single
    # step — every phrase in the draft, several of them twice. Two limits:
    # a cap per step, and a memo so an identical call is answered from the
    # first result instead of being run again.
    memo: dict[str, dict] = {}
    MAX_CALLS_PER_STEP = 12

    # The budget is deliberately generous: an agent that is genuinely unsure
    # should keep searching, rewording and reading rather than answering from
    # a first guess. What has to be prevented is not persistence but going
    # round in circles, so instead of a low ceiling there are three guards —
    # a memo (an identical call is free but adds nothing), stall detection
    # (a round that turned up no new evidence), and a wall clock.
    started = time.time()
    deadline = started + float(budget_secs) if budget_secs else None
    stalls = 0
    warned_low = False
    nudge = None            # queued for the next round

    def send(obj):
        if tag:
            obj = {**obj, **tag}
        emit(obj)

    # Some deployments serve a model without tool calling switched on — vLLM
    # needs --enable-auto-tool-choice and a --tool-call-parser, and without
    # them it rejects the whole request rather than ignoring the tools. That
    # used to break Ask and Debate outright. Notice it once, say so, and carry
    # on without tools: an answer from the attached context and the
    # conversation is worth more than a 400.
    tools_off = False

    for step in range(max_steps):
        # Tell it where it stands rather than cutting it off without warning.
        left = max_steps - step
        if nudge:
            msgs.append({"role": "user", "content": nudge})
            nudge = None
        if deadline and time.time() > deadline:
            send({"type": "note", "text": "time budget spent — answering from what was gathered"})
            break
        if left <= 3 and not warned_low:
            warned_low = True
            msgs.append({"role": "user", "content": (
                f"You have {left} tool rounds left this turn. Spend them on what is still "
                "missing, then answer. If something remains unresolved, say so in the answer "
                "rather than leaving it out.")})
        calls = None
        step_reasoning, step_content = [], []
        try:
            stream = vllm_stream(msgs, max_tokens=max_tokens,
                                 tools=None if tools_off else schemas, provider=provider)
            first = next(stream, None)
        except RuntimeError as e:
            if not tools_off and _is_tooling_unsupported(e):
                tools_off = True
                sink["tools_off"] = True     # so the saved turn can say why
                send({"type": "note", "text": (
                    "This endpoint has tool calling switched off, so the corpus tools are not "
                    "available and this answer cannot be grounded in searched passages. For "
                    "vLLM, restart it with --enable-auto-tool-choice and --tool-call-parser.")})
                # The system prompt has been telling it to use tools, so left
                # unsaid it writes a <tool_call> block out as prose. Say plainly
                # that there are none.
                msgs.append({"role": "user", "content": (
                    "IMPORTANT: the tools described above are NOT available on this endpoint. "
                    "Do not emit a tool call in any form — not as JSON, not in tags. Answer from "
                    "the attached context and this conversation alone, and say openly that you "
                    "could not search the corpus for this answer, so it carries no citations.")})
                stream = vllm_stream(msgs, max_tokens=max_tokens, tools=None, provider=provider)
                first = next(stream, None)
            else:
                raise
        for kind, chunk in ([first] if first else []) + list(stream):
            if kind == "reasoning":
                step_reasoning.append(chunk)
                reasoning.append(chunk)
                send({"type": "reasoning", "text": chunk})
            elif kind == "content":
                step_content.append(chunk)
                content.append(chunk)
                send({"type": channel, "text": chunk})
            elif kind == "tool_calls":
                calls = chunk
        # step_* are kept separately for the assistant message below; the sink
        # is appended to as each chunk arrives rather than at the end of a step,
        # because the step that matters when a turn is stopped is the one still
        # in progress — extending only at the boundary lost exactly that prose.
        if not calls:
            break
        msgs.append({
            "role": "assistant",
            "content": "".join(step_content),
            "tool_calls": [
                {"id": c["id"] or f"call_{step}_{k}", "type": "function",
                 "function": {"name": c["name"], "arguments": c["args"] or "{}"}}
                for k, c in enumerate(calls)
            ],
        })
        cites_before = len(cites.rows)
        useful = 0
        for k, c in enumerate(calls):
            try:
                args = json.loads(c["args"] or "{}")
            except json.JSONDecodeError:
                args = {}
            # emit the request whatever happens to it, so the trace shows what
            # the model asked for as well as what it got
            send({"type": "tool_call", "step": step, "name": c["name"], "args": args})
            if k >= MAX_CALLS_PER_STEP:
                result = {"error": (
                    f"not run: {len(calls)} tools were requested at once and only the first "
                    f"{MAX_CALLS_PER_STEP} are executed per step. Ask for the few that matter "
                    "most, read what they return, then ask for more if you still need them.")}
                summary = "skipped — too many calls in one step"
            else:
                key = c["name"] + "\u0000" + json.dumps(args, sort_keys=True, ensure_ascii=False)
                if key in memo:
                    result = dict(memo[key])
                    result["note"] = "identical call already made this turn; this is that result"
                    summary = atlas_tools.summarise(c["name"], result) + " (repeat)"
                else:
                    result = atlas_tools.run_tool(c["name"], args, cites, allow_web=allow_web)
                    memo[key] = result
                    summary = atlas_tools.summarise(c["name"], result)
                    if not result.get("error"):
                        useful += 1
            trace.append({"step": step, "name": c["name"], "args": args,
                          "summary": summary, "took_ms": result.get("took_ms")})
            send({"type": "tool_result", "step": step, "name": c["name"],
                  "summary": summary, "took_ms": result.get("took_ms")})
            msgs.append({
                "role": "tool",
                "tool_call_id": c["id"] or f"call_{step}_{k}",
                "name": c["name"],
                "content": json.dumps(result, ensure_ascii=False)[:60000],
            })
        if cites.rows:
            send({"type": "sources", "sources": cites.as_list()})

        # A round that ran nothing new and turned up no new evidence is a
        # circle. Say so plainly instead of letting it spin the budget away.
        if useful == 0 and len(cites.rows) == cites_before:
            stalls += 1
        else:
            stalls = 0
        if stalls >= 3:
            nudge = (
                "Your last three rounds of tool calls produced nothing new — repeats, errors, or "
                "results you already had. Stop repeating them. Either try a materially different "
                "approach (a different tool, a different wording, the concept map instead of a "
                "search, two hops instead of one), or accept that this corpus does not settle the "
                "point and answer now, saying plainly what you could not establish.")
            stalls = 0
    else:
        # Still reaching for tools when the budget ran out. Take them away and
        # make it answer from what it has, rather than ending with nothing said.
        send({"type": "note",
              "text": f"tool budget spent after {max_steps} rounds — answering from "
                      f"the {len(cites.rows)} passages gathered"})
        msgs.append({"role": "user", "content": (
            "You have used your tool budget. Do not ask for more tools; there are none left "
            "this turn. Answer now from the evidence you already have above, citing each claim "
            "by its cite_as marker. If the evidence is thin on some part of the question, say "
            "so plainly rather than guessing.")})
        for kind, chunk in vllm_stream(msgs, max_tokens=max_tokens, tools=None,
                                       provider=provider):
            if kind == "reasoning":
                reasoning.append(chunk)
                send({"type": "reasoning", "text": chunk})
            elif kind == "content":
                content.append(chunk)
                send({"type": channel, "text": chunk})
    return "".join(reasoning), "".join(content), trace


SELF_CHECK_PROMPT = """Your draft answer is above. Before the reader sees it, check it.

You still have every tool. Do this, in order:

1. Every phrase you put in quotation marks: run verify_quote on it. If the verdict is NOT FOUND,
   the quotation is wrong — remove it or replace it with wording the tool confirms. If it is CLOSE
   BUT NOT VERBATIM, copy the wording from text_as_printed.
2. Every citation marker: does the passage behind it actually support the claim you attached it
   to, or only sit near the topic? If it does not, find one that does or drop the claim.
3. Every substantive claim about what these texts say that carries NO marker: either find support
   for it with a tool, or mark it in the text as your inference rather than the corpus's word.
4. Anything you asserted about an author, a date or a work that you did not look up: look it up.

Then reply in exactly one of two ways.

If nothing needed fixing, reply with the single line:
VERDICT: stands

If anything needed fixing, reply with:
VERDICT: revised
followed by the complete corrected answer, in full, ready to show the reader. Do not describe the
changes; write the answer itself. Keep everything that was right.

Do not be precious about the draft. A quiet correction now is worth more than a confident error."""

# --------------------------------------------------------------------- debate
DEBATE_COMMON = """This is a formal debate held inside Concept Atlas, over a corpus of \
18th-century British moral philosophy: 197 indexed sources, 90,975 passages, 37 named authors, \
202 mapped concepts.

The motion is:

    {motion}

You are arguing {stance}.

Rules of this debate
--------------------
* ARGUE FROM THE CORPUS, NOT FROM MEMORY. Before you assert what any author held, find the
  passage. You have the full toolset: search_corpus in four modes, read_source for a page range,
  find_concept and concept_detail for the map and its relations, concept_passages for attested
  quotes, compare_ideas for two ideas held side by side, list_books for what is on the shelf,
  list_authors for who wrote it, and verify_quote to check any wording before you print it.
* CITE EVERY CLAIM with the cite_as marker the tool gave you, inline: "Mandeville makes luxury the
  engine of trade [S4]." A marker is clickable; prose like "in the Fable of the Bees, p. 12" is
  not. Never invent a marker and never cite one you were not given.
* QUOTE EXACTLY. Spelling is archaic; do not modernise it. If you are quoting from memory, run
  verify_quote first — a quotation the tool cannot find must not appear.
* Argue the strongest version of your side. Do not straw-man the opposition; take their best
  reading and answer it.
* If the corpus does not support a point you would like to make, say so and make a weaker point
  that it does support. A conceded point argued honestly is worth more here than a confident one
  with nothing behind it.
* Be concrete and compact. Three grounded arguments beat eight assertions."""

DEBATE_OPENING = """Write your opening statement: your strongest case for your side, grounded in
the corpus and cited. If the other side has already opened, you may engage what they actually
said — but do not answer arguments nobody has made."""

DEBATE_REBUTTAL = """Your opponent has spoken. Their argument is above.

Answer it. Quote or name the specific claim you are contesting, then say what the corpus actually
shows — with a marker. Where they are right, concede it plainly and explain why your side survives
anyway. Add new ground of your own only where it advances the motion. Do not repeat your opening."""

DEBATE_CLOSING = """Write your closing. What did this exchange actually establish for your side,
and what did your opponent fail to answer? Cite the passages that carried the weight. Do not
introduce new evidence you have not already argued."""

JUDGE_PROMPT = """You are the adjudicator, not a debater. The full transcript is above.

You have the same tools, and you should use them to CHECK rather than to argue: run verify_quote
on any quotation that carried real weight, and read_source anything decisive that was only seen as
a snippet.

Write your adjudication as markdown, in this shape:

## Where they actually disagree
The real point of difference, stripped of rhetoric — often narrower than either side made it look.

## What the corpus supports
Claim by claim, which side's reading the passages bear out, with markers. Say plainly where a
claim was asserted without support, and where a quotation did not survive checking.

## What the corpus cannot settle
The parts of the motion these 197 sources simply do not decide. Be specific about why — the texts
are silent, or they conflict, or the question is not one a text can answer.

## Verdict
Which side argued the motion better ON THE EVIDENCE, and how confidently. It is legitimate to say
the motion is not decidable from this corpus; it is not legitimate to split the difference to
avoid choosing.

Then, in a fenced ```mermaid block, draw the shape of the disagreement as a graph: the motion, the
main claims each side made, and which claims answered which. Use `graph TD`, keep node labels
short, and quote any label containing punctuation."""


def debate_schedule(sides, rounds, judge):
    """Every turn the debate will consist of, in order.

    Written out as a list rather than computed inside the loop so that a
    paused debate can be resumed by index: turn N is always the same turn,
    whoever is asking and whenever they ask.
    """
    plan = []
    for rnd in range(1, rounds + 1):
        phase = "opening" if rnd == 1 else ("closing" if rnd == rounds else "rebuttal")
        for side in sides:
            plan.append({"side": side["name"], "round": rnd, "phase": phase})
    if judge:
        plan.append({"side": "Adjudicator", "round": rounds + 1, "phase": "verdict"})
    return plan


def debate_row(did):
    return db().execute("SELECT * FROM debates WHERE id=?", (did,)).fetchone()


def debate_state(did):
    """A debate as the UI wants it: its settings, its turns and the moderator's
    notes, gathered from the row and the session transcript."""
    row = debate_row(did)
    if not row:
        return None
    turns, notes = [], []
    for m in read_messages(row["session_id"]):
        if m.get("debate_id") != did:
            continue
        if m.get("kind") == "debate_turn":
            turns.append(m)
        elif m.get("kind") == "debate_note":
            notes.append(m)
    sides = json.loads(row["sides"] or "[]")
    plan = debate_schedule(sides, row["rounds"], bool(row["judge"]))
    return {
        "id": did, "motion": row["motion"], "sides": sides,
        "rounds": row["rounds"], "judge": bool(row["judge"]),
        "allow_web": bool(row["allow_web"]), "status": row["status"],
        "done_turns": row["done_turns"], "total_turns": len(plan),
        "next": plan[row["done_turns"]] if row["done_turns"] < len(plan) else None,
        "turns": turns, "notes": notes,
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def debates_for_session(sid):
    rows = db().execute(
        "SELECT * FROM debates WHERE session_id=? ORDER BY created_at", (sid,)).fetchall()
    return [debate_state(r["id"]) for r in rows]


def pending_notes(did, side_name):
    """What the moderator has said that this speaker has not been shown yet."""
    rows = db().execute(
        "SELECT * FROM debate_notes WHERE debate_id=? AND used=0 ORDER BY created_at",
        (did,)).fetchall()
    mine = [r for r in rows if r["addressed"] in ("both", side_name)]
    return mine


def mark_notes_used(ids):
    for i in ids:
        db().execute("UPDATE debate_notes SET used=1 WHERE id=?", (i,))
    db().commit()


def debate_sides(b):
    """Two sides, defaulted sensibly, so a motion alone is enough to start."""
    raw = b.get("sides") or []
    out = []
    for i, sd in enumerate(raw[:2]):
        out.append({
            "name": (sd.get("name") or f"Side {i + 1}")[:60],
            "stance": (sd.get("stance") or ("for the motion" if i == 0 else "against the motion"))[:200],
            "persona": (sd.get("persona") or "")[:400],
        })
    while len(out) < 2:
        i = len(out)
        out.append({
            "name": "For" if i == 0 else "Against",
            "stance": "for the motion" if i == 0 else "against the motion",
            "persona": "",
        })
    return out


def assemble_context(sid: str, budget_chars: int):
    """Attached items, newest last, trimmed to fit the window.

    Trimming drops from the largest item first rather than the oldest, so
    attaching one whole book cannot silently evict five carefully chosen
    passages.
    """
    rows = db().execute(
        "SELECT * FROM context_items WHERE session_id=? ORDER BY added_at", (sid,)
    ).fetchall()
    items = []
    for r in rows:
        items.append({
            "id": r["id"], "kind": r["kind"], "label": r["label"],
            "n_chars": r["n_chars"], "text": load_ctx_text(sid, r["id"]),
        })
    total = sum(len(i["text"]) for i in items)
    if total > budget_chars and items:
        order = sorted(range(len(items)), key=lambda k: -len(items[k]["text"]))
        over = total - budget_chars
        for k in order:
            if over <= 0:
                break
            t = items[k]["text"]
            cut = min(len(t) - 500, over)
            if cut > 0:
                items[k]["text"] = t[: len(t) - cut] + "\n…[trimmed to fit the context window]"
                items[k]["trimmed"] = True
                over -= cut
    parts = []
    for i in items:
        if not i["text"]:
            continue
        parts.append(f"=== CONTEXT [{i['kind']}] {i['label']} ===\n{i['text']}")
    return "\n\n".join(parts), items


def vllm_stream(messages, max_tokens=None, temperature=0.7, tools=None, provider=None):
    """Yield ("reasoning"|"content", text) and finally ("tool_calls", [...]).

    The model emits its reasoning in a separate field, so the two can be shown
    apart instead of the UI guessing where thinking ends. Tool calls arrive as
    deltas with an index, so they are accumulated per index and handed back
    once as a list.

    `max_tokens` is left out of the request unless something asks for a limit.
    It used to default to 4096, which quietly truncated a long adjudication
    mid-sentence; a reply should end when the model has finished, or when the
    context runs out, and not before.

    `provider` points the request at the reader's own endpoint when they have
    configured one, otherwise at this deployment's.
    """
    pv = provider or {"base": CFG["vllm"], "key": CFG["api_key"], "model": CFG["model"]}
    body = {
        "model": pv["model"],
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    cap = max_tokens if max_tokens is not None else CFG.get("max_output")
    if cap:
        body["max_tokens"] = int(cap)
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    req = urllib.request.Request(
        pv["base"].rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {pv['key']}"} if pv.get("key") else {})},
        method="POST",
    )
    try:
        r = urllib.request.urlopen(req, timeout=1800)
    except urllib.error.HTTPError as e:
        # the body carries what actually went wrong; "HTTP Error 400" alone
        # sent me hunting for a while
        try:
            detail = json.loads(e.read() or b"{}").get("error", {})
            msg = detail.get("message") if isinstance(detail, dict) else str(detail)
        except Exception:
            msg = ""
        raise RuntimeError(f"vLLM {e.code}: {msg or e.reason}") from None
    pending: dict[int, dict] = {}
    with r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                d = json.loads(payload)
            except json.JSONDecodeError:
                continue
            for ch in d.get("choices", []):
                delta = ch.get("delta") or {}
                rc = delta.get("reasoning") or delta.get("reasoning_content")
                if rc:
                    yield ("reasoning", rc)
                c = delta.get("content")
                if c:
                    yield ("content", c)
                for tc in delta.get("tool_calls") or []:
                    k = tc.get("index", 0)
                    slot = pending.setdefault(k, {"id": "", "name": "", "args": ""})
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        slot["name"] = fn["name"]
                    if fn.get("arguments"):
                        slot["args"] += fn["arguments"]
    if pending:
        yield ("tool_calls", [pending[k] for k in sorted(pending)])


# ------------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "AtlasChat/1.0"

    # ---------- plumbing ----------
    def _send(self, code, ctype, body: bytes, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj, extra=None):
        self._send(code, "application/json", json.dumps(obj, ensure_ascii=False).encode(), extra)

    def _body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def _token(self) -> str:
        return (self.headers.get("X-Atlas-Token") or "").strip()

    def _user(self):
        return user_for_token(self._token())

    def _need_user(self):
        u = self._user()
        if not u:
            self._json(401, {"error": "sign in first"})
            return None
        return u

    def _own_session(self, sid, user):
        row = db().execute(
            "SELECT * FROM sessions WHERE id=? AND user_id=?", (sid, user["id"])
        ).fetchone()
        if not row:
            self._json(404, {"error": "no such session"})
            return None
        return row

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,X-Atlas-Token")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt, *args):
        import sys
        sys.stderr.write("[atlas-chat] " + (fmt % args) + "\n")

    # ---------- routes ----------
    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/healthz":
            n_u = db().execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
            n_s = db().execute("SELECT COUNT(*) c FROM sessions").fetchone()["c"]
            return self._json(200, {
                "status": "ok", "users": n_u, "sessions": n_s,
                "model": CFG["model"], "max_ctx": CFG["max_ctx"],
            })
        if p == "/auth/me":
            u = self._user()
            return self._json(200, {"user": user_public(u) if u else None})
        if p == "/sessions":
            u = self._need_user()
            if not u:
                return
            rows = db().execute(
                "SELECT * FROM sessions WHERE user_id=? ORDER BY updated_at DESC", (u["id"],)
            ).fetchall()
            return self._json(200, {"sessions": [dict(r) for r in rows]})
        m = re.fullmatch(r"/sessions/([\w-]+)", p)
        if m:
            u = self._need_user()
            if not u:
                return
            row = self._own_session(m.group(1), u)
            if not row:
                return
            ctx = db().execute(
                "SELECT id,kind,label,ref,payload,n_chars,added_at FROM context_items "
                "WHERE session_id=? ORDER BY added_at", (m.group(1),)
            ).fetchall()
            return self._json(200, {
                "session": dict(row),
                "messages": read_messages(m.group(1)),
                "dropped": sorted(dropped_turns(m.group(1))),
                "context": [{**dict(c), "payload": json.loads(c["payload"] or "{}")} for c in ctx],
            })
        if p == "/auth/provider":
            u = self._need_user()
            if not u:
                return
            row = db().execute("SELECT * FROM user_providers WHERE user_id=?",
                               (u["id"],)).fetchone()
            default = {"base_url": "", "api_key": "", "model": "", "enabled": 0,
                       "check_ok": 0, "check_note": "", "checked_at": None}
            r = dict(row) if row else default
            # the key never comes back out, only enough to recognise it
            r["api_key"] = mask_key(r.get("api_key") or "")
            r["has_key"] = bool(row and row["api_key"])
            return self._json(200, {
                "provider": r,
                "deployment": {
                    "base_url": CFG["vllm"], "model": CFG["model"],
                    "max_ctx": CFG["max_ctx"],
                    "max_ctx_effective": effective_ctx(
                        {"base": CFG["vllm"], "key": CFG["api_key"], "model": CFG["model"]}),
                    "max_output": CFG.get("max_output")},
            })
        m = re.fullmatch(r"/debates/([\w-]+)", p)
        if m:
            u = self._need_user()
            if not u:
                return
            st = debate_state(m.group(1))
            if not st or not self._own_session(debate_row(m.group(1))["session_id"], u):
                return self._json(404, {"error": "no such debate"})
            return self._json(200, {"debate": st})
        m = re.fullmatch(r"/sessions/([\w-]+)/debates", p)
        if m:
            u = self._need_user()
            if not u:
                return
            if not self._own_session(m.group(1), u):
                return
            return self._json(200, {"debates": debates_for_session(m.group(1))})
        m = re.fullmatch(r"/sessions/([\w-]+)/export", p)
        if m:
            u = self._need_user()
            if not u:
                return
            row = self._own_session(m.group(1), u)
            if not row:
                return
            ctx = db().execute(
                "SELECT id,kind,label,ref,payload,n_chars FROM context_items WHERE session_id=?",
                (m.group(1),)
            ).fetchall()
            lines = [json.dumps({
                "type": "session",
                "id": row["id"], "title": row["title"],
                "created_at": row["created_at"], "updated_at": row["updated_at"],
                "model": row["model"], "exported_at": time.time(),
                "exported_by": u["username"],
                "context": [{**dict(c), "payload": json.loads(c["payload"] or "{}"),
                             "text": load_ctx_text(m.group(1), c["id"])} for c in ctx],
            }, ensure_ascii=False)]
            for msg in read_messages(m.group(1)):
                lines.append(json.dumps({"type": "message", **msg}, ensure_ascii=False))
            body = ("\n".join(lines) + "\n").encode()
            safe = re.sub(r"[^A-Za-z0-9._-]", "_", row["title"])[:60] or "session"
            return self._send(200, "application/x-ndjson", body, {
                "Content-Disposition": f'attachment; filename="atlas-{safe}.jsonl"'
            })
        self._json(404, {"error": "not found"})

    def do_POST(self):
        p = self.path.split("?")[0]
        try:
            if p == "/auth/register":
                return self.register()
            if p == "/auth/login":
                return self.login()
            if p == "/auth/logout":
                db().execute("DELETE FROM auth_tokens WHERE token=?", (self._token(),))
                db().commit()
                return self._json(200, {"ok": True})
            if p == "/auth/update":
                return self.update_account()
            if p == "/auth/provider":
                return self.set_provider()
            if p == "/auth/provider/test":
                return self.test_provider()
            if p == "/auth/forgot":
                return self.forgot()
            if p == "/auth/reset":
                return self.reset()
            if p == "/sessions":
                return self.new_session()
            if p == "/sessions/import":
                return self.import_session()
            if p == "/chat":
                return self.chat()
            if p == "/debate":
                return self.debate()
            m = re.fullmatch(r"/debates/([\w-]+)/(pause|note)", p)
            if m:
                return self.debate_action(m.group(1), m.group(2))
            m = re.fullmatch(r"/sessions/([\w-]+)/history", p)
            if m:
                return self.history_edit(m.group(1))
            m = re.fullmatch(r"/sessions/([\w-]+)/(rename|delete|context/add|context/remove)", p)
            if m:
                return self.session_action(m.group(1), m.group(2))
        except Exception as e:  # a handler crash must not take the server down
            import traceback
            traceback.print_exc()
            return self._json(500, {"error": str(e)})
        self._json(404, {"error": "not found"})

    # ---------- auth handlers ----------
    def register(self):
        b = self._body()
        un = (b.get("username") or "").strip()
        em = (b.get("email") or "").strip()
        pw = b.get("password") or ""
        if not USERNAME_RE.fullmatch(un):
            return self._json(400, {"error": "username: 3-32 chars, letters/digits/._-"})
        if not EMAIL_RE.fullmatch(em):
            return self._json(400, {"error": "that does not look like an email address"})
        if len(pw) < 8:
            return self._json(400, {"error": "password must be at least 8 characters"})
        salt = secrets.token_hex(16)
        try:
            cur = db().execute(
                "INSERT INTO users(username,email,display_name,pw_hash,pw_salt,created_at) "
                "VALUES(?,?,?,?,?,?)",
                (un, em, b.get("display_name") or un, hash_pw(pw, salt), salt, time.time()),
            )
            db().commit()
        except sqlite3.IntegrityError as e:
            field = "username" if "username" in str(e) else "email"
            return self._json(409, {"error": f"that {field} is already registered"})
        row = db().execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
        return self._json(200, {"token": issue_token(row["id"]), "user": user_public(row)})

    def login(self):
        b = self._body()
        who = (b.get("username_or_email") or b.get("username") or "").strip()
        row = db().execute(
            "SELECT * FROM users WHERE username=? OR email=?", (who, who)
        ).fetchone()
        if not row or not check_pw(b.get("password") or "", row["pw_salt"], row["pw_hash"]):
            return self._json(401, {"error": "wrong username or password"})
        return self._json(200, {"token": issue_token(row["id"]), "user": user_public(row)})

    def update_account(self):
        u = self._need_user()
        if not u:
            return
        b = self._body()
        # changing anything sensitive re-checks the current password
        newpw = b.get("password")
        newem = (b.get("email") or "").strip()
        if (newpw or newem) and not check_pw(b.get("current_password") or "", u["pw_salt"], u["pw_hash"]):
            return self._json(401, {"error": "current password is wrong"})
        sets, args = [], []
        if b.get("display_name") is not None:
            sets.append("display_name=?")
            args.append(b["display_name"][:64])
        if newem:
            if not EMAIL_RE.fullmatch(newem):
                return self._json(400, {"error": "that does not look like an email address"})
            sets.append("email=?")
            args.append(newem)
        if newpw:
            if len(newpw) < 8:
                return self._json(400, {"error": "password must be at least 8 characters"})
            salt = secrets.token_hex(16)
            sets += ["pw_hash=?", "pw_salt=?"]
            args += [hash_pw(newpw, salt), salt]
        if not sets:
            return self._json(400, {"error": "nothing to change"})
        args.append(u["id"])
        try:
            db().execute(f"UPDATE users SET {','.join(sets)} WHERE id=?", args)
            db().commit()
        except sqlite3.IntegrityError:
            return self._json(409, {"error": "that email is already registered"})
        if newpw:  # a password change invalidates every other sign-in
            db().execute("DELETE FROM auth_tokens WHERE user_id=? AND token<>?", (u["id"], self._token()))
            db().commit()
        row = db().execute("SELECT * FROM users WHERE id=?", (u["id"],)).fetchone()
        return self._json(200, {"user": user_public(row)})

    def forgot(self):
        b = self._body()
        em = (b.get("email") or "").strip()
        row = db().execute("SELECT * FROM users WHERE email=?", (em,)).fetchone()
        if not row:
            # do not confirm which addresses are registered
            return self._json(200, {"ok": True, "reset_token": None,
                                    "note": "if that address is registered, a reset code has been issued"})
        tok = secrets.token_urlsafe(24)
        db().execute("UPDATE users SET reset_token=?, reset_expires=? WHERE id=?",
                     (tok, time.time() + 3600, row["id"]))
        db().commit()
        # No mail server is configured on this host, so the code is returned
        # for the user to copy rather than pretending an email was sent.
        return self._json(200, {"ok": True, "reset_token": tok, "expires_in": 3600,
                                "note": "no mail server is configured — copy this code"})

    def reset(self):
        b = self._body()
        tok = (b.get("reset_token") or "").strip()
        pw = b.get("password") or ""
        if len(pw) < 8:
            return self._json(400, {"error": "password must be at least 8 characters"})
        row = db().execute(
            "SELECT * FROM users WHERE reset_token=? AND reset_expires>?", (tok, time.time())
        ).fetchone()
        if not row:
            return self._json(400, {"error": "that reset code is wrong or has expired"})
        salt = secrets.token_hex(16)
        db().execute(
            "UPDATE users SET pw_hash=?, pw_salt=?, reset_token=NULL, reset_expires=NULL WHERE id=?",
            (hash_pw(pw, salt), salt, row["id"]),
        )
        db().execute("DELETE FROM auth_tokens WHERE user_id=?", (row["id"],))
        db().commit()
        return self._json(200, {"ok": True, "token": issue_token(row["id"]),
                                "user": user_public(row)})

    # ---------- session handlers ----------
    def new_session(self):
        u = self._need_user()
        if not u:
            return
        b = self._body()
        sid = secrets.token_urlsafe(12).replace("-", "_")
        now = time.time()
        db().execute(
            "INSERT INTO sessions(id,user_id,title,created_at,updated_at,model) VALUES(?,?,?,?,?,?)",
            (sid, u["id"], (b.get("title") or "New conversation")[:120], now, now, CFG["model"]),
        )
        db().commit()
        row = db().execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        return self._json(200, {"session": dict(row)})

    def set_provider(self):
        """Save the reader's own endpoint. Nothing is switched on until it has
        been tested, so a typo cannot silently break every later answer."""
        u = self._need_user()
        if not u:
            return
        b = self._body()
        row = db().execute("SELECT * FROM user_providers WHERE user_id=?", (u["id"],)).fetchone()
        base = (b.get("base_url") or "").strip()
        model = (b.get("model") or "").strip()
        # an empty key field means "keep the one you have", not "clear it"
        key = b.get("api_key")
        key = (row["api_key"] if row else "") if key is None or key == "" else key.strip()
        enabled = bool(b.get("enabled"))
        if enabled and not (base and model):
            return self._json(400, {"error": "an endpoint and a model are both needed"})
        now = time.time()
        if row:
            db().execute(
                "UPDATE user_providers SET base_url=?, api_key=?, model=?, enabled=?, "
                "updated_at=? WHERE user_id=?",
                (base, key, model, int(enabled), now, u["id"]))
        else:
            db().execute(
                "INSERT INTO user_providers(user_id,base_url,api_key,model,enabled,updated_at) "
                "VALUES(?,?,?,?,?,?)", (u["id"], base, key, model, int(enabled), now))
        db().commit()
        r = dict(db().execute("SELECT * FROM user_providers WHERE user_id=?",
                              (u["id"],)).fetchone())
        r["has_key"] = bool(r["api_key"])
        r["api_key"] = mask_key(r["api_key"])
        return self._json(200, {"provider": r})

    def test_provider(self):
        """Make a real request with the real parameters and say what happened.

        A stored key is not a working key. This sends an actual completion and
        then a tool call, because an agent that cannot call tools produces
        answers with no citations, which is the failure people would otherwise
        find out about much later."""
        u = self._need_user()
        if not u:
            return
        b = self._body()
        row = db().execute("SELECT * FROM user_providers WHERE user_id=?", (u["id"],)).fetchone()
        base = (b.get("base_url") or (row["base_url"] if row else "") or "").strip()
        model = (b.get("model") or (row["model"] if row else "") or "").strip()
        key = b.get("api_key")
        if key is None or key == "":
            key = row["api_key"] if row else ""
        if not base or not model:
            return self._json(400, {"error": "give an endpoint and a model to test"})
        res = check_provider(base, key, model)
        if res.get("ok"):
            res.update(check_provider_tools(base, key, model))
        note = (f"{res.get('model')} answered in {res.get('took_ms')}ms"
                if res.get("ok") else res.get("error", "failed"))
        if row:
            db().execute(
                "UPDATE user_providers SET checked_at=?, check_ok=?, check_note=? WHERE user_id=?",
                (time.time(), int(bool(res.get("ok"))), note[:300], u["id"]))
            db().commit()
        return self._json(200, {"result": res})

    def debate_action(self, did, action):
        """pause a running debate, or hand the next speaker a moderator's point."""
        u = self._need_user()
        if not u:
            return
        row = debate_row(did)
        if not row or not self._own_session(row["session_id"], u):
            return self._json(404, {"error": "no such debate"})
        b = self._body()
        if action == "pause":
            # the running request notices this between turns and stops cleanly
            db().execute("UPDATE debates SET status='paused', updated_at=? WHERE id=?",
                         (time.time(), did))
            db().commit()
            return self._json(200, {"debate": debate_state(did)})
        # a note
        text = (b.get("text") or "").strip()
        if not text:
            return self._json(400, {"error": "say something"})
        to = (b.get("addressed") or "both").strip() or "both"
        names = {x["name"] for x in json.loads(row["sides"] or "[]")} | {"both", "Adjudicator"}
        if to not in names:
            to = "both"
        now = time.time()
        db().execute(
            "INSERT INTO debate_notes(debate_id,addressed,text,after_turn,used,created_at) "
            "VALUES(?,?,?,?,0,?)", (did, to, text, row["done_turns"], now))
        db().commit()
        # in the transcript too, so the exchange reads as one conversation
        append_message(row["session_id"], {
            "role": "user", "kind": "debate_note", "debate_id": did,
            "addressed": to, "text": text, "content": text, "ts": now,
            "after_turn": row["done_turns"],
        })
        return self._json(200, {"ok": True, "debate": debate_state(did)})

    def history_edit(self, sid):
        """Take exchanges out of the history, or put them back.

        Body: {"drop": [i, ...]} and/or {"restore": [i, ...]}, indices into the
        message list as the session endpoint returns it. Or {"restore": "all"}.
        """
        u = self._need_user()
        if not u:
            return
        row = self._own_session(sid, u)
        if not row:
            return
        b = self._body()
        n = len(read_messages(sid))
        restore = b.get("restore")
        if restore == "all":
            db().execute("DELETE FROM dropped_turns WHERE session_id=?", (sid,))
            db().commit()
        else:
            for i in restore or []:
                set_dropped(sid, i, False)
        for i in b.get("drop") or []:
            if 0 <= int(i) < n:
                set_dropped(sid, i, True)
        cut = sorted(dropped_turns(sid))
        return self._json(200, {"dropped": cut, "n_messages": n,
                                "in_history": n - len(cut)})

    def session_action(self, sid, action):
        u = self._need_user()
        if not u:
            return
        row = self._own_session(sid, u)
        if not row:
            return
        b = self._body()
        if action == "rename":
            db().execute("UPDATE sessions SET title=?, updated_at=? WHERE id=?",
                         ((b.get("title") or "Untitled")[:120], time.time(), sid))
            db().commit()
            return self._json(200, {"ok": True})
        if action == "delete":
            db().execute("DELETE FROM sessions WHERE id=?", (sid,))
            db().commit()
            try:
                session_path(sid).unlink(missing_ok=True)
                d = SESSION_DIR / f"{sid}.ctx"
                if d.exists():
                    for f in d.iterdir():
                        f.unlink()
                    d.rmdir()
            except OSError:
                pass
            return self._json(200, {"ok": True})
        if action == "context/add":
            added = []
            for it in (b.get("items") or [])[:20]:
                built = build_context_item(it)
                n = save_ctx_text(sid, built["id"], built["text"])
                db().execute(
                    "INSERT INTO context_items(id,session_id,kind,label,ref,payload,n_chars,added_at) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (built["id"], sid, built["kind"], built["label"], built["ref"],
                     json.dumps(built["payload"]), n, built["added_at"]),
                )
                added.append({k: built[k] for k in ("id", "kind", "label", "ref", "payload")} | {"n_chars": n})
            db().commit()
            touch_session(sid)
            return self._json(200, {"added": added})
        if action == "context/remove":
            for cid in (b.get("ids") or []):
                db().execute("DELETE FROM context_items WHERE id=? AND session_id=?", (cid, sid))
                try:
                    ctx_text_path(sid, cid).unlink(missing_ok=True)
                except OSError:
                    pass
            db().commit()
            touch_session(sid)
            return self._json(200, {"ok": True})
        return self._json(404, {"error": "unknown action"})

    def import_session(self):
        u = self._need_user()
        if not u:
            return
        b = self._body()
        raw = b.get("jsonl") or ""
        head, msgs = None, []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") == "session":
                head = d
            elif d.get("type") == "message" or "role" in d:
                msgs.append({k: v for k, v in d.items() if k != "type"})
        if head is None and not msgs:
            return self._json(400, {"error": "no session or messages found in that file"})
        sid = secrets.token_urlsafe(12).replace("-", "_")
        now = time.time()
        title = ((head or {}).get("title") or "Imported conversation")[:120]
        db().execute(
            "INSERT INTO sessions(id,user_id,title,created_at,updated_at,n_messages,model) "
            "VALUES(?,?,?,?,?,?,?)",
            (sid, u["id"], title, now, now, len(msgs), (head or {}).get("model") or CFG["model"]),
        )
        for m in msgs:
            append_message(sid, m)
        for c in ((head or {}).get("context") or []):
            cid = secrets.token_urlsafe(9)
            n = save_ctx_text(sid, cid, c.get("text") or "")
            db().execute(
                "INSERT INTO context_items(id,session_id,kind,label,ref,payload,n_chars,added_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (cid, sid, c.get("kind") or "note", c.get("label") or "imported",
                 c.get("ref") or "", json.dumps(c.get("payload") or {}), n, now),
            )
        db().commit()
        row = db().execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        return self._json(200, {"session": dict(row), "n_messages": len(msgs)})

    # ---------- chat ----------
    def debate(self):
        """Run a debate, or carry on one that was paused.

        Two agents argue a motion and a third adjudicates. Everything shares
        one citation table, so [S7] is the same passage in the opening, the
        rebuttal and the verdict.

        The debate is a row in the database and its turns are records in the
        session transcript, so it belongs to the account, survives a reload,
        and can be paused and picked up at the turn it stopped on. A moderator
        — the reader — can put arguments to either side between turns.
        """
        u = self._need_user()
        if not u:
            return
        b = self._body()

        did = b.get("debate_id")
        if did:
            row = debate_row(did)
            if not row or not self._own_session(row["session_id"], u):
                return self._json(404, {"error": "no such debate"})
            sid = row["session_id"]
            motion = row["motion"]
            sides = json.loads(row["sides"] or "[]")
            rounds, judge = row["rounds"], bool(row["judge"])
            allow_web = bool(row["allow_web"])
            start_at = row["done_turns"]
        else:
            sid = b.get("session_id")
            row = self._own_session(sid, u)
            if not row:
                return
            motion = (b.get("motion") or "").strip()
            if not motion:
                return self._json(400, {"error": "give a motion to debate"})
            rounds = max(1, min(int(b.get("rounds", 2)), 4))
            judge = bool(b.get("judge", True))
            allow_web = bool(b.get("allow_web"))
            sides = debate_sides(b)
            did = secrets.token_urlsafe(9).replace("-", "_")
            now = time.time()
            db().execute(
                "INSERT INTO debates(id,session_id,motion,sides,rounds,judge,allow_web,"
                "status,done_turns,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (did, sid, motion, json.dumps(sides), rounds, int(judge), int(allow_web),
                 "running", 0, now, now))
            db().commit()
            append_message(sid, {"role": "user", "kind": "debate_motion", "debate_id": did,
                                 "content": f"Debate: {motion}", "ts": now})
            start_at = 0

        plan = debate_schedule(sides, rounds, judge)
        pv = provider_for(u["id"])
        max_steps = int(b.get("max_steps", 14))
        turn_secs = float(b.get("turn_secs", 420))
        max_tokens = b.get("max_tokens") or None

        db().execute("UPDATE debates SET status='running', updated_at=? WHERE id=?",
                     (time.time(), did))
        db().commit()

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def emit(obj):
            self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode())
            self.wfile.flush()

        # A resumed debate replays what was already said so the reader sees the
        # whole thing, and so the speakers argue against the real transcript.
        prior = [m for m in read_messages(sid)
                 if m.get("debate_id") == did and m.get("kind") in ("debate_turn", "debate_note")]
        # Each turn stores the citation table AS IT STOOD when that turn ended,
        # which is cumulative. Concatenating every turn's copy therefore
        # restored the early rows once per later turn: a resumed debate came
        # back with S1..S6 twice over, an inflated row count, and new markers
        # numbered from the wrong place. Take the last turn's table, and dedupe
        # by marker in case an older transcript is not cumulative.
        cites = atlas_tools.Cites()
        rows, seen_ids = [], set()
        turn_recs = [m for m in prior if m.get("kind") == "debate_turn"]
        for m in reversed(turn_recs):
            for r in (m.get("sources") or []):
                if r.get("id") not in seen_ids:
                    seen_ids.add(r.get("id"))
                    rows.append(r)
            if rows:
                break          # that table was already cumulative
        for m in turn_recs:    # anything an older format left out
            for r in (m.get("sources") or []):
                if r.get("id") not in seen_ids:
                    seen_ids.add(r.get("id"))
                    rows.append(r)
        rows.sort(key=lambda r: int(re.sub(r"\D", "", str(r.get("id") or "0")) or 0))
        cites.rows = rows
        cites._seen = {(r.get("book_id"), r.get("page"), (r.get("snippet") or "")[:60]): r["id"]
                       for r in cites.rows}

        emit({"type": "debate_start", "debate_id": did, "motion": motion, "rounds": rounds,
              "sides": sides, "web": allow_web, "judge": judge, "model": pv["model"],
              "resumed": start_at > 0, "done_turns": start_at, "total_turns": len(plan),
              "history": prior, "sources": cites.as_list()})

        transcript = [{"side": m["side"], "round": m["round"], "phase": m["phase"],
                       "text": m.get("text") or ""}
                      for m in prior if m.get("kind") == "debate_turn"]
        mod_seen = [m for m in prior if m.get("kind") == "debate_note"]
        interrupted = False
        spoke = 0

        def sys_for(side):
            head = DEBATE_COMMON.format(motion=motion, stance=side["stance"])
            if side.get("persona"):
                head += ("\n\nYou are speaking as: " + side["persona"] +
                         "\nStay in that voice, but never let it licence a claim the corpus does "
                         "not support.")
            head += ("\n\nWeb access is ON. Use it only for what the corpus cannot supply, and "
                     "say when a point rests on it rather than on these 197 sources."
                     if allow_web else
                     "\n\nWeb access is OFF. Argue from the corpus alone.")
            head += ("\n\nA human moderator is watching and may put points to you between turns. "
                     "When they do, engage with what they actually said: take a good argument on "
                     "board and say so, and if you think they are wrong about the texts, say that "
                     "too — with a citation. Do not flatter them and do not simply obey.")
            return head

        def transcript_text():
            out = []
            for t in transcript:
                out.append(f"--- {t['side']} — {t['phase']} (round {t['round']}) ---\n{t['text']}")
            for m in mod_seen:
                who = m.get("addressed") or "both"
                out.append(f"--- the moderator, to {who} ---\n{m.get('text','')}")
            return "\n\n".join(out)

        def speak(slot):
            nonlocal spoke
            side = next((x for x in sides if x["name"] == slot["side"]), None)
            is_judge = slot["side"] == "Adjudicator"
            emit({"type": "turn_start", "side": slot["side"], "round": slot["round"],
                  "phase": slot["phase"]})

            notes = pending_notes(did, slot["side"])
            note_block = ""
            if notes:
                note_block = "\n\nThe moderator has just said:\n" + "\n".join(
                    f"  (to {n['addressed']}) {n['text']}" for n in notes)
                for n in notes:
                    # a note posted before a pause is already in the replayed
                    # records; appending it again would put it in the prompt twice
                    if not any(x.get("text") == n["text"] for x in mod_seen):
                        mod_seen.append({"kind": "debate_note", "addressed": n["addressed"],
                                         "text": n["text"]})
                emit({"type": "moderator_used", "side": slot["side"],
                      "notes": [{"addressed": n["addressed"], "text": n["text"]} for n in notes]})

            if is_judge:
                msgs = [
                    {"role": "system", "content":
                     ("You adjudicate a debate held over a corpus of 18th-century British moral "
                      "philosophy. The motion is:\n\n    " + motion +
                      "\n\nYou have the corpus tools. Use them to check, not to argue." +
                      ("\nWeb access is ON." if allow_web else "\nWeb access is OFF.") +
                      "\nA human moderator took part; weigh their points on the evidence like "
                      "anyone else's.")},
                    {"role": "user", "content": "The debate:\n\n" + transcript_text()[:80000]},
                    {"role": "user", "content": JUDGE_PROMPT + note_block},
                ]
                tokens = b.get("judge_tokens") or None
            else:
                instruction = (DEBATE_OPENING if slot["phase"] == "opening"
                               else DEBATE_CLOSING if slot["phase"] == "closing"
                               else DEBATE_REBUTTAL)
                msgs = [{"role": "system", "content": sys_for(side)}]
                prior_text = transcript_text()
                if prior_text:
                    msgs.append({"role": "user",
                                 "content": "The debate so far:\n\n" + prior_text[:60000]})
                msgs.append({"role": "user", "content": instruction + note_block})
                tokens = max_tokens

            tag = {"side": slot["side"], "round": slot["round"], "phase": slot["phase"]}
            sink = {}
            try:
                agent_turn(msgs, emit=emit, cites=cites, allow_web=allow_web,
                           max_steps=max_steps, max_tokens=tokens, tag=tag, sink=sink,
                           budget_secs=turn_secs, provider=pv)
            finally:
                text = "".join(sink.get("content") or [])
                if text.strip() or sink.get("trace"):
                    rec = {"role": "assistant", "kind": "debate_turn", "debate_id": did,
                           "side": slot["side"], "round": slot["round"], "phase": slot["phase"],
                           "text": text, "reasoning": "".join(sink.get("reasoning") or []),
                           "tools": sink.get("trace") or [],
                           "sources": cites.as_list(), "ts": time.time()}
                    append_message(sid, rec)
                    transcript.append({"side": slot["side"], "round": slot["round"],
                                       "phase": slot["phase"], "text": text})
                    if notes:
                        mark_notes_used([n["id"] for n in notes])
                    spoke += 1
                    db().execute(
                        "UPDATE debates SET done_turns=?, updated_at=? WHERE id=?",
                        (start_at + spoke, time.time(), did))
                    db().commit()
            emit({"type": "turn_end", "side": slot["side"], "round": slot["round"],
                  "phase": slot["phase"]})
            if cites.rows:
                emit({"type": "sources", "sources": cites.as_list()})

        try:
            for slot in plan[start_at:]:
                # a pause asked for from another tab stops the debate cleanly
                cur = debate_row(did)
                if cur and cur["status"] == "paused":
                    interrupted = True
                    break
                speak(slot)
        except (BrokenPipeError, ConnectionResetError):
            interrupted = True
        except Exception as e:
            import traceback
            traceback.print_exc()
            interrupted = True
            try:
                emit({"type": "error", "error": str(e)})
            except Exception:
                pass

        done = start_at + spoke
        status = "done" if done >= len(plan) and not interrupted else "paused"
        db().execute("UPDATE debates SET status=?, done_turns=?, updated_at=? WHERE id=?",
                     (status, done, time.time(), did))
        db().commit()
        touch_session(sid, spoke)
        if row["n_messages"] <= 1 and not b.get("debate_id"):
            db().execute("UPDATE sessions SET title=? WHERE id=?", (motion[:70], sid))
            db().commit()
        try:
            emit({"type": "done", "debate_id": did, "status": status,
                  "done_turns": done, "total_turns": len(plan),
                  "turns": spoke, "sources": len(cites.rows)})
        except Exception:
            pass

    def chat(self):
        u = self._need_user()
        if not u:
            return
        b = self._body()
        sid = b.get("session_id")
        row = self._own_session(sid, u)
        if not row:
            return
        user_msg = (b.get("message") or "").strip()
        if not user_msg:
            return self._json(400, {"error": "empty message"})
        allow_web = bool(b.get("allow_web"))
        pv = provider_for(u["id"])

        history = read_messages(sid)
        # An exchange the reader has taken out of the history is not sent. This
        # is the point of the feature: a long conversation that wandered can be
        # pruned back to the thread that matters instead of dragging every
        # false start into every later answer.
        cut = dropped_turns(sid)
        history = [h for i, h in enumerate(history) if i not in cut]
        ctx = effective_ctx(pv)
        budget = int(ctx * CHARS_PER_TOKEN * 0.55)
        ctx_text, ctx_items = assemble_context(sid, budget)

        # This model's chat template accepts exactly one system message, at the
        # start, so the prompt and the attached context travel together.
        system = SYSTEM_PROMPT
        # Say which way the web switch is set. Left unsaid, the model tries a
        # web_search that is not in its schema, wasting a round on a call the
        # gate then refuses.
        system += ("\n\nWeb access is ON for this conversation: web_search and web_fetch are "
                   "available. Use them only for what the corpus cannot supply, and mark anything "
                   "they yield as coming from outside the corpus."
                   if allow_web else
                   "\n\nWeb access is OFF for this conversation. There are no web tools; do not "
                   "attempt one. If the corpus cannot answer, say so and say what you searched.")
        if ctx_text:
            system += "\n\n================ ATTACHED CONTEXT ================\n\n" + ctx_text
        msgs = [{"role": "system", "content": system}]
        for h in history[-24:]:
            if h.get("role") in ("user", "assistant") and h.get("content"):
                msgs.append({"role": h["role"], "content": h["content"]})
        msgs.append({"role": "user", "content": user_msg})

        append_message(sid, {"role": "user", "content": user_msg, "ts": time.time()})
        touch_session(sid, 1)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def emit(obj):
            try:
                self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode())
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                raise

        approx_tokens = int(sum(len(m["content"]) for m in msgs) / CHARS_PER_TOKEN)
        emit({"type": "start", "context_items": len(ctx_items),
              "context_chars": len(ctx_text), "approx_prompt_tokens": approx_tokens,
              "model": pv["model"], "own_provider": pv["own"],
              "web": allow_web, "tools": True})

        # ---------------- agentic loop ----------------
        # The model may call tools, read what they return, and call more before
        # answering. Every passage a tool yields is registered in one citation
        # table for the turn, so a marker in the answer resolves to a book, a
        # page and (for a scan) the block the match came from.
        cites = atlas_tools.Cites()
        reasoning, content, trace = "", "", []
        MAX_STEPS = int(b.get("max_steps", 30))
        BUDGET_SECS = float(b.get("budget_secs", 900))
        want_check = bool(b.get("verify", True))
        check_text = ""

        # Sinks, so a turn cut off part-way can still be saved: agent_turn
        # raises out of the streaming loop and never returns, so its return
        # values are no help on a disconnect.
        answer_sink, check_sink = {}, {}

        try:
            emit({"type": "phase", "phase": "answer"})
            reasoning, content, trace = agent_turn(
                msgs, emit=emit, cites=cites, allow_web=allow_web,
                max_steps=MAX_STEPS, max_tokens=b.get("max_tokens") or None,
                sink=answer_sink, budget_secs=BUDGET_SECS, provider=pv,
            )

            # ---------------- self-check ----------------
            # A first draft is where quotations drift and markers get attached to
            # passages that are merely nearby. The model re-reads its own answer
            # with the tools still in hand and either stands by it or replaces it.
            if want_check and content.strip():
                emit({"type": "phase", "phase": "verify"})
                msgs.append({"role": "assistant", "content": content})
                msgs.append({"role": "user", "content": SELF_CHECK_PROMPT})
                c_reasoning, check_text, c_trace = agent_turn(
                    msgs, emit=emit, cites=cites, allow_web=allow_web,
                    max_steps=int(b.get("check_steps", 8)),
                    max_tokens=b.get("max_tokens") or None,
                    channel="check", sink=check_sink, provider=pv,
                    budget_secs=float(b.get("check_budget_secs", 420)),
                )
                # mark them so the reader can see what the check actually did;
                # the check's own prose is only "VERDICT: ..." plus the
                # corrected answer, which is shown below anyway
                for t in c_trace:
                    t["phase"] = "verify"
                trace += c_trace
                reasoning += c_reasoning
                body = re.sub(r"^\s*VERDICT:\s*(stands|revised)\s*", "", check_text,
                              flags=re.I).strip()
                revised = re.match(r"\s*VERDICT:\s*revised", check_text, re.I) and len(body) > 40
                if revised:
                    emit({"type": "answer_replace"})
                    emit({"type": "content", "text": body})
                    content = body
                    emit({"type": "checked", "outcome": "revised"})
                else:
                    emit({"type": "checked", "outcome": "stands"})
            if cites.rows:
                emit({"type": "sources", "sources": cites.as_list()})
        except (BrokenPipeError, ConnectionResetError):
            # The client went away — a closed tab, a lost connection. Fall
            # through and save what was produced: the comment here used to
            # claim the turn was still saved while the return skipped the
            # save, so an answer the model had finished writing was thrown
            # away because nobody was watching it arrive.
            pass
        except Exception as e:
            # When the reader is on their own endpoint, say so: otherwise a
            # broken base URL or an expired key looks like the corpus failing,
            # and there is nothing pointing at where to fix it.
            msg = str(e)
            if pv.get("own"):
                msg = (f"{msg}\n\n(This went to your own endpoint — {pv['base']} , model "
                       f"{pv['model']}. Check it under Account settings, or turn it off to use "
                       f"this deployment's model.)")
            try:
                emit({"type": "error", "error": msg})
            except (BrokenPipeError, ConnectionResetError):
                pass

        # Recover anything the interrupted turn had already written.
        if not content:
            content = "".join(answer_sink.get("content") or [])
            reasoning = reasoning or "".join(answer_sink.get("reasoning") or [])
            trace = trace or (answer_sink.get("trace") or [])
        if want_check and not check_text:
            check_text = "".join(check_sink.get("content") or [])
        if not (content.strip() or trace):
            return   # nothing was said and nothing was looked at

        rec = {
            "role": "assistant",
            "content": content,
            "reasoning": reasoning,
            "check": check_text,
            # a turn answered without the corpus tools has to say so on reload,
            # not only while it streams
            "no_tools": bool(answer_sink.get("tools_off")),
            "ts": time.time(),
            "tools": trace,
            "sources": cites.as_list(),
            "web": allow_web,
            "context_items": [{"id": i["id"], "kind": i["kind"], "label": i["label"]} for i in ctx_items],
        }
        append_message(sid, rec)
        touch_session(sid, 1)
        # name the session from its first exchange
        if row["n_messages"] <= 1:
            title = user_msg.strip().split("\n")[0][:70]
            db().execute("UPDATE sessions SET title=? WHERE id=?", (title or "New conversation", sid))
            db().commit()
        try:
            emit({"type": "done", "reasoning_chars": len(rec["reasoning"]),
                  "content_chars": len(rec["content"]), "tool_calls": len(trace),
                  "sources": len(cites.rows)})
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8793)
    ap.add_argument("--vllm", default=os.environ.get("ATLAS_VLLM", CFG["vllm"]))
    ap.add_argument("--model", default=os.environ.get("ATLAS_MODEL", CFG["model"]))
    args = ap.parse_args()
    CFG["vllm"] = args.vllm
    CFG["model"] = args.model
    init_db()
    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    srv.daemon_threads = True
    print(f"atlas chat on http://0.0.0.0:{args.port} -> {CFG['vllm']} ({CFG['model']})")
    print(f"store: {DATA}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
