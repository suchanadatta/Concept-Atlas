# Normalization Guide — Concept IDs, Labels, Categories

All 15 agents MUST follow these rules exactly to ensure cross-agent consistency. The merger will reject non-conforming entries.

## Concept IDs
- **Format:** `snake_case`, lowercase, singular, no hyphens
- **Examples:** `self_love`, `moral_sense`, `liberty`, `divine_law`, `friendship`
- **NOT:** `Self-Love`, `self_loves`, `selfLove`, `self-love`
- **Singularize:** `passions` → `passion`, `virtues` → `virtue` (except proper plurals like `moral_sense` which is singular concept)
- **De-hyphenate:** `self-love` → `self_love`

## Concept Labels
- **Format:** Title Case, singular, human-readable
- **Examples:** `Self-Love`, `Moral Sense`, `Liberty`, `Divine Law`
- Label is display form of ID: `self_love` → `Self-Love` (but ID stays snake_case)

## Aliases
- List all surface forms found in texts: `["self-love", "self love", "amour-propre", "selfishness"]`
- Include OCR variants if relevant: `["self-love", "felf-love"]` (long-s misread)

## Category Paths
- **Format:** Array of Title Case category names, most general first, specific last
- **Examples:**
  - `["Ethics", "Moral Psychology", "Self-Love"]`
  - `["Ethics", "Virtue", "Benevolence"]`
  - `["Political Philosophy", "Liberty"]`
  - `["Moral Philosophy", "Moral Sense Theory"]`
- **Rules:**
  - Use 2-4 levels max
  - Top-level categories should be broad: `Ethics`, `Moral Psychology`, `Metaphysics`, `Political Philosophy`, `Theology`, `Epistemology`, `Aesthetics`
  - Second level more specific: `Virtue`, `Moral Motivation`, `Human Nature`, `Liberty`
  - Leaf is the concept itself's domain
  - **DO NOT invent ultra-narrow top categories:** Not `Self-Love Studies` — use `Moral Psychology`
  - **Consistency heuristic:** If unsure between two category names, prefer the one already used for a related concept (e.g., if you already have `Moral Motivation` for conscience, use same for reward/punishment, not `Motivation Theory`)

## Avoiding Near-Duplicates
| Bad (divergent) | Good (converged) |
|---|---|
| `love` vs `human_love` vs `love_human` | `love` with alias `human love` + category `["Ethics", "Love"]` |
| `societal_values` vs `society_values` vs `social_values` | `social_value` |
| `passion` vs `passions` vs `the_passions` | `passion` |
| `moral_sense` vs `moral_senses` | `moral_sense` |

- When in doubt, use the **shortest, most canonical** form
- Add longer forms as aliases, not separate concepts
- The merger will deduplicate by ID, so divergent IDs create duplicate nodes — avoid this

## Relations
- **Relation types (controlled vocabulary):**
  - `entails`, `opposes`, `supports`, `underlies`, `develops_from`, `influences`, `exemplifies`, `contrasts_with`, `subsumes`, `requires`
- **Example:** `self_love` --`opposes`--> `benevolence`
- **Strength:** 0.0-1.0, how strongly the texts support this relation

## Evidence
- Every concept MUST have ≥1 evidence entry with real quoted text (30-300 chars) from a book
- Format: `{"book_id": "BUTLER_...", "page": 42, "text_excerpt": "exact quote...", "context": "Butler argues that..."}`
- Page numbers: use printed page if available, else sequential
- Keep excerpts verbatim (including 18th-c spelling)
