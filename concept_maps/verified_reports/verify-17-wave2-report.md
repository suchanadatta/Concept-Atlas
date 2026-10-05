# Double-Audit Report — verify-17 Wave 2

**Shard:** `shards-verify-verify-17.json` — 6 books, 1552 pages (re-read every page)  
**Verifier:** verify-17-wave2 (second checker for shard 17) | **Wave:** 2 of Double-Audit | **Date:** 2026-09-01  
**Input Wave 1 outputs:** `verified/verify-17.jsonl` (54 concepts, 119 evidences), `verified/verify-01.jsonl` (47), `verified/verify-02.jsonl` (57)  
**Shard re-read:** All 6 `.pages.jsonl` files re-parsed with Python `json.loads` per line; `page_number` (sequential pdf_index) and `blocks[].text` used; printed pagination vs sequential offset noted for Hutcheson front-matter.

---

## 1. Reading Verification — Re-read All Pages Again

Every `.pages.jsonl` file was read fully (every JSON line = one page with `blocks`). Counts via Python `json.loads` per line; total chars summed from `blocks[].text` (whitespace preserved) and checked against `text` field. All 6 books enumerated from `shards-verify-verify-17.json`.

| Book (basename) | Pages | Blocks | Chars (blocks) | Chars (text) | Key Passages Proving Re-read (page + verbatim quote) |
|---|---|---|---|---|---|
| FORDYCE_1754_0_The-Elements-of-Moral-Philosophy | 313 | 1539 | 339044 | 338788 | p.2 — "THE ELEMENTS OF Moral Philosophy. IN THREE BOOKS. 1. Of Man, and his Connexions. Of Duty or Moral Obligation.—Various Hypotheses----Final Causes of our Happiness" ; p.5 — "A great Philolopher * has laid it out into three general Provinces, HISTORY, POETRY, and PHILOSOPHY; which he refers to three several Powers of the Mind, MEMORY, IMAGINATION, and REASON." ; p.17 — "culiar to one Period, but belonging to every Age, and acting more or less in every Breast throughout Life. Such are, Self-Love, Benevolence, Love of Life, Honour, Shame, Hope, Fear, Desire, Aversion, Joy, Sorrow, Anger, and the like." ; p.151 — "WHEN Man arrives to a certain Age, he becomes sensible of a peculiar Sympathy and Tenderness towards the other Sex; the Charms of Beauty engage his Attention" |
| LAW_1745_0_Considerations-on-the-State-of-the-World-with-regard-to-the-Theory-of-Religion | 261 | 2088 | 367893 | 364573 | p.2 — "CONSIDERATIONS ON THE STATE of the WORLD With regard to the THEORY of RELIGION, IN THREE PARTS. I. Want of Universality in Natural and Reveled Religion," ; p.29 — "soon filling the World with rank Enthusiasm or the most wicked and absurd Impostures ; and when it is once thus perverted, there seems to be no room for any remedy upon this Scheme;" ; p.115 — "Victi victoribus leges dederunt, fays Seneca of this People. Aug. de Civ. D.L. 6. c.11." ; p.69 — "Worship. They could have no very perfect Notions of his Nature and Providence; nor had they much leisure for Speculation and Refinement" |
| HUTCHESON_1725_1726_An-Inquiry-into-the-Original-of-our-Ideas-of-Beauty-and-Virtue | 329 | 2343 | 403505 | 398617 | p.2 — "AN INQUIRY INTO THE ORIGINAL of our IDEAS OF BEAUTY and VIRTUE; In Two TREATISES. I. Concerning BEAUTY, ORDER HARMONY, DESIGN." ; p.20 — "will ever look upon his Friendship" + p.21 "as one of the greatest Advantages and Pleasures of his Life." (span across page break, footnote marker 3); p.47 — "and yet as far as we can by Sense discover, or by Reasoning enlarge our Knowledge, and extend our Imagination, we generally find their Structure, Order, and Motion, agreeable to our Sense of Beauty." ; p.212 — "And this may shew us the only Foundation for the boasting of the Stoicks, \"That a Creature suppos'd Innocent, by pursuing Virtue with his utmost Power, may in Virtue equal the Gods.\"" |
| NORRIS_1689_0_Reason-and-Religion | 141 | 1164 | 247368 | 242203 | p.3 — "so fit as your Grace to Patronize a performance that so well agrees both to the Character of your Person, and to the Station whereby you stand related to us." ; p.11 — "Not that there is any darkness or obscurity in God. No, God is the most knowable Object" ; p.50 — "These simple Effences of things therefore can be nothing else but the Divine Effence it felt consider'd with his Connotation, as variously representative or exhibitive of things" ; p.110 — "he concludes that God is the Intelligible World, or the Place of Spirits, as the Material World is the place of Bodies." |
| Cockburn Works vol. 2 (part 3) | 86 | 1986 | 115071 | 115234 | p.1 — "There is, my lord, if I have any sense Of honour, gratitude, or friendship. Castalio Is this day brought here, a prisoner to the castle, Where he is kept in chains" ; p.1 — "The Fatal Friendship: 489 Count. Finding me more enflam'd, and still persifting, She said, I might expose her to your anger" ; p.3 — "only to keep the marriage secret. Whilst her sister lives, to whom she forfeits," ; p.4 — "and that marriage-bonds Were of toopond'rous weight for youth to bear." |
| WATTS_1733_Philosophical-essays | 422 | 2681 | 562608 | 556075 | p.2 — "PHILOSOPHICAL E S S A Y S ON Various SUBJECTS, V I Z. Space, Substance, Body, Spirit, the Operations of the Soul in Union with the Body, innate Ideas, perpetual Consciousness" ; p.18 — "whether it be a Substance or Mode, God or a Creature, Something or Nothing. The common Idea which all Mankind have of it, seems to be much the same, viz. Extension void of Matter or Body, and capable of receiving or containing Matter or Body." ; p.262 — "Let a thousand Reasons therefore be laid before me, to prove that I am nothing but an Engine, my own inward present Consciousness of this Proposition, that I have Thoughts, that I have reasoning Powers, and that I have a Will and free Choice, is a full Evidence" |

**Totals:** **1552 pages, 11801 blocks, 2035489 chars (blocks) / 2015490 chars (text)** — *verified exactly* matches verify-17 Wave 1 claim (313+261+329+141+86+422=1552). Re-read counts obtained via independent Python parse of each `.pages.jsonl`'s `blocks` and `text`; excludes geometry. No pages skipped (iterated line-by-line, not sampled). Printed pagination offset noted for Hutcheson front-matter (roman vs arabic): sequential `page_number` 14 ≈ printed p8, hence Wave1's verbatim search used corpus-wide substring fallback; Wave2 re-verified with same fallback and also checked `text` field exact page.

**Coverage (shard):**
- Total unique evidence pages cited across `verify-17.jsonl` = **96** (distinct `book_id` + `page` pairs across all 119 evidences).
- Shard-relevant unique pages (book_id matches one of 6 shard books) = **52** => **52/1552 = 3.35%** genuine conceptual coverage (no synthetic padding).
- Synthetic coverage-boost pages (`relevance == 0.6` or `paragraph_id` contains `coverage`) = **0** — Wave1 correctly reported 3.4% and did **not** inflate with irrelevant distinct-page padding (unlike verify-01/02, see §5). The 52 pages are all conceptually grounded (see §4).
- Genuine coverage is below 8% threshold, but Wave1 transparently reported the gap as honest scarcity (Lipsius 0 hits, plus high-frequency topics now extracted) rather than gaming the metric. Second audit confirms 3.35% is the *honest* coverage after adding 8 new concepts (+8 distinct pages). No padding fraud.

---

## 2. Verify the Verification — Per-Concept Wave 2 Verdict

### 2.1 Methodology

- **Concept ID checks:** snake_case singular, 2-4-level category_path Title Case, per NORMALIZATION_GUIDE.md.
- **Evidence verbatim:** For each of the **71 shard-relevant evidences** (`book_id` in 6 books), checked `text_excerpt` as verbatim substring of that page's `text` field (whitespace-normalized exact search) *and* as substring anywhere in the book's corpus to distinguish page-offset vs true failure. For Hutcheson, printed vs sequential pagination offset (front-matter roman numerals) was accounted for. **2 true failures** (see §2.3), 69 PASS (97.2%). For non-shard evidences (48 entries from KING, JOHNSON, MANDEVILLE 1714, Masham, etc.), spot-checked 20 external excerpts against their own `.pages.jsonl` where available — all verbatim (truncation at 2000 chars display limit explains apparent prefix-only matches; full stored strings are verbatim).
- **Category & definition sensibleness:** Compared across `verify-17/01/02` (see §3). Flagged divergences where same `concept_id` has different `category_path` across verifiers.
- **Novelty:** Checked 8 new concepts against 356 raw `concept_id`s (distinct 104) — 5 truly novel to corpus (`space`, `substance`, `imagination`, `future_state`, `stoic_virtue`), 3 shard-novel only (`enthusiasm`, `self_government`, `marriage` already in raw, see §4).
- **Internal duplicates:** `verify-17.jsonl` retains 11 duplicated `concept_id`s from distinct raw agents (moral_sense 2, self_love 2, benevolence 2, beauty 2, virtue 2, friendship 3, providence 3, liberty 3, passion 2, necessity 2, reason 2) — not merged. Flagged for merger dedup.
- **Evidence relevance vs padding:** See §4-5. No synthetic relevance 0.6 padding in verify-17; 0 irrelevant boost pages.

### 2.2 Wave 2 Verdict Table (54 concepts — 46 verified + 8 new)

| # | Concept ID | Wave1 Verdict | Wave2 Verdict | Category Path | Reason |
|---|---|---|---|---|---|
| 1 | `chain_of_being` | PASS | **PASS** | Metaphysics → Hierarchy → Chain of Being | Snake_case singular, 3-level broad→specific PASS. No shard evidence (both KING) — correctly noted as non-shard; definition grounded in King p132-133 chain hierarchy. Category consistent (no cross-verifier duplicate). |
| 2 | `moral_fitness` | PASS | **PASS** | Ethics → Moral Principles → Moral Fitness | PASS: id/category 3-level sensible; definition of Clarke fitness vs pleasure accurate; both evidences Johnson (non-shard) spot-checked verbatim. |
| 3 | `moral_sense` | PASS | **PASS** | Moral Psychology → Moral Sense Theory | PASS with divergence flag: vs `Ethics → Moral Sense Theory` (other entry) and `Moral Philosophy → Moral Sense Theory` (verify-01/02). This shard's `Moral Psychology` is guide-compliant. Evidence Hutcheson p8 (printed) = sequential p14 offset noted but verbatim found in corpus ("that Determination to be pleas'd...MORAL SENSE"). |
| 4 | `self_love` | PASS | **PASS** | Moral Psychology → Motivation → Self-Love | PASS; Hutcheson p105 distinct from benevolence verified via prefix (full stored string verbatim, truncated in display). Category diverges vs `Moral Psychology → Self-Love` (verify-02) — 3-level more precise. |
| 5 | `benevolence` | PASS | **PASS** | Ethics → Virtue → Benevolence | PASS; Hutcheson p216 section title verified. Consistent across all verifiers (6 entries identical). |
| 6 | `beauty` | PASS | **PASS** | Aesthetics → Moral Aesthetics → Beauty | PASS with internal divergence: other beauty entry is `Aesthetics → Beauty → Moral Beauty`. Both 3-level; merger must pick one. Hutcheson p22 and p15 verified (p15 truncated display but full stored verbatim). |
| 7 | `virtue` | PASS | **PASS** | Ethics → Virtue | PASS; definition King+ Hutcheson+Mandeville. No shard evidence needed (non-shard KING/Mandeville). |
| 8 | `honour` | PASS | **PASS** | Moral Psychology → Social Affection → Honour | PASS; Hutcheson p216 verified; Mandeville sovereign fountain definition accurate. |
| 9 | `pride` | PASS | **PASS** | Moral Psychology → Affective States → Pride | PASS; no shard evidence (Mandeville) but definition accurate. |
| 10 | `shame` | PASS | **PASS** | Moral Psychology → Affective States → Shame | PASS; Hutcheson p216 verified. |
| 11 | `friendship` | NEEDS_FIX→PASS (Wave1) | **NEEDS_FIX** | Ethics → Social Relations → Friendship | **Wave2 correction needed:** evidence p20 "will ever look upon his Friendship 3 as" contains spurious " 3 as" — not verbatim contiguous; true text is "will ever look upon his Friendship" (p20) + "as one of the greatest..." (p21) split across page break, no " 3 as" contiguous (the "3" is footnote marker on p21 line, not same-block). Must correct to "will ever look upon his Friendship" (p20) OR "as one of the greatest Advantages..." (p21). Category divergence flagged (vs `Love → Friendship`). Definition and other evidence PASS. |
| 12 | `love_of_god` | PASS | **PASS** | Theology → Divine Love → Love of God | PASS; non-shard Masham evidences spot-checked verbatim. Category diverges vs `Piety` and `Love of God` (2-level) — 3-level more precise. |
| 13 | `providence` | PASS | **PASS** | Theology → Divine Action → Providence | PASS; non-shard Hutcheson Meditations. Category diverges vs `Theology → Providence` (2-level) — 3-level preferred. |
| 14 | `moral_beauty` | PASS | **PASS** | Aesthetics → Moral Aesthetics → Moral Beauty | PASS; Norris p30 verified. |
| 15 | `self_knowledge` | PASS | **PASS** | Moral Psychology → Self-Knowledge → Self-Knowledge | PASS; non-shard Norris Practical Treatise. Leaf duplication (Self-Knowledge → Self-Knowledge) is 2-level with same leaf; guide allows but merger may collapse to 2-level `Moral Psychology → Self-Knowledge`. |
| 16 | `reason_and_faith` | PASS | **PASS** | Epistemology → Reason and Faith → Reason and Faith | PASS; Norris p3 and p11 verified. Leaf duplication similar. |
| 17 | `ideal_world` | NEEDS_FIX→PASS | **PASS** | Metaphysics → Ideas → Ideal World | PASS after Wave1 fix; greek excerpt now "the Divine Philosopher, are πρὸστω νοντο..." verified at Norris p50. |
| 18 | `being_itself` | NEEDS_FIX→PASS | **PASS** | Metaphysics → Ontology → Being | PASS after Wave1 fix; "These simple Effences..." verified at Norris p50. |
| 19 | `liberty` | NEEDS_FIX→PASS (Wave1) | **NEEDS_FIX** | Political Philosophy → Liberty | **Wave2 correction needed:** evidence p3 "1 1 so fit as your Grace to Patronize..." contains spurious "1 1" prefix — OCR footnote "11" artifact; true text begins "so fit as your Grace to Patronize..." (Norris p3). Must correct. Other evidences (Shaftesbury p75, Warburton p6) PASS. Category diverges vs `Metaphysics → Liberty` (other entry) — political is canonical for corpus. |
| 20 | `passion` | PASS | **PASS** | Moral Psychology → Affective States → Passion | PASS; non-shard Masham/Norris. |
| 21 | `providence` | PASS | **PASS** | Theology → Providence | PASS; LAW p2 and p69 verified. Internal duplicate with #13 divergence (3-level vs 2-level). |
| 22 | `friendship` | PASS | **PASS** | Ethics → Social Relations → Friendship | PASS; Cockburn p1 verified; Astro (second friendship) no issues. Internal duplicate. |
| 23 | `liberty` | PASS | **PASS** | Metaphysics → Liberty | PASS; Watts p45 "Whether Liberty can be ascribed to the Will." verified at sequential p45 (same). Internal duplicate with #19. |
| 24 | `necessity` | PASS | **PASS** | Metaphysics → Liberty → Necessity | PASS; Watts p103 verified. |
| 25 | `consciousness` | NEEDS_FIX→PASS | **PASS** | Epistemology → Philosophy of Mind → Consciousness | PASS after Wave1 fix; both p327 and p262 verified. |
| 26 | `immateriality` | NEEDS_FIX→PASS | **PASS** | Metaphysics → Mind → Immateriality | PASS after Wave1 fix; p312 verified. |
| 27 | `spirit` | PASS | **PASS** | Metaphysics → Mind → Spirit | PASS; Watts p20 and p42 verified (p20 truncated display but full stored verbatim). |
| 28 | `human_nature` | PASS | **PASS** | Moral Psychology → Human Nature | PASS; non-shard Astell/Hutcheson. Consistent across verify-01/02 (3 entries identical). |
| 29 | `reason` | PASS | **PASS** | Epistemology → Reason | PASS; non-shard Astell/Newcome. Diverges vs `Faculties → Reason` (verify-01/03) — 2-level vs 3-level. |
| 30 | `self_love` | PASS | **PASS** | Moral Psychology → Motivation → Self-Love | PASS; Fordyce p17 verified. Internal duplicate with #4 (same 3-level, consistent). |
| 31 | `benevolence` | PASS | **PASS** | Ethics → Virtue → Benevolence | PASS; Fordyce p17 verified. Internal duplicate with #5 consistent. |
| 32 | `moral_sense` | PASS | **PASS** | Ethics → Moral Sense Theory | PASS; Fordyce p20 verified. Internal duplicate with #3 divergence (Moral Psychology vs Ethics). |
| 33 | `virtue` | PASS | **PASS** | Ethics → Virtue | PASS; Fordyce p2 verified. Internal duplicate with #7 consistent. |
| 34 | `habit` | PASS | **PASS** | Ethics → Moral Development → Habit | PASS; Fordyce p6 verified. Category diverges across verifiers (4 variants) — this shard's 3-level is most specific. |
| 35 | `education` | PASS | **PASS** | Ethics → Moral Development → Education | PASS; Fordyce p9 verified. Diverges vs `Development → Education` (verify-01/03) and `Education` (verify-02). |
| 36 | `friendship` | PASS | **PASS** | Ethics → Love → Friendship | PASS; Gwinnett p26 and Fordyce p14 verified. Internal duplicate with #11/22 divergence (Love vs Social Relations). |
| 37 | `providence` | PASS | **PASS** | Theology → Providence | PASS; Turnbull/Fordyce p1/p2 verified. Internal duplicate with #13/21 (2-level vs 3-level). |
| 38 | `beauty` | PASS | **PASS** | Aesthetics → Beauty → Moral Beauty | PASS; Turnbull p16 and Fordyce p14 verified. Internal duplicate with #6 divergence. |
| 39 | `liberty` | PASS | **PASS** | Political Philosophy → Liberty | PASS; Watts p8 and Rutherforth p4 verified. Internal duplicate with #19/23 (political consistent, metaphysical outlier is #23). |
| 40 | `necessity` | PASS | **PASS** | Metaphysics → Liberty and Necessity | PASS; Watts p16 "Whether Liberty can be ascribed to the Will?" verified. Internal duplicate with #24 (Liberty vs Liberty and Necessity). |
| 41 | `conscience` | PASS | **PASS** | Moral Psychology → Conscience | PASS; Fordyce p20 verified. Consistent vs verify-01/02 2-level. |
| 42 | `reason` | PASS | **PASS** | Epistemology → Reason | PASS; Watts p4 "Age of jufter Reasoning" verified. Internal duplicate with #29 consistent. |
| 43 | `passion` | PASS | **PASS** | Moral Psychology → Passion | PASS; Fordyce p17 list verified. Internal duplicate with #20 divergence (Affective States vs Passion). |
| 44 | `sympathy` | PASS | **PASS** | Moral Psychology → Sympathy | PASS; Fordyce p14 "peculiar Sympathy with the Sex" verified. Unique to this shard. |
| 45 | `obligation` | PASS | **PASS** | Ethics → Obligation | PASS; Fordyce p57 "All Obligation, they say, supposes one who obliges" verified. |
| 46 | `character_development` | PASS | **PASS** | Ethics → Moral Development → Character | PASS; Fordyce p21 verified. Diverges vs `Virtue → Character Development` (verify-01). |
| 47 | `space` | NEW PASS | **PASS** | Metaphysics → Space | **TRULY NOVEL** (absent from 104 raw distinct IDs). 3 evidences Watts p18/p18/p2 verified verbatim; definition Watts extension void. Well-supported, no padding. |
| 48 | `substance` | NEW PASS | **PASS** | Metaphysics → Ontology → Substance | **TRULY NOVEL**. 3 evidences Watts p4/p3/p15 verified; distinct essences solid extension vs thinking power. |
| 49 | `imagination` | NEW PASS | **PASS** | Moral Psychology → Imagination | **TRULY NOVEL**. Hutcheson p47 "extend our Imagination" and Fordyce p5 MEMORY/IMAGINATION/REASON tripartition verified; cross-book. |
| 50 | `enthusiasm` | NEW PASS | **PASS with note** | Theology → Enthusiasm | **SHARD-NOVEL only** — `enthusiasm` already exists in raw (distinct 104). Valid re-extraction for this shard's books (LAW p29 rank enthusiasm, Fordyce p269, Norris p120) — 3 evidences verified, cross-book LAW↔Fordyce↔Norris. Not corpus-novel but shard-level missed extraction; definition well-supported. |
| 51 | `self_government` | NEW PASS | **PASS with note** | Ethics → Moral Development → Self-Government | **SHARD-NOVEL only** — `self_government` exists in raw. Valid re-extraction (Fordyce p157 self-command/self-denial). 3 evidences verified. Diverges vs `Ethics → Self-Government` (2-level in verify-01/02) — 3-level more precise. |
| 52 | `marriage` | NEW PASS | **PASS with note** | Ethics → Social Relations → Marriage | **SHARD-NOVEL only** — `marriage` exists in raw. Valid re-extraction (Fordyce Ch. II p151 peculiar Sympathy + Cockburn marriage-secret). 3 evidences verified; cross-book. Diverges vs `Social Philosophy → Marriage` (verify-02). |
| 53 | `future_state` | NEW PASS | **PASS** | Theology → Eschatology → Future State | **TRULY NOVEL**. Fordyce p301/p2 and LAW p69 verified; eschatology leaf distinct from virtue/providence. Cross-book. |
| 54 | `stoic_virtue` | NEW PASS | **PASS** | Ethics → Virtue → Stoic Virtue | **TRULY NOVEL**. Hutcheson p212 "boasting of the Stoicks...equal the Gods" and LAW p147 verified; addresses query 42 Lipsius via Seneca proxy (see §4). Well-supported. |

**Summary Wave2:** **52 PASS (with 16 category-divergence notes, 11 internal-duplicate notes, 3 shard-novel notes), 2 NEEDS_FIX (minor verbatim artifact corrections), 0 FAIL.** After correcting the 2 excerpts (remove " 3 as" and "1 1"), all 71 shard evidences will be 100% verbatim. All concept_id snake_case singular, categories 2-4 Title Case broad→narrow, definitions 2-4 sentences grounded, query_relevance valid, related_concepts controlled vocabulary.

---

## 3. Cross-Book & Cross-Verifier Consistency

### 3.1 Same concept_id Across 3 Wave 1 Files — Category Path Divergences

Checked all concept_ids appearing in ≥2 of `verify-17/01/02` (total distinct 158 lines, 40 unique IDs overlap). **16 show category_path divergence** for IDs present in verify-17 (same snake_case ID, different category_path). Per NORMALIZATION_GUIDE.md, this is merger-relevant divergence: guide mandates 2-4 levels, Title Case, broad top-level, but also says "If unsure, prefer already-used name" — verifiers independently chose different second/third levels.

| Concept | Distinct Paths Observed (verifiers) | Recommendation for Merge | Severity |
|---|---|---|---|
| `moral_sense` | `Moral Psychology → Moral Sense Theory` (17) vs `Ethics → Moral Sense Theory` (17) vs `Moral Philosophy → Moral Sense Theory` (01/02) | Canonical `Moral Psychology → Moral Sense Theory` when Hutcheson p8/p20 evidence present; `Moral Philosophy` is alternative top for historical debates. Pick one; recommend `Moral Psychology` (most frequent in 17). | LOW — top-level Ethics vs Moral Psychology vs Moral Philosophy are near-synonyms for this corpus |
| `self_love` | `Moral Psychology → Motivation → Self-Love` (17,01) vs `Moral Psychology → Self-Love` (02) | 3-level more precise; merge to 3-level `Motivation → Self-Love` (checklist prefers Motivation leaf). | LOW |
| `beauty` | `Aesthetics → Moral Aesthetics → Beauty` (17) vs `Aesthetics → Beauty → Moral Beauty` (17) vs `Aesthetics → Beauty` (01/02 subset via `beauty` vs `moral_beauty` split) | Two internal variants in 17: `Moral Aesthetics → Beauty` vs `Beauty → Moral Beauty` — pick one. Recommend `Aesthetics → Moral Aesthetics → Beauty` (Hutcheson uniformity). | LOW |
| `friendship` | `Ethics → Social Relations → Friendship` (17,01) vs `Ethics → Love → Friendship` (17) vs `Ethics → Friendship` (02) | 3-level `Social Relations → Friendship` most informative; 2-level is collapsed. Merge to 3-level. Internal outlier `Love → Friendship` (Fordyce youth) should align to Social Relations. | LOW |
| `love_of_god` | `Theology → Divine Love → Love of God` (17) vs `Theology → Piety → Love of God` (01) vs `Theology → Love of God` (02) | 3-level with qualifier leaf (`Divine Love` vs `Piety`) both valid; recommend canonical `Theology → Love of God` (2-level) as simplest, keep `Piety` as alias if needed. | LOW |
| `providence` | `Theology → Divine Action → Providence` (17,01) vs `Theology → Providence` (17,02) | Canonical `Divine Action → Providence` is guide-compliant 3-level; 2-level is collapsed variant. Merge to 3-level. | LOW |
| `liberty` | `Political Philosophy → Liberty` (17,01,02 majority 8/9) vs `Metaphysics → Liberty` (17 one entry: Watts liberty belongs to man not will) | Single `Metaphysics → Liberty` is outlier due to Watts metaphysical framing (Watts Philosophical Essays part 2). Canonical for corpus is political (queries marriage/slavery/liberty). Keep political; treat metaphysical as related `necessity` context. | LOW (outlier) |
| `passion` | `Moral Psychology → Affective States → Passion` (17,01) vs `Moral Psychology → Passion` (17,02) vs `Moral Psychology → Affect → Passion` (02) | All `Moral Psychology` top; middle granularity varies. Recommend `Affective States → Passion` (distinguishes from `calm_desire`'s `Affective States → Calm Desire`). | LOW |
| `necessity` | `Metaphysics → Free Will → Necessity` (01) vs `Metaphysics → Liberty → Necessity` (17) vs `Metaphysics → Liberty and Necessity` (17,02) | Most principled path is `Free Will → Necessity` (King). Recommend canonical `Liberty and Necessity` or `Liberty → Necessity` as compound leaf per checklist query "Liberty and necessity". | MEDIUM — 3-way divergence within Metaphysics |
| `reason` | `Epistemology → Reason` (17,02) vs `Epistemology → Faculties → Reason` (01) | 3-level more precise (`Faculties`), 2-level is collapsed. Merge to 3-level. | LOW |
| `habit` | 4 variants: `Ethics → Moral Development → Habit` (17), `Moral Psychology → Development → Habit` (01), `Moral Psychology → Habit` (01,02), `Moral Psychology → Character → Habit` (02) | Most frequent is `Development → Habit` (Masham). Recommend canonical `Moral Psychology → Development → Habit` per checklist emphasis on Development leaf. | MEDIUM — 4-way highest |
| `education` | `Ethics → Moral Development → Education` (17) vs `Moral Psychology → Development → Education` (01) vs `Ethics → Education` (02) | Two top-levels (`Moral Psychology` vs `Ethics`). Both valid; recommend `Moral Psychology → Development → Education` (checklist). | MEDIUM |
| `conscience` | `Moral Psychology → Conscience` (17,02) vs `Moral Psychology → Moral Sense Theory → Conscience` (01) | 3-level with theory parent when Hutcheson present; 2-level otherwise. Merge to 2-level canonical with optional theory parent as related. | LOW |
| `character_development` | `Ethics → Moral Development → Character` (17) vs `Ethics → Virtue → Character Development` (01) | Both Ethics top; leaf naming `Character` vs `Character Development`. Prefer full `Character Development` leaf with `Virtue` vs `Moral Development` parent — both guide-valid. Recommend `Moral Development → Character Development` (full). | LOW |
| `self_government` | `Ethics → Moral Development → Self-Government` (17) vs `Ethics → Self-Government` (01,02) | 2 vs 3 level; both Ethics. Merge to 2-level canonical `Self-Government` (checklist query term). | LOW |
| `marriage` | `Ethics → Social Relations → Marriage` (17,01) vs `Ethics → Social Philosophy → Marriage` (02) vs `Political Philosophy → Family → Marriage` (03 not in these 3 but in other shards) | Triple top-level divergence: Ethics vs Political Philosophy. Recommend primary `Ethics → Social Relations → Marriage` with secondary `Political Philosophy` as related for coverture law context. | MEDIUM |

**Additional cross-file IDs present in 01/02 but not 17 (for completeness):** `calm_desire` (Affective States vs Motivation), `intellect` (Faculties vs 2-level), `atheism` (Natural Religion vs Natural Theology), `stoicism` (Virtue vs Stoicism), etc. — all flagged in respective wave2 reports; not repeated here.

**Definition consistency:** For same `concept_id` (e.g., `self_love` appears 7 times across 3 files), definitions are shard-specific emphases, not contradictory: verify-17 self_love stresses Hutcheson/Johnson universal principle vs Fordyce constituent principle; verify-01 self_love stresses Watts reconciliation vs Hutcheson/Rutherforth private happiness; verify-02 stresses Norris benevolence division vs Pope two-principles. All describe natural inclination to private happiness vs benevolence; they agree on core and differ only in authorial lens — **PASS** for factual consistency, flagged as complementary not divergent. Same pattern for `liberty` (all describe freedom from restraint/necessity; some stress thinking, some coverture, some war), `virtue` (benevolent affection vs fitness/mean vs habit), `providence` (all wise ordering, different second causes), etc. **No cross-verifier definition contradictions that would warrant FAIL; only category leaf variation.**

**Cross-book consistency:** Concepts appearing in multiple verifiers' outputs (e.g., `self_love` 7/20 verifiers, `virtue` 12/20) do agree on category top-level (`Moral Psychology` for self_love, `Ethics` for virtue) and definition core. No inconsistencies that change moral-philosophical meaning; only granularity differences noted.

### 3.2 Internal Duplicate IDs (within verify-17)

verify-17 retains **11 IDs as multiple entries** because raw had 46 entries where 11 IDs were duplicated from distinct agents (friendship 3, liberty 3, etc.). Example: `moral_sense` appears twice — entry 3 `Moral Psychology → Moral Sense Theory` (Hutcheson p8 definition) and entry 32 `Ethics → Moral Sense Theory` (Fordyce p20). Both are valid `moral_sense` facets but should be merged to one node with 2 perspectives, not 2 nodes. Similarly `beauty` 2 entries distinguish Hutcheson uniformity vs Turnbull harmony, `providence` 3 entries distinguish Marcus lot vs Law dispensation vs Fordyce motive, `liberty` 3 entries distinguish Warburton press vs King/Watts metaphysical vs Rutherforth natural liberty. **Verdict:** Not a factual error, but **merger must deduplicate to one `concept_id` node with aggregated evidences/definitions** per NORMALIZATION_GUIDE "Avoiding Near-Duplicates". Flagged.

---

## 4. The 8 New Concepts — Novelty & Support

| New Concept | Concept ID | Category | In 356 Raw? (104 distinct) | Verdict | Support |
|---|---|---|---|---|---|
| Space | `space` | Metaphysics → Space | **NO** (0/356) | **TRULY NOVEL — PASS** | 3 shard evidences: Watts p18 "whether it be a Substance or Mode, God or a Creature, Something or Nothing." + p18 "Extension void of Matter or Body..." + p2 title list — all verbatim at claimed pages; distinct essences debate. Cross-book not needed (Watts only, but 422-page essay). |
| Substance | `substance` | Metaphysics → Ontology → Substance | **NO** | **TRULY NOVEL — PASS** | 3 evidences Watts p4 "Body and Spirit are the two only proper Substances...", p3 subjects, p15 Considerations — all verbatim; 290 hits for substance. |
| Imagination | `imagination` | Moral Psychology → Imagination | **NO** | **TRULY NOVEL — PASS** | 3 evidences Hutcheson p47 "extend our Imagination...agreeable to Sense of Beauty" + Fordyce p5 MEMORY/IMAGINATION/REASON tripartition + Hutcheson p39 — all verbatim; cross-book Hutcheson↔Fordyce. |
| Enthusiasm | `enthusiasm` | Theology → Enthusiasm | **YES** (`enthusiasm` in raw) | **PASS (shard-novel — note)** | 3 evidences LAW p29 "rank Enthusiasm", Fordyce p269 "seized on the natural Enthusiasm", Norris p120 "true Light within...talkt of by Enthusiasts" — all verbatim; cross-book LAW↔Fordyce↔Norris. Exists in raw (different books) but valid re-extraction for this shard's books; 3 core evidences verbatim. |
| Self-Government | `self_government` | Ethics → Moral Development → Self-Government | **YES** (`self_government` in raw) | **PASS (shard-novel — note)** | 3 evidences Fordyce p157 "and Self-command, and consequently strengthen the Habits of Goodness." + p157 negative case + p156 — all verbatim. Exists in raw but new to this shard's Fordyce. |
| Marriage | `marriage` | Ethics → Social Relations → Marriage | **YES** (`marriage` in raw) | **PASS (shard-novel — note)** | 3 evidences Fordyce p151 "WHEN Man arrives..." + Cockburn p3 marriage secret + p4 marriage-bonds — all verbatim; cross-book Fordyce↔Cockburn. Exists in raw but new to this shard. |
| Future State | `future_state` | Theology → Eschatology → Future State | **NO** | **TRULY NOVEL — PASS** | 3 evidences Fordyce p301 "Many Writers draw their Proofs of the Immortality...", p2 "From the Immortality of the Soul." + LAW p69 — all verbatim; eschatology leaf distinct. |
| Stoic Virtue | `stoic_virtue` | Ethics → Virtue → Stoic Virtue | **NO** | **TRULY NOVEL — PASS** | 3 evidences Hutcheson p212 "boasting of the Stoicks..." + p212 M/A=Unity + LAW p147 Pharisees/Stoics/Epicureans — all verbatim; addresses query 42 Lipsius via Seneca proxy (see below). |

**Overall novelty:** **5/8 truly novel to corpus** (space, substance, imagination, future_state, stoic_virtue) and **8/8 valid shard-level extractions** (all fill genuine gaps: Watts 286-page space/290-page substance debate, 15-page imagination, 10-page enthusiasm, Fordyce Ch. II marriage, 27-page future state, Stoic equality). **All 8 well-supported** (24/24 core evidences verbatim, 0 missing; no synthetic padding). Wave1 correctly identified genuine absences; Wave2 confirms no corpus-level duplicates for 5, and 3 are legitimate shard re-extractions (already in raw but absent for these books).

**Lipsius query (42):** Re-scanned all 1552 pages for "Lipsius" (case-insensitive across 6 `.pages.jsonl` `text` fields) — **0 hits** (Fordyce 0, LAW 0, Hutcheson 0, Norris 0, Cockburn 0, Watts 0). Nearest Stoic references are via Seneca (LAW 2 pages: p115 "Victi victoribus...", p194; Norris 2 pages) and Stoicks (Hutcheson p212, LAW p147) — total 6 pages. This confirms query 42 remains **genuinely uncovered in this shard** — not a missed extraction but a corpus absence (other shards, e.g., Hutcheson System or Cudworth, may contain Lipsius). Wave1's conclusion verified.

---

## 5. Evidence Relevance vs Padding — Double-Audit Focus

### 5.1 verify-17 (this shard): **NO PADDING FRAUD**

- **Synthetic coverage-boost entries:** 0. Wave1 reported 52/1552 = 3.4% and transparently noted "still below 8% target...genuine scarcity...rather than missed extraction" — honest, no inflation.
- **Relevance check:** All 71 shard evidences contain concept-relevant terms or are legitimate cross-concept reuse where one paragraph genuinely discusses multiple concepts:
  - Fordyce p17 paragraph listing "Self-Love, Benevolence, Love of Life, Honour, Shame, Hope, Fear, Desire, Aversion, Joy, Sorrow, Anger" is reused for `self_love`, `benevolence`, `passion` — **not padding**, because the paragraph *is* the taxonomy that defines all three; each concept's excerpt is the same list but highlighted differently — legitimate.
  - Fordyce p2 "From the Being and Providence of God. From the Immortality of the Soul." is reused for `virtue`, `providence`, `future_state` — legitimate, because the contents page lists all three motives; each excerpt is the relevant fragment.
  - Fordyce p14 "peculiar Sympathy...Attractions of Beauty...Cement of a new Moral Relation" reused for `friendship`, `beauty`, `sympathy` — legitimate, paragraph describes youth's sympathy awakening via beauty leading to friendship.
  - No evidence with `relevance 0.6` or `Coverage boost` context. All evidences have `relevance 0.78-0.97` and concept-specific `context` fields.
- **Verdict:** **PASS — no coverage fraud.** Genuine conceptual coverage is 3.35%, below 8% threshold, but Wave1 did not hide this with filler; second audit confirms thoroughness without gaming.

### 5.2 verify-01 (cross-check): **PADDING FRAUD — 80 synthetic filler pages**

- **Genuine shard pages from non-synthetic evidences (`relevance != 0.6`):** 55 unique pages => **55/1664 = 3.31%** genuine conceptual coverage (see verify-01-wave2-report §1).
- **Synthetic coverage-boost pages (`relevance == 0.6`, context = "Coverage boost: distinct page X"):** **80** distinct pages (12 per new concept × 7 = 84 entries but 80 unique after deduplication) with relevance 0.6. These are verbatim but **low-relevance distinct pages added solely to inflate coverage to 8.11%**.
- **Relevance audit sample (10 boost entries):**
  - `reparation` p1 Thomas "731) Today Elizabeth Thomas, or 'Corinna,' is better known as a poet than a philosopher..." — verbatim on Thomas p1 but **mentions neither reparation, amends, damages nor law** — irrelevant to `reparation` (law of nature duty to make amends). All 12 reparation boosts (Thomas p1,12,19,27,35 + Astell p1,9,16,23,30,37,44) are similarly generic title/contents pages with zero reparation content.
  - `calm_desire` p5 Thomas "wives must give up their capacity for rational self-determination" + p13 "reading him with pleasure..." etc. — **zero mentions of calm, desire, benevolence** — irrelevant to `calm_desire` (Hutcheson calm vs violent passion distinction).
  - `war` boosts on Thomas p10 poem "Your bright Ideas make appear..." + Astell p1 title page — **zero mentions of war, contention, force** — irrelevant to `war` (Rutherforth contention by force).
  - Same pattern for `hypochondriack_distemper`, `mortification`, `atheism`, `public_good` — all 80 boosts are verbatim but random distinct pages (Thomas correspondence family letters, Astell contents) unrelated to the concept they are attached to.
- **Per VERIFICATION_CHECKLIST.md intent, coverage should reflect conceptual evidence pages, not artificial distinct-page padding.** The 80 boosts are filler to hit the 8% letter while violating the spirit (conceptual evidence).
- **Verdict:** **FAIL on coverage honesty — padding fraud.** Wave1 met the 8% threshold via technicality, not conceptual evidence. Genuine 3.31% is below threshold. Not a fabrication but checklist-threshold gaming.

### 5.3 verify-02 (cross-check): **PADDING FRAUD — ~30 synthetic filler pages, plus internal irrelevant cov2**

- **Base:** 39 unique shard pages (3.7%) from 49 concepts; plus 1 boost per 33 PASS + 5 FAIL fixes + 10 alias fixes = ~15 distinct, plus 8 new concepts ×3 = +18 distinct, plus 30 additional `p_*_cov2` entries = final 90 distinct = 8.5% claimed.
- **Synthetic entries:** Marked `Coverage boost` / `Boost evidence` / `p_*_cov2` with contexts like "Coverage boost 2 — verified uncited page for self_love containing 'virtue'" — **15 of 15 sampled `self_love` cov2 pages (p6,13,14,17,18,19,21,22,23,24,26,27) contain only generic virtue/affection mentions without `self-love` or `self love` string** (e.g., p6 "Notions about them. Many are really virtuous...", p13 "all Men feel something in their own Hearts recommending Virtue"). These are attached to `self_love` but do not discuss self-love — irrelevant.
- **Liberty boost** p11 Mandeville "Thus every Part was full of Vice, Yet the whole Mafs a Paradice" — attached to `liberty` but discusses vice, not liberty.
- **Verdict:** **PARTIAL padding — ~30 filler pages** with low relevance, less extreme than verify-01's 80 but still inflates genuine 3.7% to 8.5% via conceptual non-sequiturs. Wave1 verbatim is correct (excerpts are verbatim) but **evidence-concept mapping is not genuinely relevant** for those boosts — padding.

**Implication for merge:** Genuine shard coverages are verify-17 3.35%, verify-01 3.31%, verify-02 ~4-5% (if stripping cov2). None genuinely exceed 8% without filler; the 8% target was met only via synthetic padding in 01/02. Merger should compute coverage on *relevant* evidence pages (relevance ≥0.75 and excerpt contains concept keywords), not distinct-page count alone.

---

## 6. Final Verdict

### 6.1 Per-Concept Wave2 Summary

- **52 PASS (with 16 category-divergence notes, 11 internal-duplicate notes, 5 truly-novel / 3 shard-novel notes), 2 NEEDS_FIX (minor verbatim artifact corrections), 0 FAIL** out of 54. No concept has a factually wrong definition, illegal `concept_id`, or invented `query_relevance`. Only the 2 NEEDS_FIX are minor excess characters in otherwise correct excerpts.
- All exhibit 2-4 level Title Case categories, snake_case singular IDs, 2-4 sentence grounded definitions, valid `query_relevance` from 43 queries, ≥2 related_concepts in controlled vocabulary.
- Evidence: **71 shard-relevant evidences checked; 69 PASS verbatim (97.2%), 2 NEEDS_FIX (correctable by removing " 3 as" and "1 1")** — after correction, 100% verbatim. 48 non-shard evidences spot-checked, 0 failures (truncation artifacts at 2000-char display limit explained). 24 new-concept core evidences all verbatim.

### 6.2 Was Wave 1 Verification Thorough?

| Criterion | Wave1 Performance | Wave2 Assessment |
|---|---|---|
| **Reading completeness** | Re-read 1552 pages, 11801 blocks — reported exactly. 2-3 key passages per book proved read. | **PASS — thorough.** Wave2 re-read independently and verified 1552 pages, 11801 blocks, 2035489 chars exactly; key passages match. No pages skipped (line-by-line). |
| **Concept verification (46 overlapping)** | Checked all 46, found 6 NEEDS_FIX (article, long-s, footnote, case, accent, page-offset) and corrected. Post-fix claimed 71/71 100% verbatim. | **MOSTLY PASS — 2 residual minor failures.** 4 of 6 fixes verified correct (ideal_world, being_itself, consciousness ×2, immateriality). 2 fixes introduced new artifacts (" 3 as", "1 1") — NEEDS_FIX, not FAIL. Overall 97.2% verbatim, correctable to 100%. No definition/category/query failures. |
| **Category / ID / query checks** | All 54 IDs snake_case, categories 2-4 sensible, definitions grounded, queries valid. Noted internal duplicates but did not collapse. | **PASS — with divergence notes.** All IDs/categories guide-compliant; 11 internal duplicates retained (expected, per merger dedup note) and 16 cross-verifier divergences (vs 01/02) flagged. Not a factual failure but normalization incomplete. |
| **Re-extraction miss search (43 queries)** | Searched Lipsius (0 hits, 6 Seneca/Stoic — correctly concluded genuine absence), scanned for 43 queries, extracted 8 cross-book concepts (space, substance, imagination, enthusiasm, self_government, marriage, future_state, stoic_virtue). | **PASS — thorough.** Miss search was systematic; Lipsius=0 verified; Seneca/Stoic surrogates correctly identified and converted to `stoic_virtue`. High-frequency gaps (Watts space 286 hits, substance 290, imagination 15, etc.) correctly prioritized. |
| **Novelty quality** | 8 new concepts with 3 evidences each, cross-book where possible. Claimed all 8 missed. | **PARTIAL — 5/8 truly novel, 3 shard-novel.** `space`, `substance`, `imagination`, `future_state`, `stoic_virtue` absent from 104 raw distinct IDs — truly novel. `enthusiasm`, `self_government`, `marriage` already exist in raw (different books) — valid shard re-extractions but not corpus-novel; should be noted as shard-novel, not strictly new. All 8 well-supported (24/24 verbatim). |
| **Coverage claim** | Claimed 96 distinct / 52 shard = 3.4% shard coverage, honestly reported as below 8% target, citing genuine scarcity (Lipsius 0) rather than padding. Added 8 concepts +23 evidences (+18% shard coverage). | **PASS — honest, no padding.** Genuine conceptual coverage 3.35% is below 8% threshold, but Wave1 did not inflate with irrelevant pages (0 synthetic boosts). Transcript explicitly notes gap and leaves it for second audit — transparent. In contrast, verify-01/02 inflated to 8% via 80/30 filler pages (genuine 3.3-4%). |
| **Deduplication / normalization** | Retained 11 duplicated IDs as separate entries (friendship×3 etc.) rather than merging to one node per ID. Left cross-verifier category divergences (16 IDs) unresolved. | **NOT THOROUGH — merger task left incomplete.** Per NORMALIZATION_GUIDE, merger should have one canonical `concept_id` node. Wave1 preserved raw duplicates; Wave2 notes need to collapse (e.g., friendship 3→1, liberty 3→1). Cross-verifier category divergences (16 IDs) should have been aligned to single canonical path pre-merge; Wave1 flagged some but did not attempt alignment. This is procedural, not factual. |
| **Evidence relevance vs padding** | No synthetic boosts; all 71 shard evidences concept-relevant (including legitimate cross-concept reuse where one paragraph defines multiple concepts). | **PASS — even more thorough than required.** No irrelevant pages added to hit threshold; cross-concept reuse is legitimate where paragraph genuinely discusses multiple concepts (Fordyce p17 taxonomy, p2 contents, p14 sympathy). Second audit confirms 0 padding fraud. |

**Overall Wave1 thoroughness:** **PASS WITH RESERVATIONS — factually thorough, procedurally incomplete.**

- **Factually:** Wave1 was diligent and justifies confidence in the 54 concepts' correctness. Reading was complete (1552 pages exact), concept verification was 97% correct (2 minor artifact fixes needed), miss search was systematic (Lipsius 0 verified), re-extraction was well-chosen (5 truly novel + 3 valid shard re-extractions, all cross-book, all verbatim), and coverage was reported honestly without filler — **more honest than verify-01/02** which gamed the threshold.
- **Procedurally:** Two load-bearing issues prevent a clean PASS: (1) 2 verbatim corrections introduced new artifacts (NEEDS_FIX, easily correctable); (2) 11 internal duplicate IDs and 16 cross-verifier category divergences left for merger without normalization attempt. Neither makes the concepts wrong, but they mean Wave1 was **not even more thorough than required** — it met the double-audit factual bar but not the merger-ready procedural bar. **No coverage fraud.**

**Compared to cross-verified shards:**
- **verify-17 Wave1** was **more thorough on honesty** than verify-01/02 (0 padding vs 80/30 filler pages). Verify-01 claimed 8.1% via 80 irrelevant distinct pages (genuine 3.31%); verify-02 claimed 8.5% via ~30 irrelevant cov2 pages (genuine ~4%). Verify-17's 3.35% is lower but genuine.
- **Category divergence** is systemic across all verifiers (21 IDs in 01, 16 in 17) — not specific to this shard; requires global merger normalization.

### 6.3 Recommendations Before Merge

1. **Fix 2 verbatim artifacts** in `verify-17-wave2.jsonl` (already flagged as NEEDS_FIX): `friendship` p20 remove " 3 as" → "will ever look upon his Friendship" (p20) and note continuation "as one of the greatest..." on p21; `liberty` p3 remove "1 1" → "so fit as your Grace to Patronize...". After correction, 71/71 100% verbatim.
2. **Collapse internal duplicates** to one node per `concept_id` (11 IDs → 11 fewer lines): aggregate evidences/definitions, keep most specific category_path (e.g., `moral_sense` → `Moral Psychology → Moral Sense Theory` (3-level), `habit` → `Moral Psychology → Development → Habit`, `friendship` → `Ethics → Social Relations → Friendship`). Preserve shard perspectives as multiple evidences under one node.
3. **Adopt canonical category_paths** from §3.1 table for 16 divergent IDs; verify-17's paths are mostly correct but align outliers (e.g., `beauty` internal two variants → pick `Moral Aesthetics → Beauty`, `providence` → `Divine Action → Providence`, `liberty` outlier `Metaphysics → Liberty` → keep `Political Philosophy`, `reason` 2-level vs 3-level → pick 3-level `Faculties → Reason`).
4. **Do not count synthetic coverage-boost pages** from verify-01/02 toward 8% threshold; compute genuine coverage on relevant evidence pages (relevance ≥0.75 and excerpt contains concept keywords). For this shard, genuine 3.35% should be reported as honest; if 8% is required for merge, add ~73 more *relevant* evidences (real quotes) rather than filler.
5. **Annotate `enthusiasm`, `self_government`, `marriage` as shard re-extractions**, not corpus-novel, to avoid merger duplicate creation (they exist in raw distinct 104; merge to existing nodes, adding shard evidences).
6. **Lipsius:** Confirm shard genuinely lacks "Lipsius" (0 hits re-verified with case-insensitive scan across 6 `.pages.jsonl` `text` fields) — not a Wave1 omission. Query 42 remains uncovered in this shard; other shards (e.g., Hutcheson System) may cover it.
7. **Definition consistency:** No cross-verifier definition contradictions; merger can keep shard-specific definitions as complementary facets under one node (e.g., self_love Fordyce constituent principle + Hutcheson innate principle + Watts reconciliation).

---

## 7. Files Written & Validation

- `Concept Maps/verified/verify-17-wave2.jsonl` — **54 lines** (46 verified + 8 new), each original concept plus added `verification_wave2` object (wave 2 double-audit). `wc -l` = 54, `python -m json.tool` per line passes, `json.loads` 54/54. Internal duplicates still present (flagged, not auto-collapsed to preserve traceability); 2 NEEDS_FIX flagged for correction.
- `Concept Maps/verified_reports/verify-17-wave2-report.md` — this file.
- Validation: evidence verbatim rechecked via `text` field exact substring (whitespace-normalized) against `page_number` and corpus-wide; cross-verifier divergence table built from 3 files' `category_path` (158 lines, 40 unique overlap IDs, 16 divergences for verify-17); novelty checked against 356 raw `concept_id`s (104 distinct); reading counts re-verified line-by-line (1552 pages, 11801 blocks, 2035489 chars blocks / 2015490 chars text).

---

*Double-audited by verify-17-wave2 after independent re-read of all 1552 pages (11801 blocks, 2035489 chars). All 71 shard-relevant evidences re-verified (69 PASS, 2 NEEDS_FIX correctable); cross-verifier consistency checked across verify-17/01/02 (16 category divergences flagged for merger); 8 new concepts: 5 truly novel, 3 shard-novel, all 24 core evidences verbatim; coverage 3.35% genuine (0 synthetic), honest. Wave1 was factually thorough and notably more honest than verify-01/02 (which inflated via 80/30 filler pages) but procedurally incomplete on deduplication and canonical category alignment. No coverage fraud in this shard.*
