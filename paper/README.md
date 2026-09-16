# Two Descriptions of the Same Shelf

A paper written from the Concept Atlas corpus, comparing the hand-built
concept map against the dense vector index over the same 197 works.

    make analysis    # recompute everything from the corpus (needs the services up)
    make             # build paper.pdf
    make check       # fail on any LaTeX warning or bad box

## What is here

| path | what it is |
|---|---|
| `paper.tex`, `sections/` | the document |
| `analysis/*.py` | every number and figure in it |
| `data/*.json` | analysis output, committed so the paper builds without re-running |
| `figures/*.pdf` | generated figures |
| `generated/numbers.tex` | LaTeX macros built from `data/` — the prose quotes these, never literals |
| `tools/check_log.py` | the zero-warning gate |

## Analyses

- **a0** recovers publication years by reading imprints off the scans, and
  **a0b** measures how often that agrees with the catalogue.
- **a1** profiles the corpus: sources, decades, authors.
- **a2** takes the concept map apart: relation types, hubs, categories.
- **a3** is the centrepiece — concept *usage* vectors built from the corpus,
  compared against the curator's assertions and against the *definition*
  vectors the live query graph uses.
- **a4** compares BM25 and semantic retrieval on the same queries, through the
  running services.
- **a5** tracks the moral vocabulary across the period.
- **a6** compares the books by women with the books by men.

`a_support.py` builds the concept-to-passage index the others share; it takes a
few minutes and is cached in `data/concept_support.json` (gitignored, 2.8 MB).

## Notes

`a3` and `a4` need the Jasper service (`:8790`) and the UI (`:8788`) running.
The rest read `models/jasper_index_v2/` directly.

Numbers are never typed into the prose. If an analysis changes, re-run
`make analysis` and the document's figures change with it.
