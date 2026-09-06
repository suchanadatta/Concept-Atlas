# BMoral — British Moral Philosophy Corpus System

A scholar's search system over **129 books of 18th-century British moral
philosophy** (~27,000 pages): OCR with word-level geometry, a verified
202-concept knowledge graph, hybrid semantic search (Jasper embeddings +
archaic-aware lexical), and an interactive 2D/3D concept-graph UI.

## What's in this repo

| Path | Contents |
|---|---|
| `tools/` | OCR pipeline, Jasper index builder + semantic search server, validators, audit suite |
| `outputs/` | **Committed OCR extractions** — per-book `.pages.jsonl` (blocks + word `bbox_pts` + paragraphs + page numbers), `.json`, `.md` |
| `Concept Maps/final/` | **Committed knowledge graph** — 202 concepts, 1,099 relations, 2,072 verbatim evidence paragraphs, 42 research queries |
| `Concept Maps/graph-ui/` | The full web UI (search engine, PDF/TXT reader with annotations, concept graphs, query graphs) |
| `models/` | Model weights & embedding indexes (NOT committed — rebuilt by scripts) |
| `data/` | Source PDFs/TXTs (NOT committed — see `data/.gitkeep`) |
| `log/` | Pipeline orchestration scripts + server launchers |
| `plans/` | Engineering decision/audit logs from the build process |

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
- **Ask** → chat over the corpus with tools: hybrid/semantic/lexical search,
  read any page range, look up a concept and walk its relations 1–2 hops,
  the query network, the author registry, and an optional web search behind
  a toggle. Citations are registered per turn and clickable — a marker opens
  that book at that page with the cited region highlighted.
- **Docs** → in-app documentation

## Data model

Each book gets `<BOOK_ID>.pages.jsonl` — one line per page:
`blocks[]` (text, zone, `bbox_pts` in PDF points, `words[]` with per-word
`bbox_pts`), `paragraphs[]` (char-offset ranges + rebased word boxes),
`book_page_number`, `printed_page_number`, two-up sheet detection.

The concept graph (`Concept Maps/final/`) was built by 15 extractor agents →
20 verifiers → 20 double-auditors → 25 independent auditors; every evidence
quote is a verbatim OCR substring with page/box citations.
