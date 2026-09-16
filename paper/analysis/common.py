"""Shared loaders for the corpus, the concept map and the embedding index.

Every number in the paper comes from one of these; nothing is transcribed by
hand. Paths are resolved relative to the repository root so the scripts run
from anywhere.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAPER = REPO / "paper"
DATA = PAPER / "data"
FIGS = PAPER / "figures"
GRAPH = REPO / "Concept Maps" / "final" / "concept_graph.jsonl"
INVERTED = REPO / "Concept Maps" / "final" / "inverted_index.jsonl"
INDEX = REPO / "models" / "jasper_index_v2"
JASPER = os.environ.get("ATLAS_JASPER", "http://127.0.0.1:8790")
UI = os.environ.get("ATLAS_UI", "http://127.0.0.1:8788")

DATA.mkdir(parents=True, exist_ok=True)
FIGS.mkdir(parents=True, exist_ok=True)

# A book id is AUTHORKEY_YEAR_Title. The year is the only four-digit run in the
# 1500-1899 range that is not glued to another digit; \b fails here because the
# separator is an underscore, which is itself a word character.
YEAR_RE = re.compile(r"(?<!\d)(1[5-8]\d\d)(?!\d)")


def book_year(book_id: str) -> int | None:
    m = YEAR_RE.search(book_id)
    return int(m.group(1)) if m else None


def book_author_key(book_id: str) -> str:
    return book_id.split("_", 1)[0].lower()


def load_graph() -> tuple[list[dict], list[dict]]:
    nodes, edges = [], []
    with open(GRAPH, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            (nodes if d.get("type") == "node" else edges).append(d)
    return nodes, edges


def load_inverted() -> list[dict]:
    with open(INVERTED, encoding="utf-8") as f:
        return [json.loads(l) for l in f]


def load_meta() -> list[dict]:
    """Passage metadata, one row per embedding row, in index order."""
    with open(INDEX / "meta.jsonl", encoding="utf-8") as f:
        return [json.loads(l) for l in f]


def load_embeddings(mmap: bool = True):
    import numpy as np
    return np.load(INDEX / "embeddings.npy", mmap_mode="r" if mmap else None)


def post(path: str, payload: dict, base: str | None = None, timeout: int = 180):
    """Call the live search service — the same one the website uses."""
    url = (base or JASPER) + path
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def get(url: str, timeout: int = 60):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def save(name: str, obj) -> Path:
    p = DATA / name
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote {p.relative_to(REPO)}")
    return p


# ---------------------------------------------------------------- plotting
def style():
    """One look for every figure: serif to match the document, no chartjunk."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.dpi": 150,
        "savefig.dpi": 150,
        "font.family": "serif",
        "font.serif": ["DejaVu Serif"],
        "font.size": 8,
        "axes.titlesize": 9,
        "axes.labelsize": 8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linewidth": 0.5,
        "legend.frameon": False,
        "figure.constrained_layout.use": True,
    })
    return plt
