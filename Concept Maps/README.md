# Concept Maps — British Moral Philosophy Corpus (129 books, 7.7M tokens)

## Overview
This folder contains the concept extraction and mapping for the entire 129-book corpus (68 OCR PDFs + 61 text files) covering 18th-century British moral philosophy. The work is divided among 15 parallel LLM agents (1M context each), each reading 8-9 books and extracting concepts, then merged into a unified category tree and concept graph optimized for 43 test queries.

## Structure
```
Concept Maps/
├── README.md                    # This file
├── NORMALIZATION_GUIDE.md      # Shared rules for concept IDs, labels, categories
├── SCHEMA.md                    # JSONL output schemas
├── shards.json                  # 15 shards (8-9 books each)
├── shards-agent-*.json          # Per-agent shard definitions
├── text_extracts/               # 129 text-only extracts (one per book, ~42M chars)
│   └── {book_id}.txt           # Clean text for LLM reading
├── raw/                         # Per-agent raw outputs (15 JSONL files)
│   └── agent-*.jsonl           # Concepts + evidence + relations (free discovery)
├── merged/                      # Consolidated outputs (after all agents + merger)
│   ├── category_tree.json      # Hierarchical category tree
│   ├── concept_graph.jsonl     # Full graph: nodes + edges
│   ├── inverted_index.jsonl    # Concept -> paragraphs (cross-book)
│   └── query_concept_map.json  # 43 queries -> ranked concepts
└── queries.txt                  # 43 test queries with narrations
```

## Workflow
1. **Map phase (15 agents, parallel):** Each agent reads its 8-9 books (text_extracts + optional geometry from .pages.jsonl for evidence), extracts concepts freely, writes to `raw/agent-{id}.jsonl`
2. **Reduce phase (1 merger agent):** Reads all 15 raw files, normalizes concept IDs/labels, merges duplicates, builds category tree and graph, optimizes for query relevance

## Key Constraints for Agents
- **Free discovery, disciplined normalization:** Discover categories yourself, but follow NORMALIZATION_GUIDE.md strictly for IDs/labels to avoid "love" vs "human love" divergence
- **Do NOT predefine categories** in prompt — let agents find them, then merger reconciles
- **Every concept must have evidence:** At least one paragraph excerpt with book_id, page, text
- **Query-aware:** Tag each concept with relevant query_ids from queries.txt

## Token Budget
- 129 books × ~325k chars avg = ~42M chars → ~10.5M tokens
- 15 agents × ~900k tokens each (8-9 books) fits in 1M context
- Text extracts used (not raw JSONL with geometry) to stay within budget
