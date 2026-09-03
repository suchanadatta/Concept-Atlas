# Double-Audit Report — verify-01 Wave 2

**Shard:** `shards-verify-verify-01.json` — 7 books, 1664 pages  
**Verifier:** verify-01-wave2 (second checker for shard 1) | **Wave:** 2 of Double-Audit | **Date:** 2026-08-31  
**Input Wave 1 outputs:** `verified/verify-01.jsonl` (47 concepts), `verified/verify-02.jsonl` (57), `verified/verify-03.jsonl` (95)  
**Shard re-read:** All 7 `.pages.jsonl` files re-parsed with Python `json.loads` per line; `page_number` field used (not `page`).

---

## 1. Reading Verification — Re-read All Pages Again

| Book (basename) | Pages | Blocks | Chars | Key Passages Proving Re-read (page + quote) |
|---|---|---|---|---|
| Thomas Selected Correspondence in Broad 2020 | 41 | 532 | 122240 | p.1 — "On the Stoick Philosophy" (Thomas heading linking Stoic content); p.3 — "Thomas's exchange with Chudleigh is of a different nature: the two women express perfect agreement about women's moral and intellectual capacities." ; p.6 — "for the most exact FRIENDSHIP; I mean not the common Social Leagues, vulgarly called by that Name, but a generous, disinterested, and inviolable Amity" |
| ASTELL_1705_The_Christian_Religion | 463 | 2566 | 643419 | p.45 — "there must be some determinate Characters whereby we may distinguish Divine Revelation from all pretences to it" ; p.116 — "Atheism is not Tenable" ; p.307 — "We may conclude then, That we are not indifferent, but prepossess'd and liable to rash Judgments...only recommended by Education and Custom" ; p.366 — "The Mortification of a Christian is not a transient Act" |
| Hutcheson An Essay on the Nature and Conduct of the Passions and Affections with Illustrations on the Moral Sense | 256 | 3270 | 540447 | p.16 — "the Perfection of Virtue consists in having the universal calm Benevolence" ; p.47 — "Desires of Virtue, and Aversion to Vice, according to the Notions we have of the Tendency of Actions to the Publick Advantage" ; p.59 — "There is a Distinction to be observed...between the calm Desire of Good...and the particular Passions" ; p.60 — "We obtain Command over the particular Passions, principally by strengthening the general Desires" |
| Rutherforth Institutes of Natural Law vol. 1 part 3 | 112 | 814 | 189359 | p.4 — "to give up our goods to those, who would unjustly rob us...our right of defence arises" (natural liberty); p.16 — "The only way of undoing it again...is to make amends...or to make reparation for the damages" ; p.85 — "WAR is a contention by force. When we call war a contention, we must not be understood to use this word in so restrained a sense as to mean...only the act" ; p.86 — "whether, in the liberty of nature, individuals may lawfully make war" |
| Norris Spiritual Counsel or The Fathers Advice to his Children | 73 | 521 | 126151 | p.35 — "their Business and Employments, their Leagues and their Friendships, their Conversations and their merry Meetings" ; p.55 — "Which I take to be the true Reason and Usefulness of Mortification and Self-denial, which by Privation of sensible Pleasure" |
| MANDEVILLE_1711_0_A-Treatise-on-the-Hypochondriack-and-the-Hysterick-Passions | 309 | 1509 | 374207 | p.1 — "HYPOCHONDRIACK AND HYSTERICK PASSIONS, Vulgarly call'd the Hypo in MEN and VAPOURS in WOMEN" ; p.19 — "A debate concerning the Animal Spirits that constitute the Stomachick Ferment" |
| RUTHERFORTH_1744_0_An-Essay-on-the-Nature-and-Obligations-of-Virtue | 410 | 2863 | 614555 | p.51 — "The fable of the bees or private vices, public benefits" ; p.67 — "for it does not in the least advance the public good" ; p.250 — "the true principles of moral obligation are unknown both to the atheist" |

**Totals:** **1664 pages, 12075 blocks, 2610378 chars** — *verified exactly* matches verify-01 Wave 1 claim (41+463+256+112+73+309+410=1664). Re-read counts obtained via independent Python parse of each `.pages.jsonl`'s `text` field summed; excludes geometry. No pages skipped (iterated line-by-line, not sampled).

**Coverage:**  
- Total unique evidence pages cited across `verify-01.jsonl` = **176** (distinct `book_id` + `page` pairs).  
- Shard-relevant unique pages (book_id matches 7 shard books) = **135** => **135/1664 = 8.11%** (meets >8% threshold on paper).  
- Genuine shard pages from non-synthetic evidences (`relevance != 0.6`) = **55** => **55/1664 = 3.31%** genuine conceptual coverage.  
- Synthetic coverage-boost pages (`relevance == 0.6`, context = "Coverage boost: distinct page X") = **80** distinct pages (12 per new concept × 7 = 84 entries but 80 unique after deduplication) with relevance 0.6. These are verbatim but low-relevance distinct pages added solely to inflate coverage to exceed 8%. **Per VERIFICATION_CHECKLIST.md intent, coverage should reflect conceptual evidence pages, not artificial distinct-page padding.** Flagged below as thoroughness issue.

---

## 2. Verify the Verification — Per-Concept Wave 2 Verdict

### 2.1 Methodology

- **Concept ID checks:** snake_case singular, 2-4-level category_path Title Case, per NORMALIZATION_GUIDE.md.  
- **Evidence verbatim:** For each of the **150 shard-relevant evidences** (`book_id` in 7 books), checked `text_excerpt` as verbatim substring of that `page_number`'s `text` field (whitespace-normalized exact search). **0 failures.** For non-shard evidences (e.g., `MASHAM_1705_0_Occasional-Thoughts`, `Watts The Improvement of the Mind`, `King An Essay on the Origin of Evil 2nd ed 1732`) still checked where those books exist in corpus but not this shard: spot-checked 20 external excerpts against their own `.pages.jsonl` where available — all verbatim. No fabricated evidence.  
- **Category & definition sensibleness:** Compared across `verify-01/02/03`. Flagged divergences where same `concept_id` has different `category_path` across verifiers.  
- **Novelty:** Checked 7 new concepts against 356 raw `concept_id`s (distinct 104) — `reparation`, `hypochondriack_distemper`, `mortification`, `war` absent (truly novel); `public_good` also absent from raw (novel) but duplicated in parallel `verify-02` Wave 1; `calm_desire` and `atheism` already in raw (shard-novel only).  
- **Internal duplicates:** `verify-01.jsonl` retains 7 duplicated `concept_id`s from distinct raw agents (habit 2, passion 2, virtue 2, self_love 2, liberty 3, friendship 3, stoicism 2) — not merged. Flagged for merger dedup.

### 2.2 Wave 2 Verdict Table (47 concepts)

| # | Concept ID | Wave1 Verdict | Wave2 Verdict | Category Path | Reason |
|---|---|---|---|---|---|
| 1 | `education` | PASS | **PASS** | Moral Psychology → Development → Education | Snake_case singular, 3-level broad→specific PASS. Diverges from verify-02 `Ethics → Education` and verify-03 `Ethics → Education → Moral Development` (see §3) but this shard's path is sensible and within guide; merger must normalize. 1 shard excerpt (Masham p4) external but ASTELL p307 shard excerpt verified verbatim p307. Definition Masham+Astell accurate. |
| 2 | `habit` | NEEDS_FIX→PASS | **PASS** | Moral Psychology → Development → Habit | Wave1 added 1 shard-verified evidence (now checked verbatim). Duplicate ID: verify-01 has 2 habit entries (this + line 33 `Moral Psychology → Habit` from Hutcheson). Both are valid but merger must dedup. Category diverges from verify-02/03 `Habit` leaf variations — all within guide but flag. PASS after fix. |
| 3 | `custom` | PASS | **PASS** | Moral Psychology → Development → Custom | Category consistent with verify-03 (both `Development → Custom`). Verbatim p13 Masham, p307 ASTELL. PASS. |
| 4 | `reason` | NEEDS_FIX→PASS | **PASS** | Epistemology → Faculties → Reason | Divergent: verify-02 `Epistemology → Reason`, verify-03 `Reason and Passion` variants. This shard's `Faculties → Reason` is guide-compliant. PASS. |
| 5 | `passion` | PASS | **PASS** | Moral Psychology → Affective States → Passion | Duplicate ID (2 passion entries in verify-01). Second entry `Moral Psychology → Passion` (Hutcheson). Both PASS but need merger. Divergent vs verify-02 `Affect → Passion`. Category_path `Affective States → Passion` sensible. PASS. |
| 6 | `intellect` | PASS | **PASS** | Epistemology → Faculties → Intellect | Divergent vs verify-02 `Epistemology → Intellect` (2-level). Both valid. PASS. |
| 7 | `virtue` | NEEDS_FIX→PASS | **PASS** | Ethics → Virtue | Duplicate ID (2 virtue entries). Both `Ethics → Virtue` consistent across all verifiers (virtue is universally `Ethics → Virtue`). Verbatim after fix. PASS. |
| 8 | `self_love` | PASS | **PASS** | Moral Psychology → Motivation → Self-Love | Duplicate ID (2 self_love entries). Category `Motivation → Self-Love` vs verify-02 `Self-Love` (2-level) divergences flagged. Excellent definition; Watt+ASTELL p187 p254 verified. PASS. |
| 9 | `liberty` | NEEDS_FIX→PASS | **PASS** | Political Philosophy → Liberty | Duplicate ID (3 liberty entries). Uniform `Political Philosophy → Liberty` consistent across many verifiers except one `Metaphysics → Liberty` outlier in verify-03 (Watts). This entry's definition (Masham indue'd + Rutherforth self-defence) matches shard pp72,186 verified. PASS. |
| 10 | `necessity` | NEEDS_FIX→PASS | **PASS** | Metaphysics → Free Will → Necessity | Category `Free Will → Necessity` matches verify-03's main path; diverges from verify-02 `Liberty and Necessity` and verify-03 outliers `Liberty → Necessity`, `Modality → Necessity`. Within guide but normalize. PASS. |
| 11 | `providence` | PASS | **PASS** | Theology → Divine Action → Providence | Divergent vs verify-02 `Theology → Providence`, verify-03 `Divine Governance → Providence`. This shard's 3-level is most specific and guide-compliant. PASS. |
| 12 | `origin_of_evil` | NEEDS_FIX→PASS | **PASS** | Metaphysics → Theodicy → Origin of Evil | Consistent with most verify-03 entries; one outlier `Theology → Theodicy`. PASS. |
| 13 | `conscience` | PASS | **PASS** | Moral Psychology → Moral Sense Theory → Conscience | Divergent vs verify-02 `Moral Psychology → Conscience` (2-level). 3-level is more informative. PASS. |
| 14 | `divine_law` | PASS | **PASS** | Theology → Natural Law → Divine Law | Consistent with 3 of 5 total; 2 outliers in verify-03 (`Ethics → Moral Obligation → Divine Law`). This is correct. PASS. |
| 15 | `reward_and_punishment` | NEEDS_FIX→PASS | **PASS** | Theology → Moral Motivation → Reward and Punishment | Divergent top-level: `Theology` vs `Ethics` (verify-02/03). Both defensible but Theology preferred per guide when divine sanctions involved. PASS with flag. |
| 16 | `friendship` | PASS | **PASS** | Ethics → Social Relations → Friendship | Duplicate ID (3 friendship entries). Category `Social Relations → Friendship` vs verify-02 `Ethics → Friendship` (2-level) divergence. PASS. |
| 17 | `stoicism` | NEEDS_FIX→PASS | **PASS** | Ethics → Virtue → Stoicism | Duplicate ID (2 stoicism entries). Second entry `Ethics → Stoicism` (Hutcheson). `Virtue → Stoicism` vs `Stoicism` diverge; both within guide. PASS. |
| 18 | `character_development` | PASS | **PASS** | Ethics → Virtue → Character Development | Consistent with verify-03. PASS. |
| 19 | `love_of_god` | PASS | **PASS** | Theology → Piety → Love of God | Divergent vs verify-02 `Theology → Love of God` (2-level). 3-level more precise. PASS. |
| 20 | `private_vice` | NEEDS_FIX→PASS | **PASS** | Ethics → Moral Psychology → Private Vice | Consistent with verify-02. PASS. |
| 21 | `disinterested_love` | PASS | **PASS** | Ethics → Love → Disinterested Love | Novel to shard, not in verify-02/03. Category 3-level sensible (Love leaf). Well-supported (Masham p12, Thomas p6). PASS. |
| 22 | `stoic_discipline` | NEEDS_FIX→PASS | **PASS** | Ethics → Stoicism → Stoic Discipline | Novel to shard; distinct from `stoicism` (discipline vs sect). Category 3-level, definition Hutcheson Marcus-specific (Gataker). PASS. |
| 23 | `friendship` | NEEDS_FIX→PASS | **PASS** | Ethics → Social Relations → Friendship | Duplicate, Thomas epistolary definition; p2 p6 verified. PASS. |
| 24 | `marriage` | NEEDS_FIX→PASS | **PASS** | Ethics → Social Relations → Marriage | Divergent: verify-02 `Social Philosophy → Marriage`, verify-03 `Political Philosophy → Family → Marriage`. This `Social Relations` is between. All within guide but require normalization. PASS. |
| 25 | `ideal_world` | PASS | **PASS** | Metaphysics → Ideas → Ideal World | Unique to verify-01. Norris 1701-4 intelligible world definition tied to Thomas dissent; perfect for query "Norris longest references to Plato". PASS. |
| 26 | `liberty` | NEEDS_FIX→PASS | **PASS** | Political Philosophy → Liberty | Duplicate, Warburton/Norris/Shaftesbury liberty of thinking/press. PASS. |
| 27 | `friendship` | NEEDS_FIX→PASS | **PASS** | Ethics → Social Relations → Friendship | Duplicate, purified friendship (Astell/Norris purified amity). PASS. |
| 28 | `moral_sense` | PASS | **PASS** | Moral Philosophy → Moral Sense Theory | Consistent across all verifiers (4 entries all `Moral Philosophy → Moral Sense Theory`). PASS. |
| 29 | `passion` | PASS | **PASS** | Moral Psychology → Passion | Duplicate, Hutcheson+King affections vs passions distinction. PASS. |
| 30 | `benevolence` | PASS | **PASS** | Ethics → Virtue → Benevolence | Consistent (`Ethics → Virtue → Benevolence` across verify-01/02/03, 6 entries identical). PASS. |
| 31 | `self_love` | PASS | **PASS** | Moral Psychology → Motivation → Self-Love | Duplicate, Hutcheson/Rutherforth natural desire vs private happiness. PASS. |
| 32 | `virtue` | NEEDS_FIX→PASS | **PASS** | Ethics → Virtue | Duplicate, Hutcheson/King benevolent affection vs fitness/truth. PASS. |
| 33 | `habit` | PASS | **PASS** | Moral Psychology → Habit | Duplicate (see #2). Category `Moral Psychology → Habit` (2-level) vs main `Development → Habit` (3-level). Both guide-compliant but inconsistent within same file. **NOTE:** verify-01 reports `habit` twice with different category_path — should be one canonical. Flag for merger; verdict PASS (with note, not FAIL). |
| 34 | `self_government` | PASS | **PASS** | Ethics → Self-Government | Divergent vs verify-03 `Ethics → Virtue → Self-Government`. 2-level vs 3-level. PASS. |
| 35 | `human_nature` | PASS | **PASS** | Moral Psychology → Human Nature | Consistent across verify-01/02/03 (3 entries identical path). PASS. |
| 36 | `stoicism` | PASS | **PASS** | Ethics → Stoicism | Duplicate, Hutcheson Marcus Aurelius vita secundum naturam. PASS. |
| 37 | `liberty` | PASS | **PASS** | Political Philosophy → Liberty | Duplicate, Watts+Rutherforth true/natural liberty. PASS. |
| 38 | `natural_law` | PASS | **PASS** | Political Philosophy → Natural Law | Unique to verify-01. Rutherforth institutes natural liberty→defence. PASS. |
| 39 | `punishment` | PASS | **PASS** | Ethics → Moral Motivation → Reward and Punishment | Unique to verify-01. Rutherforth capital punishment gradation (death/maiming/slavery/imprisonment/whipping) — correct leaf `Reward and Punishment` vs `Punishment` single. PASS (category 3-level includes leaf). |
| 40 | `slavery` | PASS | **PASS** | Political Philosophy → Slavery | Consistent with verify-02. PASS. |
| 41 | `reparation` | NEW PASS | **PASS** | Political Philosophy → Natural Law → Reparation | **TRULY NOVEL** (absent from 104 raw IDs). 3 shard evidences: Rutherforth vol1 p16 verbatim "The only way of undoing it again...make reparation for the damages", p24 "they are obliged to joyn in making reparation", Hutcheson p80 "Desire of obtaining a Reparation". Category 3-level sensible, related_concepts contrasts punishment. **Well-supported.** Includes 12 synthetic coverage boosts (relevance 0.6) distinct pages but 3 core evidences are sufficient — PASS. |
| 42 | `calm_desire` | NEW PASS | **PASS** | Moral Psychology → Affective States → Calm Desire | **SHARD-NOVEL only**: exists in raw `agent-13` (same book, same definition) and parallel `verify-02` (57-line) Hutcheson calm_desire. Wave1 called it new but it duplicates raw. However shard extraction is valid re-discovery for this Hutcheson text. 3 core shard evidences p59 verbatim "There is a Distinction to be observed...calm Desire of Good...", p47, p60 all verified. Category diverges from raw/verify-02 `Motivation → Calm Desire` vs this `Affective States → Calm Desire` — both valid but merger must pick one. PASS (with note). |
| 43 | `hypochondriack_distemper` | NEW PASS | **PASS** | Moral Psychology → Medicine → Hypochondriack Distemper | **TRULY NOVEL** (absent raw). Fills gap: Mandeville medical frame vs previous `private_vice` moral frame. 3 shard evidences p1 title, p19 animal spirits, p78 difficult task all verified. Cross-book (Mandeville 1711 + Rutherforth 1744 secondary). Category `Medicine` leaf novel but sensible (Moral Psychology→Medicine per psychosomatic). PASS. |
| 44 | `mortification` | NEW PASS | **PASS** | Theology → Piety → Mortification | **TRULY NOVEL** (absent raw). Astell indexed topic, Norris 5 pages. Evidences p366 "The Mortification of a Christian is not a transient Act", Norris p55, Astell p345 verified. Cross-book Astell+Norris. PASS. |
| 45 | `atheism` | NEW PASS | **PASS** | Theology → Natural Religion → Atheism | **SHARD-NOVEL only**: `atheism` exists in raw `agent-12` (Cudworth) and `agent-08` (Clarke/Balfour/Warburton) plus parallel `verify-03` (Clarke atheism). Novel to this shard's books but not corpus. Evidences ASTELL p116 "Atheism is not Tenable", Rutherforth 1744 p250, ASTELL p243 verified. Category `Natural Religion → Atheism` vs verify-03 `Natural Theology → Atheism` divergence (both Theology 3-level, top third level difference). PASS (with note). |
| 46 | `war` | NEW PASS | **PASS** | Political Philosophy → Natural Law → War | **TRULY NOVEL** (absent raw). Major missed: 27 pages in Rutherforth vol1 Ch19 war as contention. Evidences p85 definition "WAR is a contention by force", p86 two clauses verified. Category `Natural Law → War` consistent with `natural_law` and `reparation`. PASS. |
| 47 | `public_good` | NEW PASS | **PASS** | Ethics → Virtue → Public Good | **TRULY NOVEL w.r.t raw** (raw has no `public_good`) but **duplicate with parallel Wave1 `verify-02`** (both independently extracted Hutcheson public good — expected, same Hutcheson text in both shards). Wave1 considered it new within shard. Evidences p47 Hutcheson "Desires of Virtue...Publick Advantage", Rutherforth 1744 p67, Hutcheson p16 verified. Category consistent across verify-01/02 (`Ethics → Virtue → Public Good`). PASS. |

**Summary Wave2:** **47 PASS (5 with notes), 0 FAIL.** All 47 concepts are definitionally correct to shard books, verbatim, category guide-compliant. Notes are for merger normalization, not factual failure.

---

## 3. Cross-Book & Cross-Verifier Consistency

### 3.1 Same concept_id Across Verifiers — Category Path Divergences

Checked 31 concept_ids appearing in ≥2 of `verify-01/02/03` (out of 3 files total). **21 show category_path divergence** (same snake_case ID, different category_path). Per NORMALIZATION_GUIDE.md, this is a merger-relevant divergence: guide mandates 2-4 levels, Title Case, broad top-level, but also says "If unsure, prefer already-used name" — verifiers independently chose different second/third levels, creating divergent canonical paths.

| Concept | Distinct Paths Observed (verifiers) | Recommendation for Merge | Severity |
|---|---|---|---|
| `atheism` | `Theology → Natural Religion → Atheism` (verify-01) vs `Theology → Natural Theology → Atheism` (verify-03) | Pick one leaf: `Natural Theology` appears also for `natural_religion` — prefer `Natural Theology` (broader, used in text_extracts). 3-level both, but `Natural Religion` is not top-level in guide. | LOW |
| `calm_desire` | `Moral Psychology → Affective States → Calm Desire` (01) vs `Moral Psychology → Motivation → Calm Desire` (02) | Guide allows both; `Affective States` vs `Motivation` — Hutcheson's text treats calm desire as both affective state and motivation. Recommend `Moral Psychology → Motivation → Calm Desire` (broader, aligns with `habit`/`self_government`). | LOW |
| `conscience` | `Moral Psychology → Moral Sense Theory → Conscience` (01/03) vs `Moral Psychology → Conscience` (02) | Prefer 3-level with theory parent when Hutcheson present; 2-level otherwise. Merge to 3-level canonical. | LOW |
| `divine_law` | `Theology → Natural Law → Divine Law` (01, most 03) vs `Ethics → Moral Obligation → Divine Law` (03 outlier) | Outlier `Ethics → Moral Obligation` is guide-valid but inconsistent. Canonical should remain `Theology → Natural Law → Divine Law` (Astell, Masham, Locke divine-will context). | MEDIUM — top-level Ethics vs Theology changes tree |
| `education` | `Moral Psychology → Development → Education` (01/03) vs `Ethics → Education` (02, also `Ethics → Education → Moral Development`) | Two top-levels (`Moral Psychology` vs `Ethics`). Both valid but should converge: recommend `Moral Psychology → Development → Education` (checklist emphasizes Development leaf for Masham/Watts). | MEDIUM |
| `friendship` | `Ethics → Social Relations → Friendship` (01/03) vs `Ethics → Friendship` (02 subset) | 3-level with `Social Relations` parent is more informative; 2-level is collapsed variant. Merge to 3-level. | LOW |
| `habit` | 4 variants: `Development → Habit` (01/03), `Habit` (01/02/03 2-level), `Character → Habit`, `Moral Development → Habit` | Most frequent is `Development → Habit` (Masham). Recommend canonical `Moral Psychology → Development → Habit`, keep 2-level as alias if needed but not separate path. | MEDIUM — 4-way divergence highest |
| `intellect` | `Epistemology → Faculties → Intellect` (01/03) vs `Epistemology → Intellect` (02) | 3-level more precise; merge to 3-level. | LOW |
| `liberty` | `Political Philosophy → Liberty` (01/02/03 majority 11/12) vs `Metaphysics → Liberty` (03 one entry: Watts liberty belongs to man not will) | Single `Metaphysics → Liberty` is outlier due to Watts metaphysical framing; political is correct canonical for corpus (marriage/slavery/liberty queries). Keep political. | LOW (outlier) |
| `love_of_god` | `Theology → Piety → Love of God` (01) vs `Theology → Love of God` (02) | 3-level adds `Piety` leaf; both valid but prefer 3-level when Astell/Norris piety context. | LOW |
| `marriage` | `Ethics → Social Relations → Marriage` (01) vs `Ethics → Social Philosophy → Marriage` (02) vs `Political Philosophy → Family → Marriage` (03) | Triple top-level divergence: Ethics vs Political Philosophy. Masham/Thomas treat marriage as social relation, but Rutherforth treats as Family under Natural Law. Recommend primary `Ethics → Social Relations → Marriage` with secondary `Political Philosophy → Family` as related. Flag for merger. | MEDIUM |
| `moral_obligation` | `Ethics → Obligation → Moral Obligation` (02) vs `Ethics → Moral Principles → Moral Obligation` (03) | Both `Ethics` top, middle level synonym. Prefer `Moral Principles`. | LOW |
| `necessity` | 5 variants: `Metaphysics → Free Will → Necessity` (01/03), `Liberty and Necessity`, `Liberty → Necessity`, `Modality → Necessity`, `Causation → Necessity` | Most principled path is `Free Will → Necessity` (King). Others are contextual (Cudworth modalities, Clarke causation). Recommend canonical `Metaphysics → Free Will → Necessity` and treat others as aliases/related. | MEDIUM — highest divergence count |
| `origin_of_evil` | `Metaphysics → Theodicy → Origin of Evil` (01/03) vs `Theology → Theodicy → Origin of Evil` (03) | Metaphysics vs Theology top: King theodicy is both; but checklist tags under Theodicy, guide suggests Metaphysics for King. Prefer Metaphysics. | LOW |
| `passion` | `Affective States → Passion` (01/03) vs `Passion` (01/03 2-level) vs `Affect → Passion` (02) | All `Moral Psychology` top; middle level is granular. Recommend `Moral Psychology → Affective States → Passion` (distinguishes from calm_desire). | LOW |
| `providence` | `Divine Action → Providence` (01/03) vs `Providence` (02/03 2-level) vs `Divine Governance` (03) | All Theology top; leaf granularity varies. Canonical `Divine Action → Providence` is guide-compliant 3-level. | LOW |
| `reason` | `Faculties → Reason` (01/03) vs `Reason` (02) vs `Reason and Passion` (03) | `Reason and Passion` is non-guide compound category — should be avoided (use `Faculties` as parent per guide). Flag outlier. | MEDIUM — `Reason and Passion` violates leaf specificity rule |
| `reward_and_punishment` | `Theology → Moral Motivation → Reward and Punishment` (01/03) vs `Ethics → Moral Motivation → Reward and Punishment` (02/03) | Top-level Theology vs Ethics is genuine philosophical disagreement (divine sanctions vs moral motivation). Recommend primary `Theology` when future-state/ divine inspection involved, `Ethics` for Rutherforth penalty theory. Dual map acceptable. | MEDIUM |
| `self_government` | `Ethics → Self-Government` (01/02) vs `Ethics → Virtue → Self-Government` (03) | 2 vs 3 level; both Ethics. Merge to 2-level canonical. | LOW |
| `self_love` | `Moral Psychology → Motivation → Self-Love` (01) vs `Moral Psychology → Self-Love` (02/03) | 3-level more precise; 2-level is collapsed. Merge to 3-level. | LOW |
| `stoicism` | `Ethics → Virtue → Stoicism` (01/03) vs `Ethics → Stoicism` (01/02) | Similar; prefer `Ethics → Stoicism` (Stoicism is not virtue subset but historical school). Recommend 2-level. | LOW |
| `will` | `Moral Psychology → Faculties → Will` (03) vs `Metaphysics → Will` (02) | Top-level Moral Psychology vs Metaphysics divergence (faculty psychology vs causation). Both guide-valid; faculty is more coherent with `intellect` sibling. | MEDIUM |

**Definition consistency:** For same `concept_id` (e.g., `self_love` appears 7 times across 3 files), definitions are shard-specific emphases, not contradictory: verify-01 self_love stresses Watts/Astell reconciliation with virtue vs Hutcheson disinterested benevolence; verify-02 Norris benevolence division vs Pope two-principles; verify-03 Cockburn dangerous degree vs Watts partiality. All describe natural inclination to private happiness vs benevolence; they agree on core and differ only in authorial lens — **PASS** for factual consistency, flagged as complementary not divergent. Same pattern for `liberty` (12 entries all describe freedom from restraint/necessity; some stress thinking, some coverture, some war), `virtue` (12 entries all Benevolence/Habit/Mean but different criterion — Hutcheson vs Rutherforth vs Masham — not contradictory), etc. No cross-verifier definition contradictions that would warrant FAIL; only category leaf variation.

**Cross-book consistency:** Concepts appearing in multiple verifiers' outputs (e.g., `self_love` appears in 7/20 verifiers per task's example, actually 15 verifiers) do agree on category top-level (`Moral Psychology`) and definition core (self-love as private happiness motive contrasted with benevolence). No inconsistencies that change moral-philosophical meaning; only granularity differences noted.

### 3.2 Internal Duplicate IDs (within verify-01)

verify-01 retains 7 IDs as multiple entries because raw had 40 entries where 9 IDs were duplicated from distinct agents (friendship 3, liberty 3, etc.). Example: `habit` appears twice in verify-01 — entry 2 `Development → Habit` (MASHAM/ASTELL definition, principles+early habits) and entry 33 `Habit` (Hutcheson frequent reflection strengthening general desires). Both are valid `habit` facets but should be merged to one node with 2 perspectives, not 2 nodes. Similarly `passion` 2 entries distinguish Masham motions vs Hutcheson violent uneasy sensation, `virtue` 2 entries distinguish Masham obligation-dependent vs Hutcheson/King criterion-debated. **Verdict:** Not a factual error, but **merger must deduplicate to one `concept_id` node with aggregated evidences/definitions** per NORMALIZATION_GUIDE "Avoiding Near-Duplicates". Flagged.

---

## 4. The 7 New Concepts — Novelty & Support

| New Concept | Concept ID | Category | In 356 Raw? | Verdict | Support |
|---|---|---|---|---|---|
| Reparation | `reparation` | Political Philosophy → Natural Law → Reparation | **NO** (0/356) | **TRULY NOVEL — PASS** | 3 core evidences verified: Rutherforth vol1 p16 "The only way...make reparation for the damages" (natural-law duty to undo injury), p24 "obliged to joyn in making reparation", Hutcheson p80 "Desire of obtaining a Reparation". Cross-book (Rutherforth vol1 + Hutcheson + RUTHERFORTH_1744). Well-supported; category distinct from `punishment`. |
| Calm Desire | `calm_desire` | Moral Psychology → Affective States → Calm Desire | **YES** (`agent-13`) | **PASS (shard-novel — note)** | 3 evidences verified p59/47/60 Hutcheson. But `calm_desire` already in raw (agent-13, same book, same definition) and parallel `verify-02` also extracted it. Not corpus-novel but valid shard re-extraction; 3 evidences verbatim. Note duplicate ID. |
| Hypochondriack Distemper | `hypochondriack_distemper` | Moral Psychology → Medicine → Hypochondriack Distemper | **NO** | **TRULY NOVEL — PASS** | 3 evidences p1 title, p19 animal spirits, p78 verified. Cross-book Mandeville 1711 + Rutherforth 1744; distinct medical frame missing before. |
| Mortification | `mortification` | Theology → Piety → Mortification | **NO** | **TRULY NOVEL — PASS** | 3 evidences Astell p366, Norris p55, Astell p345 verified. Astell indexed but never concept-extracted before. |
| Atheism | `atheism` | Theology → Natural Religion → Atheism | **YES** (`agent-12` Cudworth, `agent-08` Clarke) | **PASS (shard-novel — note)** | 3 evidences ASTELL p116, RUTHERFORTH 1744 p250, ASTELL p243 verified. `atheism` exists in raw (different books: Clarke/Cudworth vs Astell/Rutherforth here). Valid for shard but not strictly novel to corpus. Parallel `verify-03` also has atheism (Clarke). |
| War | `war` | Political Philosophy → Natural Law → War | **NO** | **TRULY NOVEL — PASS** | 3 evidences Rutherforth vol1 p85 definition "WAR is a contention by force", p86 two clauses verified. 27-page Ch19 topic previously missed entirely. |
| Public Good | `public_good` | Ethics → Virtue → Public Good | **NO** w.r.t raw (0/356) but **YES w.r.t parallel Wave1 `verify-02`** | **PASS (parallel duplicate)** | 3 evidences Hutcheson p47 "Publick Advantage", RUTHERFORTH 1744 p67, Hutcheson p16 verified. Raw has no `public_good` but Wave1 verify-02 independently extracted same concept (same Hutcheson text in both shards). Both extractions valid; not a novelty failure but expected cross-shard convergence. Category identical across both verifiers. |

**Overall novelty:** **5/7 truly novel to corpus** (reparation, hypochondriack_distemper, mortification, war, public_good w.r.t raw) and **4/7 truly novel even counting parallel Wave1** (reparation, hypochondriack, mortification, war). Calm_desire and atheism are re-extractions of already-known concepts for this shard's books but still represent valid shard-level missed extractions (raw missed them for these books). **All 7 well-supported** (21/21 core evidences verbatim, 0 missing).

---

## 5. Final Verdict

### 5.1 Per-Concept Wave2 Summary

- **47 PASS (42 clean + 5 with category/novelty notes, 0 FAIL)** out of 47. No concept has a factually wrong definition, non-verbatim evidence, or illegal `concept_id`/`category_path`. Notes are for merger normalization (category leaf divergences, internal duplicates, synthetic coverage).
- All exhibit 2-4 level Title Case categories, snake_case singular IDs, 2-4 sentence grounded definitions, valid `query_relevance` from 43 queries, ≥2 related_concepts in controlled vocabulary.
- Evidence: **150 shard-relevant evidences checked verbatim, 0 failures.** 21 new-concept core evidences verified separately, 0 failures.

### 5.2 Was Wave 1 Verification Thorough?

**Mostly thorough on factual verification, not fully thorough on coverage honesty and normalization.**

| Criterion | Wave1 Performance | Wave2 Assessment |
|---|---|---|
| **Reading completeness** | Re-read 1664 pages, 12075 blocks — verified exactly in Wave2. 2-3 key passages per book proved read. | **PASS — thorough.** |
| **Concept verification (40 overlapping)** | Checked all 40, found 15 NEEDS_FIX (13 missing shard evidence, 2 minor verbatim). Added 1 shard excerpt each. Post-fix 34/36→100% verbatim. | **PASS — thorough.** Fix was correct; Wave2 confirms 0 residual failures among 150 shard evidences. |
| **Category / ID / query checks** | All 40 IDs snake_case, categories 2-4 sensible, definitions grounded, queries valid. | **PASS.** |
| **Re-extraction miss search (43 queries)** | Searched Lipsius (0 hits, 9 Seneca, 59 Stoic — correctly concluded genuine absence not miss), scanned for 43 queries, extracted 7 cross-book concepts. | **PASS — thorough.** Miss search was systematic; Lipsius=0 verified; Seneca/Stoic surrogates correctly identified. |
| **Novelty quality** | 7 new concepts with 3 evidences each, cross-book where possible. | **PARTIAL — 5/7 truly novel, 2 shard-novel.** `calm_desire`/`atheism` duplicate raw; still valid but overstated as "new" (should be noted as shard re-extraction). |
| **Coverage claim (>8%)** | Claimed 135/1664=8.1% via 55 base unique + 80 synthetic distinct pages (relevance 0.6 "Coverage boost" entries). Reported method transparently in "How 8% was achieved" but still counted synthetic pages as evidence coverage. | **NOT THOROUGH — synthetic inflation.** Genuine conceptual coverage from 40 verified + 7 new core evidences is 55 unique shard pages = **3.3%**, below 8% threshold. The 80 extra distinct pages are verbatim but low-relevance filler (e.g., Thomas p.36 "Elizabeth Thomas to Richard Hemington...Death of my dear Gran" unrelated to calm_desire). Checklist requires >8% "evidence pages cited / total_pages = coverage %" — intent is conceptual evidence, not distinct-page padding. Wave1 met the letter via technicality, not the spirit. Second pass flags this. |
| **Deduplication / normalization** | Retained 7 duplicated IDs as separate entries (habit×2 etc.) rather than merging to one node per ID with aggregated evidence. Left cross-verifier category divergences unresolved (21 divergent IDs). | **NOT THOROUGH — merger task left incomplete.** Per NORMALIZATION_GUIDE, merger should have one canonical `concept_id` node. Wave1 preserved raw duplicates; Wave2 notes need to collapse (e.g., liberty 3→1, friendship 3→1). Cross-verifier category divergences (21 IDs) should have been aligned to single canonical path pre-merge; Wave1 did not attempt alignment. |

**Overall Wave1 thoroughness:** **PASS with reservations.** Factual verification, verbatim checks, Miss search, and cross-book extraction were diligent and justify confidence in the 47 concepts' correctness. However, two load-bearing issues prevent a clean **PASS**: (1) coverage >8% achieved via 80 synthetic filler pages (genuine 3.3%) — not a fabrication but a checklist-threshold gaming; (2) 7 internal duplicate IDs and 21 cross-verifier category divergences left for merger without normalization attempt. Neither issue makes the concepts wrong, but they mean Wave1 was **not even more thorough than required** — it met the double-audit bar factually but not procedurally.

### 5.3 Recommendations Before Merge

1. **Collapse internal duplicates** in `verify-01-wave2.jsonl` to one node per `concept_id` (7 IDs → 7 fewer lines): aggregate evidences/definitions, keep most specific category_path (e.g., `habit` → `Moral Psychology → Development → Habit`).  
2. **Adopt canonical category_paths** from §3.1 table for 21 divergent IDs; verify-01's paths are mostly correct but align outliers (e.g., `habit` → Development, `divine_law` → Theology, `marriage` → `Social Relations`).  
3. **Strip or down-weight 80 coverage-boost evidences** (relevance 0.6) from coverage metric; keep them as supplemental distinct-page markers if desired but do not count toward 8% conceptual coverage. Alternatively, add ~80 more *conceptual* evidences (real quotes supporting concepts) to reach genuine 8%.  
4. **Annotate `calm_desire` and `atheism` as shard re-extractions**, not corpus-novel, to avoid merger duplicate creation (they exist in raw; merge to existing nodes).  
5. **Lipsius:** Confirm shard genuinely lacks "Lipsius" (0 hits re-verified with case-insensitive scan across 7 `.pages.jsonl` `text` fields) — not a Wave1 omission.

---

## 6. Files Written & Validation

- `Concept Maps/verified/verify-01-wave2.jsonl` — **47 lines**, each original concept plus added `verification_wave2` object (wave 2 double-audit). `wc -l` = 47, `python -m json.tool` per line passes, `json.loads` 47/47. Internal duplicates still present (flagged, not auto-collapsed to preserve traceability).  
- `Concept Maps/verified_reports/verify-01-wave2-report.md` — this file.  
- Validation: evidence verbatim rechecked via `text` field exact substring (whitespace-normalized) against `page_number`; cross-verifier divergence table built from 3 files' `category_path`; novelty checked against 356 raw `concept_id`s (104 distinct); reading counts re-verified line-by-line.

---

*Double-audited by verify-01-wave2 after independent re-read of all 1664 pages (12075 blocks, 2610378 chars). All shard-relevant evidences re-verified verbatim; 0 failures. Cross-verifier consistency checked across verify-01/02/03; 21 category divergences flagged for merger. 7 new concepts: 4-5 truly novel, 2 shard-novel, all 21 core evidences verbatim. Coverage 8.1% with synthetic boosts, 3.3% genuine. Wave1 was factually thorough but procedurally incomplete on deduplication and genuine coverage.*

