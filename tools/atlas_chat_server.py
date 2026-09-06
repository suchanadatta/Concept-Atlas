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

CFG = {
    "vllm": "http://localhost:8000/v1",
    "model": "Qwen3.8-27B-TURBO",
    "max_ctx": 550_000,
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
2. DO NOT GIVE UP AFTER ONE CALL. If hybrid search returns nothing to the point:
     * reword in the period's own vocabulary (vertue, felf-love, the paffions);
     * try mode='semantic' for meaning, or 'bm25'/'keyword' for a literal word or rare name;
     * try find_concept — the map may hold the idea under a name you did not guess;
     * try concept_detail with hops=2 to reach it through a neighbouring concept.
   Only after several genuinely different attempts may you say the corpus does not address it.
3. When a snippet is not enough to settle what an author claims, read_source the page range.
4. Quote sparingly and exactly. Spelling is archaic — read through it and never silently modernise
   a quotation.

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


def vllm_stream(messages, max_tokens=4096, temperature=0.7, tools=None):
    """Yield ("reasoning"|"content", text) and finally ("tool_calls", [...]).

    The model emits its reasoning in a separate field, so the two can be shown
    apart instead of the UI guessing where thinking ends. Tool calls arrive as
    deltas with an index, so they are accumulated per index and handed back
    once as a list.
    """
    body = {
        "model": CFG["model"],
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    req = urllib.request.Request(
        CFG["vllm"].rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
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
                "context": [{**dict(c), "payload": json.loads(c["payload"] or "{}")} for c in ctx],
            })
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

        history = read_messages(sid)
        budget = int(CFG["max_ctx"] * CHARS_PER_TOKEN * 0.55)
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
              "model": CFG["model"], "web": allow_web, "tools": True})

        # ---------------- agentic loop ----------------
        # The model may call tools, read what they return, and call more before
        # answering. Every passage a tool yields is registered in one citation
        # table for the turn, so a marker in the answer resolves to a book, a
        # page and (for a scan) the block the match came from.
        cites = atlas_tools.Cites()
        schemas = atlas_tools.schemas(allow_web=allow_web)
        reasoning, content, trace = [], [], []
        MAX_STEPS = int(b.get("max_steps", 8))

        try:
            for step in range(MAX_STEPS):
                calls = None
                step_reasoning, step_content = [], []
                for kind, chunk in vllm_stream(
                    msgs, max_tokens=int(b.get("max_tokens", 4096)), tools=schemas
                ):
                    if kind == "reasoning":
                        step_reasoning.append(chunk)
                        emit({"type": "reasoning", "text": chunk})
                    elif kind == "content":
                        step_content.append(chunk)
                        emit({"type": "content", "text": chunk})
                    elif kind == "tool_calls":
                        calls = chunk
                reasoning.extend(step_reasoning)
                content.extend(step_content)

                if not calls:
                    break

                # the assistant turn that requested the tools has to go back in
                msgs.append({
                    "role": "assistant",
                    "content": "".join(step_content),
                    "tool_calls": [
                        {"id": c["id"] or f"call_{step}_{k}", "type": "function",
                         "function": {"name": c["name"], "arguments": c["args"] or "{}"}}
                        for k, c in enumerate(calls)
                    ],
                })
                for k, c in enumerate(calls):
                    try:
                        args = json.loads(c["args"] or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    emit({"type": "tool_call", "step": step, "name": c["name"], "args": args})
                    result = atlas_tools.run_tool(c["name"], args, cites, allow_web=allow_web)
                    summary = atlas_tools.summarise(c["name"], result)
                    trace.append({"step": step, "name": c["name"], "args": args,
                                  "summary": summary, "took_ms": result.get("took_ms")})
                    emit({"type": "tool_result", "step": step, "name": c["name"],
                          "summary": summary, "took_ms": result.get("took_ms")})
                    msgs.append({
                        "role": "tool",
                        "tool_call_id": c["id"] or f"call_{step}_{k}",
                        "name": c["name"],
                        "content": json.dumps(result, ensure_ascii=False)[:60000],
                    })
                if cites.rows:
                    emit({"type": "sources", "sources": cites.as_list()})
            else:
                emit({"type": "note",
                      "text": f"stopped after {MAX_STEPS} tool rounds"})
        except (BrokenPipeError, ConnectionResetError):
            return  # client went away mid-stream; the turn is still saved below
        except Exception as e:
            emit({"type": "error", "error": str(e)})

        rec = {
            "role": "assistant",
            "content": "".join(content),
            "reasoning": "".join(reasoning),
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
