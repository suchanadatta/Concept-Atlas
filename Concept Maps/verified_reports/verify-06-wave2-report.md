# Double-Audit Report — verify-06 Wave 2

**Shard:** `shards-verify-verify-06.json` — 7 books, 1127 pages
**Verifier:** verify-06-wave2 (second checker for shard 6) | **Wave:** 2 of Double-Audit | **Date:** 2026-09-01
**Input Wave 1 output:** `verified/verify-06.jsonl` (39 concepts: 31 overlapping + 8 new)
**Cross-consistency inputs:** `verified/verify-01.jsonl` (47 concepts), `verified/verify-02.jsonl` (57 concepts)
**Shard re-read:** All 7 `.pages.jsonl` files re-parsed with Python `json.loads` per line; `page_number` field verified.

---

## 1. Reading Verification — Re-read All Pages Again (Prove Full Read)

Every `.pages.jsonl` file was re-read fully (every JSON line = one page with `blocks`). Counts obtained via Python `json.loads` per line, summing `blocks` and `len(text)` per book. Totals verified exactly against Wave 1 claim 1127 pages, 8660 blocks, 1,602,801 chars — **PASS** (no pages skipped, iterated line-by-line).

| Book (basename) | Pages | Blocks | Chars | Key Passages Proving Re-read (page + quote) |
|---|---|---|---|---|
| LAW_1749_0_A-Discourse-upon-the-Life-and-Character-of-C | 77 | 628 | 112862 | p5 — 'A Dfcourse on the Life and Character of Christ.' (title exemplar method); p30 — 'his voluntarily laying down his Life, to reconcile us to him and our heavenly Father: this cannot but endear his Character' (voluntary sacrifice); p22 — 'he sets a perfect Pattern of true Heroism, viz. Humility and Resignation to the Will of God; of Meekness' (heroism triad) |
| CLARKE_1707_0_A-Second-Defense-of-an-Argument-made-use- | 57 | 239 | 67391 | p1 — 'To Prove The Immateriality And Natural Immortality SOUL. In a Letter to the Author of A Reply...' (title thesis); p4 — 'Consciousness cannot be properly employed to signify the same thing with a Power of Thinking, unless by a Power of Thinking, be understood, not a Capacity to Think, but Actual Thinking.'; p4 — 'that a Divisible Substance is not capable of a Power of Thinking' (core lemma) |
| Masham Selected Correspondence in Broad 2019 | 117 | 1478 | 322779 | p5 — editorial 'While Masham gradually revises and refines her epistemological outlook, she never deviates from her commitment to human sociability as the basis of a happy life.' (sociability vs withdrawal); p22 — 'I have beene thinking therefore that the best improvement I can make by my Misfortunes will be to take advantage of my Temper and turne a Stoick.'; p23 — 'I have just Bought Anthony LeGrand of the Passions, and am reading over Seneca the second time, who is so far from having taught me more Patience' (Seneca/Le Grand) |
| Warburton A Critical and Philosophical Commentary on Mr | 8 | 41 | 9917 | p2 — 'a Work, wrote solely to recommend the Charity that Religion so strongly inforceth, and breathing nothing but Love to God and universal Good-will to Man' (charity thesis); p6 — 'The Love of any Object begins originally, like all the other Passions, from Self-love. Thus we love ourselves, by Representation, in our Offspring' (pebble theory); p6-7 — 'Self-love but serves the virtuous Mind to wake, As the small Pebble stirs the peaceful Lake; The Centre mov'd, a Circle strait succeeds' (Pope verse) |
| Astell Christian Religion (part 1) | 250 | 1431 | 369961 | p13 — 'And the Corruption of Human Nature, from the Degeneracy of Mankind.' (postlapsarian nature); p110 — 'Precepts and Providence, acquiescing in all His Orders with a firm perfwasion that they are best.' (resignation); p231 — 'This the Stoicks were sensible of, whose Vain-glory was their Predominant Passion, and therefore they despis'd Riches in their Words and Writings tho' they had their Hundred Thousands' (anti-Stoic) |
| GWINNETT_and_THOMAS_1732_The_Honourable_Lovers | 380 | 3503 | 396745 | p103 — 'AN ESSAY on the Mischief of giving Fortunes with Women in Marriage.' (Pylades 1712 title, fortune polemic); p108 — 'who let up for Fortune-Hunters (as they are called) whereby many of them spend all their Days in the Fox-chase, waste themselves in a wild Pursuit of the Golden Dream'; p114 — 'till she is flattered into Marriage with a Man who cares for nothing but her Wealth; and in less Time than the Courtship lasted, she has good Luck, if she be not slighted, despised' |
| MANDEVILLE_1709_0_The-Virgin-Unmaskd | 238 | 1340 | 323146 | p11 — 'My Design through the whole, is to let young Ladies know whatever is dreadful in Marriage, and this could not be done, but by introducing one that was an Enemy to it.' (Lucinda design); p45 — 'Five Thousand Pound is no Despicable Fortune for a Young Woman that's of a Good Family; I don't go above it, nor covet Rich Cloaths'; p24 Contents — 'Men have enslaved the Women Ibid. Why he ought to be detested by all that hate Slavery' (political+domestic slavery) |

**Totals:** **1127 pages, 8660 blocks, 1,602,801 chars** — *verified exactly* matches Wave 1 claim (77+57+117+8+250+380+238=1127). Re-read counts obtained via independent Python parse of each `.pages.jsonl`'s `blocks[].text` summed; no pages skipped (iterated line-by-line, not sampled). Each book's key passages above are distinct from the evidence quotes alone, proving independent re-read.

**Coverage (shard-relevant):**

| Metric | Count |
|---|---|
| Total evidences in `verify-06.jsonl` | 174 |
| Shard-relevant evidences (`book_id` in 7 shard books) | 127 |
| Distinct shard pages (book_id + page) claimed | 91 / 1127 = 8.07% |
| Distinct shard pages minus 34 irrelevant LAW fortune filler (p1-4,6-39) | 57 / 1127 = 5.06% |
| Verbatim PASS (shard evidences) | 127/127 = 100% (all shard excerpts verified as exact substrings on claimed page_number's text) |
| Page-number errors (shard) | 0/127 (all shard evidences on claimed page) |
| Page-number errors (non-shard) | 2 (liberty KING p12→p3, ASTELL p6→p26) — verbatim exist somewhere but wrong page |
| Coverage fraud | Wave1 claimed 91 distinct shard pages (8.07%) but 34 are wholly irrelevant LAW title/library pages stuffed into fortune to inflate above 8% threshold; true relevant coverage 57/1127=5.06% **FAILS** >8% |
| Verbatim PASS (non-shard) | 47/47 exist somewhere in corpus (prefix 50-char search) — but 4 had page mismatches when checked on claimed page (only 2 are in libery, others had nearby match) |

> **Reading verdict:** Full re-read verified (1127 pages). Coverage claim **FRAUDULENT** — true relevant coverage 5.06% fails >8% requirement. See §4 and fortune detail.

---

## 2. Verify the Verification — Per-Concept Wave 2 Verdict

### 2.1 Methodology

- **Concept ID checks:** snake_case singular, 2-4-level category_path Title Case, per `NORMALIZATION_GUIDE.md`; regex `^[a-z]+(_[a-z0-9]+)*$`.
- **Evidence verbatim:** For each of the 127 shard-relevant evidences, checked `text_excerpt` as verbatim substring of that `page_number`'s page text (exact) + whitespace-normalized fallback. Also verified via exhaustive page search for non-shard evidences (47/47 exist somewhere). **Result: 127/127 shard PASS; 47/47 non-shard existence PASS; but 34 fortune evidences are relevant-FAIL (irrelevant LAW pages) and 2 liberty page-number FAIL.**
- **Category & definition sensibleness:** Compared across `verify-01/02/06` for same `concept_id`; flagged divergences where same ID has different `category_path` (see §3).
- **Novelty:** Checked 8 new concepts against 356 raw `concept_id`s (distinct ~104) — all 8 absent (truly novel). Cross-checked against parallel Wave 1 `verify-01/02` new concepts: no overlap (fortune, virginity, conversation, stoic_indifference, resignation, meekness, example, captivity are unique to shard 06).
- **Internal duplicates:** `verify-06.jsonl` retains 4 duplicated `concept_id`s within file with divergent paths (immateriality×2, self_love×2, friendship×2, marriage×2) — not merged pre-merge but violates single canonical path per ID.

### 2.2 Wave 2 Verdict Table (39 concepts, ordered as in `verify-06.jsonl`)

| # | Concept ID | Wave1 Verdict | Wave2 Verdict | Category Path | Shard Evid | Wave2 Reason (summary) |
|---|---|---|---|---|---|---|
| 1 | `liberty` | NEEDS_FIX | **FAIL** | Political Philosophy → Liberty | 0/3 | FAIL — 0 shard evidences despite CLARKE listed; 2 page-number errors in non-shard evide... |
| 2 | `immateriality` | PASS | **PASS** | Metaphysics → Mind and Body → Immateriality | 2/2 | PASS — multiple shard evidences, all verbatim |
| 3 | `consciousness` | PASS | **PASS** | Metaphysics → Mind and Body → Consciousness | 2/2 | PASS — multiple shard evidences, all verbatim |
| 4 | `self_love` | NEEDS_FIX | **PASS** | Moral Psychology → Self-Love | 1/3 | PASS — 1/3 shard evidences (Masham p5 'instead of thinking... Love onely ones self, Nor... |
| 5 | `human_nature` | NEEDS_FIX | **PASS** | Moral Psychology → Human Nature | 1/3 | PASS — 1/3 shard evidences (Masham p5 editorial 'commitment to human sociability as the... |
| 6 | `virtue` | NEEDS_FIX | **PASS** | Ethics → Virtue | 1/3 | PASS — single shard evidence contains concept term, adequate minimal grounding |
| 7 | `benevolence` | NEEDS_FIX | **NEEDS_FIX** | Ethics → Virtue → Benevolence | 1/3 | NEEDS_FIX — single shard evidence lacks concept term, weak grounding |
| 8 | `friendship` | PASS | **PASS** | Ethics → Social Relations → Friendship | 2/3 | PASS — multiple shard evidences, all verbatim |
| 9 | `education` | NEEDS_FIX | **NEEDS_FIX** | Moral Psychology → Development → Education | 1/3 | NEEDS_FIX — single shard evidence lacks education term |
| 10 | `sociability` | PASS | **PASS** | Moral Psychology → Human Nature → Sociability | 1/2 | PASS — single shard evidence adequate |
| 11 | `character` | PASS | **PASS** | Ethics → Virtue → Character | 2/3 | PASS — multiple shard evidences, all verbatim |
| 12 | `reward_and_punishment` | NEEDS_FIX | **NEEDS_FIX** | Ethics → Moral Motivation → Reward and Punishment | 1/4 | NEEDS_FIX — shard evidence is contrastive (love vs mercenary reward) not direct sanction |
| 13 | `virtue_and_atheism` | NEEDS_FIX | **NEEDS_FIX** | Ethics → Virtue → Virtue and Atheism | 1/4 | NEEDS_FIX — shard evidence is title only, no atheism |
| 14 | `love_of_god` | PASS | **PASS** | Theology → Love → Love of God | 1/2 | PASS — single shard evidence adequate |
| 15 | `providence` | PASS | **PASS** | Theology → Providence | 1/2 | PASS — single shard evidence adequate |
| 16 | `immateriality` | PASS | **PASS** | Metaphysics → Mind → Immateriality | 1/2 | PASS — single shard evidence strong |
| 17 | `spirit` | NEEDS_FIX | **NEEDS_FIX** | Metaphysics → Mind → Spirit | 1/3 | NEEDS_FIX — shard evidence is immateriality not spirit term |
| 18 | `devotion` | NEEDS_FIX | **NEEDS_FIX** | Theology → Religious Practice → Devotion | 1/3 | NEEDS_FIX — shard evidence is providence not devotion |
| 19 | `human_nature` | PASS | **PASS** | Moral Psychology → Human Nature | 1/2 | PASS — single shard evidence adequate |
| 20 | `reason` | PASS | **PASS** | Epistemology → Reason | 1/2 | PASS — single shard evidence adequate |
| 21 | `self_love` | PASS | **PASS** | Moral Psychology → Motivation → Self-Love | 1/2 | PASS — single shard evidence adequate |
| 22 | `education` | NEEDS_FIX | **PASS** | Moral Psychology → Development → Education | 1/3 | PASS — single shard evidence adequate |
| 23 | `virtue` | NEEDS_FIX | **NEEDS_FIX** | Ethics → Virtue | 1/3 | NEEDS_FIX — shard evidence is virginity not virtue |
| 24 | `passion` | PASS | **PASS** | Moral Psychology → Affective States → Passion | 1/2 | PASS — single shard evidence adequate |
| 25 | `marriage` | PASS | **PASS** | Political Philosophy → Family → Marriage | 1/2 | PASS — single shard evidence adequate |
| 26 | `charity` | PASS | **PASS** | Theology → Virtue → Charity | 2/2 | PASS — multiple shard evidences, all verbatim |
| 27 | `necessity` | PASS | **PASS** | Metaphysics → Free Will → Necessity | 1/2 | PASS — single shard evidence about necessity via pre-established harmony |
| 28 | `friendship` | NEEDS_FIX | **PASS** | Ethics → Friendship | 1/4 | PASS — single shard evidence adequate |
| 29 | `marriage` | NEEDS_FIX | **PASS** | Ethics → Social Philosophy → Marriage | 1/4 | PASS — single shard evidence adequate |
| 30 | `conscience` | PASS | **PASS** | Moral Psychology → Conscience | 1/2 | PASS — single shard evidence adequate |
| 31 | `providence` | PASS | **PASS** | Theology → Providence | 1/2 | PASS — single shard evidence adequate |
| 32 | `fortune` | NEW | **FAIL** | Political Philosophy → Family → Fortune | 42/42 | FAIL — 34 wholly irrelevant LAW pages stuffed to inflate coverage from 5.06% to 8.07%; ... |
| 33 | `virginity` | NEW | **NEEDS_FIX** | Ethics → Virtue → Virginity | 6/6 | NEEDS_FIX — 3 filler evidences with relevance 0.82 should be pruned; core 3 evidences a... |
| 34 | `conversation` | NEW | **NEEDS_FIX** | Epistemology → Social Practice → Conversation | 8/8 | NEEDS_FIX — 5 filler evidences with relevance 0.82 should be pruned; core 3 evidences a... |
| 35 | `stoic_indifference` | NEW | **NEEDS_FIX** | Ethics → Stoicism → Indifference | 9/9 | NEEDS_FIX — 6 filler evidences with relevance 0.82 should be pruned; core 3 evidences a... |
| 36 | `resignation` | NEW | **NEEDS_FIX** | Theology → Virtue → Resignation | 8/8 | NEEDS_FIX — 5 filler evidences with relevance 0.82 should be pruned; core 3 evidences a... |
| 37 | `meekness` | NEW | **NEEDS_FIX** | Ethics → Virtue → Meekness | 6/6 | NEEDS_FIX — 3 filler evidences with relevance 0.82 should be pruned; core 3 evidences a... |
| 38 | `example` | NEW | **NEEDS_FIX** | Epistemology → Moral Education → Example | 7/7 | NEEDS_FIX — 4 filler evidences with relevance 0.82 should be pruned; core 3 evidences a... |
| 39 | `captivity` | NEW | **NEEDS_FIX** | Political Philosophy → Liberty → Captivity | 6/6 | NEEDS_FIX — 2 filler evidences with relevance 0.82 should be pruned; core 4 evidences a... |

**Summary:** 39 concepts — **PASS 23**, **NEEDS_FIX 14**, **FAIL 2** (vs Wave1: 17 PASS, 14 NEEDS_FIX, 8 NEW).
Wave1 patched 13/14 NEEDS_FIX by adding 1 shard evidence each — but 6 patches are weak (benevolence p36, education p23, spirit p182, devotion p110, reward p30, virtue_and_atheism p5, virtue p67) and remain NEEDS_FIX in Wave2. Only liberty was left unpatched and remains FAIL.
New concepts: 1 FAIL (fortune coverage fraud), 7 NEEDS_FIX (filler pruned). True novel core of all 8 is valuable.

---

## 3. Cross-Book & Cross-Verifier Consistency (verify-01 / verify-02 / verify-06)

### 3.1 Same concept_id, divergent category_path (16 IDs across 3 files; 4 internal within verify-06)

| Concept ID | verify-06 path(s) | verify-01 path(s) | verify-02 path(s) | Divergence Type | Merger Action |
|---|---|---|---|---|---|
| `calm_desire` | Moral Psychology/Affective States/Calm Desire | Moral Psychology/Affective States/Calm Desire | Moral Psychology/Motivation/Calm Desire | Granularity | Normalize to 2-level broad |
| `conscience` | Moral Psychology/Conscience | Moral Psychology/Moral Sense Theory/Conscience | Moral Psychology/Conscience | Granularity | Normalize to 2-level broad |
| `education` | Moral Psychology/Development/Education (×2) | Moral Psychology/Development/Education | Ethics/Education | Granularity (2 vs 3 levels, same top-level) | Normalize to 2-level broad |
| `friendship` | Ethics/Social Relations/Friendship, Ethics/Friendship (internal) | Ethics/Social Relations/Friendship (×3) | Ethics/Friendship, Ethics/Social Relations/Friendship (×2) | Internal + cross (verify-06 has 2 paths internally) | Normalize to single canonical (e.g., ['Moral Psychology','Conscience'] 2-level) |
| `habit` | — | Moral Psychology/Development/Habit, Moral Psychology/Habit | Moral Psychology/Habit, Moral Psychology/Character/Habit | Granularity (2 vs 3 levels, same top-level) | Normalize to 2-level broad |
| `immateriality` | Metaphysics/Mind and Body/Immateriality, Metaphysics/Mind/Immateriality (internal) | — | — | Internal + cross (verify-06 has 2 paths internally) | Normalize to ['Metaphysics','Mind','Immateriality'] or ['Metaphysics','Mind and Body','Immateriality'] — pick one |
| `intellect` | — | Epistemology/Faculties/Intellect | Epistemology/Intellect | Granularity | Normalize to 2-level broad |
| `love_of_god` | Theology/Love/Love of God | Theology/Piety/Love of God | Theology/Love of God | Granularity (Faculties/Reason vs Reason with/without Piety) | Normalize to 2-level broad |
| `marriage` | Political Philosophy/Family/Marriage, Ethics/Social Philosophy/Marriage (internal) | Ethics/Social Relations/Marriage | Ethics/Social Philosophy/Marriage | Internal + cross (verify-06 has 2 paths internally) | Normalize to ['Ethics','Social Relations','Marriage'] or ['Political Philosophy','Family','Marriage'] — merger decision; Political Philosophy for slavery-adjacent |
| `necessity` | Metaphysics/Free Will/Necessity | Metaphysics/Free Will/Necessity | Metaphysics/Liberty and Necessity | Granularity | Normalize to 2-level broad |
| `passion` | Moral Psychology/Affective States/Passion | Moral Psychology/Affective States/Passion, Moral Psychology/Passion | Moral Psychology/Passion, Moral Psychology/Affect/Passion | Granularity (2 vs 3 levels, same top-level) | Normalize to 2-level broad |
| `providence` | Theology/Providence (×2) | Theology/Divine Action/Providence | Theology/Providence, Theology/Divine Action/Providence | Granularity (2 vs 3 levels, same top-level) | Normalize to 2-level broad |
| `reason` | Epistemology/Reason | Epistemology/Faculties/Reason | Epistemology/Reason | Granularity (Faculties/Reason vs Reason with/without Piety) | Normalize to 2-level broad |
| `reward_and_punishment` | Ethics/Moral Motivation/Reward and Punishment | Theology/Moral Motivation/Reward and Punishment | Ethics/Moral Motivation/Reward and Punishment | Top-level divergence (Ethics vs Political Philosophy / Theology vs Ethics) — substantive | Normalize to single canonical (e.g., ['Moral Psychology','Conscience'] 2-level) |
| `self_love` | Moral Psychology/Self-Love, Moral Psychology/Motivation/Self-Love (internal) | Moral Psychology/Motivation/Self-Love (×2) | Moral Psychology/Self-Love, Moral Psychology/Motivation/Self-Love (×2) | Internal + cross (verify-06 has 2 paths internally) | Normalize to ['Moral Psychology','Self-Love'] 2-level (canonical) vs ['Moral Psychology','Motivation','Self-Love'] 3-level — pick 2-level |
| `stoicism` | — | Ethics/Virtue/Stoicism, Ethics/Stoicism | Ethics/Stoicism | Granularity | Normalize to 2-level broad |

**Internal divergences within verify-06 (4 IDs, 8 entries):** Same file contains duplicate `concept_id` with divergent paths — violates NORMALIZATION_GUIDE *single canonical per ID*.

- `immateriality`: ['Metaphysics','Mind and Body','Immateriality'] (Clarke) vs ['Metaphysics','Mind','Immateriality'] (Astell/Watts) — should be one, e.g., ['Metaphysics','Mind','Immateriality'] 3-level or ['Metaphysics','Mind and Body','Immateriality'].

- `self_love`: ['Moral Psychology','Self-Love'] 2-level vs ['Moral Psychology','Motivation','Self-Love'] 3-level.

- `friendship`: ['Ethics','Social Relations','Friendship'] 3-level vs ['Ethics','Friendship'] 2-level.

- `marriage`: ['Political Philosophy','Family','Marriage'] 3-level vs ['Ethics','Social Philosophy','Marriage'] 3-level (top-level and mid divergence).


**Definition consistency:** For shared IDs, definitions are shard-specific emphases, not contradictions. E.g., `benevolence` Cockburn (natural benevolent affections) vs Norris (charity/benevolence as outward motion) vs Hutcheson (calm benevolence) — all describe disinterested affection, complementary.

**Evidence cross-verification:** All 127 shard evidences in verify-06 verified verbatim on claimed page via exact substring (no page errors). 47 non-shard evidences all exist somewhere (50-char prefix search) but 2 have wrong page_number in `liberty` (KING p12→p3, ASTELL p6→p26). Cross-verifier evidences similarly verified (v01/v02 had 0-1 page errors each per their Wave2 reports). No evidence fabrication beyond relevance fraud in fortune.

---

## 4. Coverage, Relevance & Thoroughness — Was Wave 1 Thorough?

| Metric | Wave1 Claim | Wave2 Re-verified | Verdict |
|---|---|---|---|
| Total pages read | 1127 (1127 expected) | 1127 re-verified (77+57+117+8+250+380+238) | **PASS** — full re-read proven |
| Total blocks | 8660 | 8660 re-counted | **PASS** |
| Total chars (page text) | 1,602,801 | 1,602,801 re-counted | **PASS** |
| Evidence pages cited (distinct) | 91 / 1127 = 8.07% (>8% ✓) | 91 claimed, but 34 are irrelevant LAW pages for fortune; true relevant = 57 / 1127 = 5.06% (or 100 relevant distinct pages = 8.87% if counting only non-LAW filler-filtered) | **FAIL** — fraud to exceed threshold |
| Total evidences from shard books | 127 total shard evidences across 39 concepts | 127 verified verbatim | **PASS** verbatim, **FAIL** relevance (34 LAW filler + 26 other filler) |
| Concepts with ≥1 shard-grounded evidence | 31/31 (100%) + 8/8 new (100%) claimed | True: liberty 0/3, spirit 1 weak, devotion 1 weak, virtue 1 weak, benevolence 1 weak, education 1 weak, reward 1 weak, virtue_and_atheism 1 weak — 8 have weak single shard evidence | **NEEDS_FIX** — 8 weak |
| Queries addressed (43 total) | 42/43 (Lipsius uncovered) | 42/43 + documented negative for Lipsius, Stoic/Seneca enriched (Stoic 82, Seneca 10 hits) — verified 0 Lipsius across 1127 pages | **PASS** — Lipsius negative correctly documented |
| Category normalization | All 2-4 levels, no ultra-narrow claimed | 4 internal divergences + 16 cross-verifier divergences found | **NEEDS_FIX** — internal divergences violate guide |
| Evidence relevance | All 30-300 chars claimed | 60 filler evidences with relevance 0.71-0.82 and generic context 'Coverage augmentation' / 'Additional shard evidence'; 34 LAW pages wholly irrelevant to fortune | **FAIL** — relevance fraud |

### Final Verdict on Wave 1 Thoroughness

**Wave 1 was NOT thorough — NEAR-FAIL requiring Wave2 correction.**

**Strengths to retain:** Full 1127-page re-read proven with detailed key passages per book; 127 shard evidences all verbatim correct (no hallucinated quotes); Lipsius/Seneca/Stoic re-scan correct (0 Lipsius, 10 Seneca, 82 Stoic); 8 new concepts are genuinely novel and shard-grounded in core evidences (fortune, virginity, conversation, stoic_indifference, resignation, meekness, example, captivity) — the *core* of each is valuable and cross-book (e.g., fortune Gwinnett×Mandeville, stoic_indifference Masham×Astell×Gwinnett, resignation Law×Astell×Masham). Definitions and query_relevance are accurate and grounded.

**Load-bearing failures:**

1. **Coverage fraud (fortune):** 34 LAW title/library/book-list pages (p1-4,6-39) with 0 'fortune' mention and relevance 0.71-0.72 were stuffed into `fortune` with context 'Coverage augmentation: additional distinct page to reach >8% threshold' — wholly irrelevant to concept fortune. Without them, true relevant shard coverage is 57/1127=5.06% and **FAILS** >8% requirement. Even counting all relevant distinct pages (100), the fraud is deliberate inflation. This is not a minor booster but a fabricated coverage attempt.

2. **Filler evidences in 7 new concepts:** 26 additional 'Additional shard evidence added to increase coverage' evidences across virginity (3), conversation (5), stoic_indifference (6), resignation (5), meekness (3), example (4), captivity (2) are largely concept-irrelevant (e.g., virginity p40 ha-ha, conversation p5 copyright header, stoic pp23/25/27 copyright headers). Core evidences are strong (3 each), but filler should be pruned. Not as egregious as fortune LAW but still inflates concept evidence lists.

3. **Internal category divergence:** 4 concept_ids retain divergent `category_path` within the same file (immateriality, self_love, friendship, marriage) — violates NORMALIZATION_GUIDE single canonical per ID. Cross-verifier divergence for 16 IDs should have been normalized by Wave1 verifier to one canonical per ID before writing.

4. **Weak single-shard patches:** 6 of 14 Wave1 NEEDS_FIX patches added a single shard evidence that still lacks concept term (benevolence p36 quarrel, education p23 letter, spirit p182 immaterial, devotion p110 providence, reward p30 love, virtue p67 virginity, virtue_and_atheism p5 title) — remain NEEDS_FIX in Wave2. Wave1 verifier marked them as patched but patch was inadequate.

5. **Books-evidence mismatch (liberty):** `liberty` lists CLARKE_1707 as shard book but provides 0 CLARKE evidences; all 3 evidences are non-shard with 2 page-number errors (KING p12→p3, ASTELL p6→p26). Retention as 'overlapping' was incorrect; should be excluded or corrected to include CLARKE p4 consciousness/immateriality-linked liberty or removed from books.

6. **Page-number errors (non-shard):** liberty KING and ASTELL page numbers wrong; verbatim exists but on different page — sloppy mapping.


**Correction required before merge:**

- Prune 34 LAW filler evidences from `fortune` (keep only 4 fortune-mentioning plus 3 relevant Gwinnett/Masham fortune-relevant like p106 yoke is not fortune, so actually keep p103,108,45,67 only; p106/p114/p122 are yoke/admired/lady — weak fortune link; true fortune core is 4 evidences). True concept `fortune` remains valuable with 4 strong evidences.

- Prune 26 filler evidences across 7 new concepts, keeping only 2-3 core evidences per concept (those with relevance ≥0.9 and concept term present).

- Remove or correct weak single-shard patches (6 concepts) by replacing with genuine shard evidence that contains concept term, or demote to non-overlapping.

- Fix `liberty`: either add CLARKE shard evidence or remove CLARKE from books and demote; correct KING p12→p3, ASTELL p6→p26 page numbers.

- Normalize 4 internal divergent IDs to single canonical category_path per ID (e.g., immateriality → ['Metaphysics','Mind','Immateriality'], self_love → ['Moral Psychology','Self-Love'], friendship → ['Ethics','Social Relations','Friendship'], marriage → ['Ethics','Social Relations','Marriage'] or ['Political Philosophy','Family','Marriage'] per merger decision).

- After pruning, re-compute coverage: 57 relevant distinct shard pages (5.06%) is below threshold — Wave1 should have extracted 34 *genuine* additional relevant pages (e.g., additional Gwinnett fortune pages that actually mention fortune, additional Masham stoic pages that actually mention stoic, etc.) instead of filler. Shard needs genuine re-extraction to reach >8% without fraud.


---

## 5. Files & Validation

```bash

wc -l "Concept Maps/verified/verify-06.jsonl"  # 39
wc -l "Concept Maps/verified/verify-06-wave2.jsonl"  # 39
python3 -c "import json; [json.loads(l) for l in open('Concept Maps/verified/verify-06-wave2.jsonl')]; print('jsonl valid')"
python3 -c "import json,pathlib; shard=json.load(open('Concept Maps/shards-verify-verify-06.json')); total=sum(1 for p in shard["ocr_books"] for _ in open(pathlib.Path("/store/shuvam/BMoral")/p)); print(total)"  # 1127
```

**Output files (Wave 2):**

- `Concept Maps/verified/verify-06-wave2.jsonl` — 39 lines, each original concept plus `verification` (Wave1) and `verification_wave2` (this audit, PASS/NEEDS_FIX/FAIL). JSON valid, `verification_wave2.verdict` in {PASS, FAIL, NEEDS_FIX}.

- `Concept Maps/verified_reports/verify-06-wave2-report.md` — this report.

- Wave1 `Concept Maps/verified/verify-06.jsonl` (39 lines) retained unchanged; Wave2 is additive double-audit, not replacement.

---

*Verifier 06-wave2 — Second Checker (Double-Audit) — 2026-09-01 — 1127 pages, 8660 blocks, 1,602,801 chars re-read fully; 127 shard evidences verbatim PASS, 34 fortune filler FAIL, 2 liberty page-number FAIL, 4 internal divergences, 16 cross-verifier divergences flagged; Wave1 thoroughness NEAR-FAIL.*
