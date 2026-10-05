# JSONL Schemas — Concept Maps

## Per-Agent Raw Output: `raw/agent-{NN}.jsonl`
One JSON object per line, each line is a **concept node**. Schema:

```json
{
  "concept_id": "self_love",
  "concept_label": "Self-Love",
  "category_path": ["Moral Psychology", "Self-Love"],
  "aliases": ["self-love", "self love", "amour-propre"],
  "definition": "In 18th-century British moral philosophy, self-love denotes ... (2-4 sentences, grounded in the books read)",
  "query_relevance": ["self-love", "Cockburn and self-love", "Debates on whether humans are by nature self-interested..."],
  "books": [
    {"book_id": "BUTLER_1726_...", "author": "Butler", "year": "1726", "role": "primary"}
  ],
  "evidence": [
    {
      "book_id": "BUTLER_1726_...",
      "page": 42,
      "paragraph_id": "p_42_3",
      "text_excerpt": "Every particular affection, even the most properly benevolent, must be gratified...",
      "context": "Butler argues self-love is consistent with benevolence",
      "relevance": 0.92
    }
  ],
  "related_concepts": [
    {"target": "benevolence", "relation": "contrasts_with", "strength": 0.85, "evidence": "Butler contrasts self-love with..."},
    {"target": "conscience", "relation": "requires", "strength": 0.6}
  ],
  "importance": 0.88,
  "extraction_confidence": 0.92,
  "agent_id": "agent-03",
  "book_count": 2
}
```

### Field Details
- `concept_id` (required): snake_case, singular (see NORMALIZATION_GUIDE.md)
- `concept_label` (required): Title Case display form
- `category_path` (required): 2-4 levels, Title Case
- `aliases` (required): ≥1 alias, includes surface forms
- `definition` (required): 2-4 sentences, specific to corpus, not generic
- `query_relevance` (required): List of query_ids from queries.txt that this concept helps answer (agents receive the 43 queries)
- `books` (required): ≥1 book where concept appears
- `evidence` (required): ≥1 evidence, 30-300 char verbatim quote
- `related_concepts` (optional): ≥2 relations per concept preferred
- `importance` (required): 0.0-1.0, how central to the corpus
- `extraction_confidence` (required): 0.0-1.0
- `agent_id` (required): e.g., "agent-03"
- `book_count` (required): number of books in shard where concept appears

### Constraints
- At least 15-30 concepts per agent (so total ~225-450 concepts before merging)
- Each concept must have ≥1 evidence and ≥2 related_concepts where possible
- query_relevance must reference actual query_text values, not invented ones

## Merged Output: `merged/category_tree.json`
Hierarchical tree built by merger:
```json
{
  "name": "Root",
  "children": [
    {
      "name": "Moral Psychology",
      "concepts": ["self_love", "benevolence"],
      "children": [
        {"name": "Self-Love", "concepts": ["self_love"], "children": []}
      ]
    }
  ]
}
```

## Merged Output: `merged/concept_graph.jsonl`
One line per node or edge:
```json
{"type": "node", "id": "self_love", "label": "Self-Love", "category": ["Moral Psychology"], "importance": 0.88, "book_count": 12, "evidence_count": 8}
{"type": "edge", "source": "self_love", "target": "benevolence", "relation": "opposes", "strength": 0.85, "evidence": "Butler..."}
```

## Merged Output: `merged/inverted_index.jsonl`
Concept -> paragraphs index:
```json
{"concept_id": "self_love", "book_id": "BUTLER_1726", "page": 42, "paragraph_id": "p_42_3", "text": "full paragraph...", "bbox_pts": [x0,y0,x1,y1]}
```

## Merged Output: `merged/query_concept_map.json`
43 queries mapped to ranked concepts:
```json
{
  "self-love": {
    "query_text": "The user seeks information on which terms authors associate with self-love",
    "concepts": [
      {"concept_id": "self_love", "relevance": 0.98, "evidence_count": 12},
      {"concept_id": "self_interest", "relevance": 0.85}
    ]
  }
}
```
