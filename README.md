# Concept Atlas - Evidence-Grounded Conceptual Retrieval 

A scholar's search system over **134 books of 18th-century British moral philosophy** (~27,000 pages): OCR with word-level representation, a verified 202-concept knowledge graph, hybrid semantic search (Jasper embeddings + archaic-aware lexical), and an interactive 2D/3D concept-graph UI.

## What's in this repo

| Path | Contents |
|---|---|
| `tools/` | OCR pipeline, Jasper index builder + semantic search server, validators, audit suite |
| `outputs/` | **Committed OCR extractions** — per-book `.pages.jsonl` (blocks + word `bbox_pts` + paragraphs + page numbers), `.json`, `.md` |
| `Concept Maps/final/` | **Committed knowledge graph** — 202 concepts, 1,099 relations, 2,072 verbatim evidence paragraphs, 42 research queries |
| `Concept Maps/graph-ui/` | The full web UI (search engine, PDF/TXT reader with annotations, concept graphs, query graphs) |
| `models/` | Model weights & embedding indexes (NOT committed — rebuilt by scripts) |
| `data/` | Source PDFs/TXTs (see `data/txt_books`); Queries (see `data/query.tsv`); Authors' brief biography (see `author_bio.tsv`) |
| `log/` | Pipeline orchestration scripts + server launchers |
| `plans/` | Engineering decision/audit logs from the build process |

## Configuration

One file, `.env` at the repo root — copy `.env.example` and edit. It sets the model endpoint, the model, the context window, the ports, and whether the chat agent may search the web. Real environment variables override it, so a container or systemd unit needs no edits.

```
ATLAS_VLLM=http://localhost:8000/v1     # any OpenAI-compatible endpoint
ATLAS_MODEL=Qwen3.8-27B-TURBO
ATLAS_API_KEY=                          # local vLLM usually needs none
ATLAS_MAX_OUTPUT_TOKENS=                # empty = no cap on a reply's length
```

Readers can also point Ask and Debate at **their own** OpenAI-compatible
endpoint from *Account settings* — their key, their model, their quota. The
key is stored against the account and never returned to the browser except
masked. Nothing is switched on until **Test it** has made a real request: it
reports the reply, token usage, the finish reason, and whether the model can
call tools, because an agent that cannot call tools produces answers with no
citations.

## Quickstart

```bash
# one command on a fresh clone (uv + GPU required for the semantic index):
bash scripts/bootstrap.sh
```

This installs deps (uv + Python 3.12), downloads the Jasper embedding model
(`infgrad/Jasper-Token-Compression-600M`, ~1.2 GB, one-time), builds the
semantic index over the committed OCR text, and prints the server start
commands. Manual equivalent:

```bash
uv venv --python 3.12 && uv pip install -r pyproject.toml

# 1) OCR new PDFs          (needs GPU ~10GB for vLLM)
bash log/run_full_68.sh

# 2) Build the semantic index   (needs free GPU)
python tools/build_jasper_index.py --device cuda --batch 128
python tools/build_concept_vectors.py cuda          # concept vectors for query graphs

# 3) Launch
python tools/jasper_search_server.py --port 8790 --device cuda   # semantic backend
cd "Concept Maps/graph-ui" && ./start.sh                          # UI on :8788
```

**What works without any downloads** (keyword + BM25 search + full UI):
the committed OCR text (`outputs/`, 129 books) and concept map
(`Concept Maps/final/`) are in the repo — `serve.py` starts immediately.
Semantic mode additionally needs the Jasper model + embeddings (bootstrap
step 2–3).

## Reaching it from outside

`tools/zrok-share.sh` puts the UI on a public URL that does not change between
restarts. zrok v2 keeps the *name* and the *tunnel* as separate things: the
name is reserved to the account once and outlives everything, while the tunnel
is torn down whenever the process stops. Bind every run to the same reserved
name and the URL is stable.

```bash
zrok enable <account-token>          # once per machine
tools/zrok-share.sh                  # reserves ATLAS_ZROK_NAME, then shares :8788
# https://concept-atlas.shares.zrok.io
```

A public URL is only as durable as what sits behind it, so the whole stack
runs under systemd:

```bash
tools/install-services.sh              # index, chat, UI, tunnel
sudo loginctl enable-linger "$USER"    # only if it should survive logout/reboot
```

Four user units, ordered for real rather than hopefully: the index holds its
start job open until `/healthz` answers (about twenty seconds while the model
loads), the chat service and UI start after that, and the tunnel starts last.
Each restarts on failure, verified by `kill -9` on all three. A restart of the
UI does not bounce the tunnel — only ordering is shared, not restarts, which
matters because a new share takes a few seconds to route and returns 502 until
it does.

```bash
systemctl --user status  concept-atlas-{jasper,chat,ui,zrok}
journalctl --user -u concept-atlas-ui -f
```

A share only releases its name on a clean `SIGTERM`; after a `kill -9` or a
power cut the name is still held and the next start would fail with a 409, so
the script sweeps the stale share before sharing again.

The free zrok service shows a one-time interstitial ("You are about to visit
a zrok share…") to browser visitors before the app loads. It is triggered by
the browser's `Accept`/User-Agent, so `curl` and every API client go straight
through; anything that needs to bypass it can send a `skip_zrok_interstitial`
header with any value. Adding a verified credit card to the zrok account
removes it for good — the controller decides at *share creation* time, so
restart the service afterwards to recreate the share.

`zrok list namespaces` shows which namespaces the account may use. On the free
hosted service that is only `public` (`*.shares.zrok.io`), so the shape of the
URL is fixed and the name is the only part you choose; a custom domain needs a
self-hosted zrok instance.

One thing worth knowing about tunnels and token streams: the model can think
for a minute or more before its first token, and a silent connection looks
dead to anything in the middle — zrok's frontend hangs up at around sixty
seconds. `serve.py` therefore sends an SSE keepalive comment every
`ATLAS_SSE_HEARTBEAT` seconds (default 15) while a stream is quiet.

## The UI (`http://<host>:8788`)

- **Search** — natural-language queries; 🧠 semantic (Jasper hybrid, scored
  results) or ⌨ keyword (archaic-spelling aware: *vertue*, *loue*, *felf*)
- **Passages** → click → side-panel PDF reader at the exact page with
  word-level highlights; TXT books open in paragraph mode with word
  selection annotation
- **Concepts** → matched concepts → floating concept graph
- **Graph tab** → live **query graph**: concept matches + bridge concepts +
  documents + their interconnections (2D pan/zoom/hover + 3D orbit)
- **Explore** → the full 202-node concept map: per-relation colored/dashed
  edges, neighborhood isolation, spread control, edge clicks, dark mode
- **Written by** → filter the search results, the concept map (2D + 3D) and
  all three query-graph modes by author sex, joined on book id from
  `data/authors.csv`. Of 202 concepts the women in this corpus attest 99,
  13 of them attested by no male-authored book here.
- **Ask** → chat over the corpus with twelve tools: hybrid/semantic/lexical
  search, read any page range, look up a concept and walk its relations 1–2
  hops, compare two ideas and find where they are argued *together*, list the
  shelf, the query network, the author registry, `verify_quote` to check a
  quotation before printing it, and an optional web search behind a toggle.
  Citations are registered per turn and clickable — a marker opens that book
  at that page with the cited region highlighted. The answer is then re-read
  by the model with the tools still in hand, and either stands or is replaced;
  the panel says which. Markdown, tables and ```mermaid diagrams render.
  Around 30 tool rounds per question, so it keeps searching when unsure; the
  guards are a repeat-call memo, stall detection and a wall clock rather than
  a low ceiling. Web search runs on `ddgs` (real engines, pinned backends) with
  pagination, `site:` pinning, recency and news/catalogue verticals; `web_fetch`
  pages through a document too long for one call.
- **Conversation panel** → every exchange enumerated, and any of them droppable
  from the history: it stays in the transcript, struck through, but stops being
  sent — so a discussion that wandered can be pruned back to the thread that
  matters.
- **⚖ Debate** → two agents argue a motion out of the corpus, each finding its
  own evidence, then an adjudicator checks the quotations and reports where
  they actually disagreed, what the corpus bears out and what it cannot
  settle. One shared citation table across all three speakers, shown live and
  clickable (web → the page, corpus → the reader, concept → the map).
  Debates belong to the account: pause between turns and resume at the turn it
  stopped on. You moderate — put a point to either side or the adjudicator and
  the next speaker answers it.
- **Docs** → in-app documentation

## Data model

Each book gets `<BOOK_ID>.pages.jsonl` — one line per page:
`blocks[]` (text, zone, `bbox_pts` in PDF points, `words[]` with per-word
`bbox_pts`), `paragraphs[]` (char-offset ranges + rebased word boxes),
`book_page_number`, `printed_page_number`, two-up sheet detection.

The concept graph (`Concept Maps/final/`) was built by 15 extractor agents →
20 verifiers → 20 double-auditors → 25 independent auditors; every evidence
quote is a verbatim OCR substring with page/box citations.
