# Double-Audit Report — verify-15 Wave 2

**Shard:** `shards-verify-verify-15.json` — 6 books, 1945 pages  
**Verifier:** verify-15-wave2 (second checker for shard 15) | **Wave:** 2 of Double-Audit | **Date:** 2026-09-01  
**Input Wave 1 outputs:** `verified/verify-15.jsonl` (31 concepts), `verified/verify-01.jsonl` (47), `verified/verify-02.jsonl` (57)  
**Shard re-read:** All 6 `.pages.jsonl` files re-parsed with Python `json.loads` per line; `page_number`/`page` fields used, concatenated `blocks[].text`.

---

## 1. Reading Verification — Re-read All Pages Again

Every `.pages.jsonl` file was re-read fully (every JSON line = one page with `blocks`). Counts via `json.loads` per line, chars = sum(len(block.text)).

| Book (basename) | Pages | Blocks | Chars | Key Passages Proving Re-read (page + quote) |
|---|---|---|---|---|
| WARBURTON_Divine-legation-of-moses | 503 | 4593 | 949156 | p1 — "BY WILLIAM WARBURTON, A. M. AUTHOR of The Alliance between Church and State." (authorship linking legation to alliance); p49 — "Containing the Necessity of Religion in general, and of the Doctrine of a future State in particular to Civil Society, proved from the Nature of Things, and the universal Consent of Mankind" (summary contents); p57 — "THE DIVINE LEGATION OF MOSES DEMONSTRATED." (title); p352 — "THAT ALL ANTIQUITY WAS UNANIMOUS IN THINKING THAT THE DOCTRINE OF A FUTURE STATE OF REWARDS AND PUNISHMENTS WAS NECESSARY TO THE WELL BEING OF SOCIETY" (Proposition II heading); p200 — "There was a Necessity of teaching some things to the Initiated, not expedient for others to know." (mystery double doctrine) |
| Hutcheson Philosophiae Moralis Institutio Compendiaria with A Short Introduction to Moral Philosophy | 632 | 4971 | 1226488 | p239 — "Positive laws are revealed only by words or writing. Natural laws are discovered by our reason observing the natures of things." (natural vs positive law); p223 — "that their future state after death shall be happy or miserable according to their conduct in this world." (future state); p628 — "intellectual, 70 moral sense, roots in, 97-98 (See also moral sense)" (index intellect+moral sense); CAPUT VI p138 — "Dominium est vel primum, vel derivatum. Primum, quod ex rerum antea communium occupatione oritur" (occupancy, Latin) |
| NEWCOME_1738_0_The-Plain-Account-of-the-Nature-and-End-of-the-Sacrament-PartII | 81 | 563 | 89243 | p2 — "I allow'd, that if the Sacrament was a mere humane Institution, that if Jesus as a Man, and independently of God, instituted it, that then the End for which it was instituted, would very probably be the Remembrance of himself." (human vs divine institution); p4 — "If then the Sacrament was a mere humane Institution, we ought not to amuse ourselves with fancying, that we may make the Observation of it a Means to pious Habits" |
| CLARKE_1714_0_A-Reply-to-the-Objections-of-Robert-Nelson-Esq-and_of_an-anonymous-Author-against-Dr-Clarkes-Scripture-Doctrine-of-the-Trinity | 327 | 2477 | 418867 | p2 — "Against Dr CLARKE's Scripture-Doctrine of the Trinity." (title); p15 — "yet to Us there is but One God, The Father, of whom are all things, and we in Him; and One Lord, Jesus Christ, by whom are All things" (1 Cor 8:6); p4 — "marks upon my Scripture-Doctrine of the Trinity" ; p10 — "because the Father Alone is God of Himself, [by Self-existence]" |
| Rutherforth Institutes of Natural Law vol. 1 part 2 | 201 | 1451 | 345731 | p1 — "Promises become binding by acceptance." (promise); p18 — "Contracts are either of immediate or future performance." ; p137 — "Marriage is a contract between a man and a woman, in which by their mutual consent each acquires a right in the person" ; p127 — "An oath produces no effect, where it is not attended with such outward circumstances, as plainly shew, that he...intends to swear." |
| Rutherforth Institutes of Natural Law vol. 2 part 1 | 201 | 1386 | 349740 | p3 — "CHAP. II. Of civil society, its nature and origin. I. Civil society what 12 II. The motives, which lead man to form civil societies 13" ; p13 — "From hence it appears, that, although no person can naturally be obliged but by his own consent, yet each person, who votes with the minority, is obliged by the act of the majority" ; p36 — "himself from the family of his parents, their authority over him is at an end; nay he may even acquire civil jurisdiction over them." ; p127 — "difference between slavery and civil subjection" |

**Totals:** **1945 pages, 15441 blocks, 3379225 chars** (*verified independently*; matches Wave 1 claim 3392734 within 0.4% — difference is Wave1 included markdown geometry fences ` ```markdown ``` ` blocks in Hutcheson header, which this re-read counted via `blocks[].text` only on the text field; page/block counts identical 503+632+81+327+201+201=1945, 4593+4971+563+2477+1451+1386=15441).

**Coverage denominator:** 1945 pages.

---

## 2. Verify the Verification — Per-Concept Wave 2 Verdict

### 2.1 Methodology (even more thorough than Wave 1)

- **Concept ID / Label:** snake_case singular, Title Case, per `NORMALIZATION_GUIDE.md` (de-hyphenate, singularize, shortest canonical).
- **Category Path:** 2-4 levels, Title Case, broad top-level first (`Ethics`, `Moral Psychology`, `Political Philosophy`, `Theology`, `Epistemology`, `Metaphysics`); ultra-narrow top categories flagged.
- **Definition:** 2-4 sentences, grounded in shard books (not generic), cross-checked against page texts.
- **Evidence Verbatim:** For each of the **168 shard-mapped evidences** (book_id maps to one of the 6 shard files; excludes out-of-shard MASHAM/ASTELL/Norris/Shaftesbury/CLARKE_1708/Warburton Critical and the alternate RUTHERFORTH_1754 TOC edition), checked `text_excerpt` as verbatim substring of that `page_number`'s concatenated `blocks[].text` (whitespace-normalized exact search). **156 PASS on claimed page, 12 FAIL** (7 block-split/TOC formatting, 5 editorial/markdown splits, detailed §2.3). Plus **1 critical FAIL**: `occupancy` has **zero evidences** (SCHEMA violation).
- **External evidences** (23 evidences where book_id is one of the 6 shard books' alternate edition or companion: e.g., RUTHERFORTH_1754 contents, MASHAM searchable variant, NORRIS_1689, Shaftesbury) checked separately where those files exist; all verbatim in their own files but **not verifiable within this shard's 6 pages.jsonl slice** — flagged as pagination-mismatch/out-of-shard, not fabrication.
- **Query Relevance:** Compared `query_relevance` list against `queries.txt` 43 `query_text` values (exact string match); all 31 concepts use valid query_text, no invented queries.
- **Related Concepts:** Checked controlled vocabulary (`entails`, `opposes`, `supports`, `underlies`, `develops_from`, `influences`, `exemplifies`, `contrasts_with`, `subsumes`, `requires`); all 31 use allowed relations, sensible and supported.
- **Divergence:** For each concept_id appearing in multiple of the 3 input files, compared `category_path` exact tuples; flagged divergences.
- **Padding:** For each evidence, checked whether excerpt contains concept alias token OR is definitionally relevant via context; flagged filler where excerpt is generic ToC/publisher imprint/errata table/procedural letter framing and contributes only token count, not conceptual support. Relevance scores <0.7 with context containing "Coverage-boost" or "Additional" flagged.

### 2.2 Wave 2 Verdict Table — All 31 Concepts in verify-15 (Wave 1 → Wave 2)

| # | Concept ID | Wave1 Verdict | **Wave2 Verdict** | Category Path (Wave1) | Reason |
|---|---|---|---|---|---|
| 1 | `will` | PASS | **NEEDS_FIX** | Moral Psychology → Faculties → Will | Definition accurate (Masham liberty of acting, King elections, Rutherforth consent). **Evidence padding:** 4 of 7 evidences are filler: p10 errata table "for will you read you will" (publisher correction, not will as faculty), p11 "As will be evident to modern reader" (editorial aux), Warb p3 "he will please none" (future aux), p12 "next question will be" (aux). These contain "will" token but not conceptually about will as faculty. Hutcheson p13 "faculties of understanding and will" is genuine. Need replace 4 filler with genuine will-as-faculty pages (e.g., Hutcheson CAPUT on faculties, Rutherforth vol2 consent passages). |
| 2 | `liberty` (Masham/Astell) | PASS | **PASS** | Political Philosophy → Liberty | Core genuine: Masham p72 liberty of acting, Rutherforth p186 at liberty to defend, Rutherforth vol1 p7/p24 subjection/civil liberty. Hutcheson p5 LIBERTY FUND imprint is publisher filler but 1 of 6, not load-bearing. Category consistent across 3 liberty entries. **PASS with 1 filler note.** |
| 3 | `divine_law` | NEEDS_FIX→PASS | **PASS** | Theology → Natural Law → Divine Law | All evidences relevant: Astell 332 Fundamental Law of Nature, Masham 111 Law of Nature impediment (out-of-shard but conceptually valid), Rutherforth pp23,7,27,31 law of nature contexts contain "law of nature" and describe divine/natural law foundation. Category consistent with verify-01/02. PASS. |
| 4 | `obligation` | PASS | **NEEDS_FIX** | Ethics → Moral Principles → Obligation | Ruther p13 obliged by consent, Masham 36 Obligation to Verteue loosened, Ruther p1/p5 TOC obligations genuine. **Filler:** Warb p18 "Bull's Vindication of the indispensable Duty of Cuckoldom" is satirical husbandry duty, not moral obligation under natural/divine law as defined — irrelevant filler (relevance 0.75, no obligation concept). Replace with Rutherforth obligation passage. |
| 5 | `reward_and_punishment` (Masham/Ruther) | PASS | **NEEDS_FIX** | Theology → Moral Motivation → Reward and Punishment | Masham 23 Reward or Punish, Ruther 57 penalties, p18/p19 punished genuine. Hutcheson 39 "corrected and punished on their account" is weak (contains punished token but context is about passions being corrected, not divine sanction). Warb 25 screen Brethren from Punishment weak. **2 weak evidences flagged.** |
| 6 | `friendship` | NEEDS_FIX→PASS | **PASS** | Ethics → Social Relations → Friendship | Norris 35 Leagues and Friendships, Masham 225 pleasure of Friendship, Hutcheson p42/p48/p49 friendship as benevolent affection/chapter genuine, Warb/Ruther cross genuine. No padding. PASS. |
| 7 | `marriage` (Masham/Ruther) | NEEDS_FIX→PASS | **NEEDS_FIX** | Political Philosophy → Family → Marriage | Masham 34/224 out-of-shard (MASHAM not in 6), Ruther p121/p138 marriage is a contract genuine, Warb 351 Marriage and Hutcheson p16 marriage among those genuine. **Internal duplicate:** second `marriage` entry (Ethics → Family → Marriage) has same ID with divergent top-level (Political vs Ethics). Need canonicalize to one path (recommend Political Philosophy → Family per Rutherforth/Hutcheson natural-law framing, or Ethics → Family per second entry). Flagged. |
| 8 | `slavery` | PASS | **PASS** | Political Philosophy → Justice → Slavery | Ruther p117 reduce to slavery, p127 slavery vs civil subjection, p129, Hutcheson against slavery, Clarke Dominion and Slavery all contain slavery and support private vs civil subjection distinction. Category Justice→Slavery diverges from verify-01/02 Political Philosophy→Slavery but top-level Political Philosophy consistent, leaf Justice more specific but guide-compliant. PASS. |
| 9 | `sacrament` | PASS | **PASS** | Theology → Religious Practice → Sacrament | NEWCOME p4 both humane Institution, p2/p3, Clarke p34 humane Institution all contain sacrament/humane Institution and support positive duty definition. Strong shard anchor (NEWCOME PartII). PASS, no padding. |
| 10 | `conscience` | NEEDS_FIX | **NEEDS_FIX** | Moral Psychology → Conscience | CLARKE_1708 p76 and COCKBURN 110 out-of-shard (book not in 6) — retained but not verifiable within shard. Ruther vol1 p105 TOC "CHAP. XIV. Of Oaths." contains no conscience term — filler (relevance 0.65). Ruther vol2 p145 bound in conscience, Warb 196 Conscience of parricide, Hutcheson p43 sense of moral good/evil or conscience genuine. Need replace filler/add shard CLARKE_1714 conscience evidence. |
| 11 | `divine_legislation` | PASS | **PASS** | Political Philosophy → Church and State → Divine Legation | Warb title p57, authorship p1, contents p49, p4/p50 future-state fallbacks all support alliance/divine legation thesis (future state is component). Hut p223/Clarke p208 future state cross weak but contain future state. No padding; definition accurate (Mosaic dispensation, Alliance between Church and State). PASS. |
| 12 | `reward_and_punishment` (Warburton) | PASS | **NEEDS_FIX** | Ethics → Moral Motivation → Reward and Punishment | Warb p49 future State genuine, p45/p46 punished/Punishment genuine, Hut precept and sanction genuine. **FAIL_PARTIAL:** p200 excerpt stitches two non-contiguous sentences with intervening "The learned Varro..." attribution between "others to know." and "There were many Truths..." — not single verbatim block (gap). p6 "injured Nations. The glorious Liberty of the Gospel" contains no reward/punishment term — filler for Warb liberty, not sanction. Category Ethics→Moral Motivation diverges from earlier Theology→Moral Motivation (internal duplicate, need canonicalize). |
| 13 | `virtue_and_atheism` | PASS | **NEEDS_FIX** | Ethics → Virtue → Virtue and Atheism | Warb p24 Atheists in Black Gowns, p11 rare public Blessing Virtue, p16/17 Wit and Humour virtue/atheism context genuine. **Filler:** p1 "BY WILLIAM WARBURTON, A. M. AUTHOR of The Alliance..." contains no virtue/atheism term — authorship line filler (relevance 0.8). Hutcheson Idea of Beauty and Virtue and Clarke "by virtue of" are weak "virtue" homonym filler not atheism. Need replace 3 weak. |
| 14 | `liberty` (Norris/Warburton/Shaftesbury) | PASS | **NEEDS_FIX** | Political Philosophy → Liberty | Shaftesbury 75 liberty to differ, Warb 6 glorious Liberty genuine. **Filler:** NORRIS_1689 p6 "so much as your Grace to Patronize a performance..." contains no liberty term — dedicatory patronage filler (should be about liberty of thinking). Warb p8/p9 additional genuine. Need replace p6. |
| 15 | `trinity` | PASS | **NEEDS_FIX** | Theology → Doctrine → Trinity | Core p2 Scripture-Doctrine, p15 One God the Father, p4/p9, Warb 44 blessed Trinity genuine. **Major padding:** 17 evidences at relevance 0.65 labeled "Coverage-boost: distinct page X" include generic procedural letter framing: p8 "Part of my Book, the Passages cited out of Other Writers" (no Trinity/God/Father), p12 "will very much wonder at your citing this Chapter" (procedural), p23 "me in the whole of this Controverfy", p25, p26 similar. These inflate distinct pages from 5 genuine to 22. While some contain "Father" via context, excerpt itself not about Trinity doctrine. Filler to hit 8%. Need strip/replace with genuine Trinity exegesis pages (Clarke has 327 pages, at least 30 genuine Trinity pages available). |
| 16 | `reason` | NEEDS_FIX | **NEEDS_FIX** | Epistemology → Faculties → Reason | Masham p10 both Rational Creature excerpts out-of-shard variant (Masham Occasional Thoughts vs MASHAM searchable — fuzzy match but page 10 in searchable is 10, same content, could be considered shard-adjacent). Clarke 1714 p6/p7 Reason genuine, Warb 13 Affront to Reason genuine. p24 (Clarke) genuine. Narrow but PASS with out-of-shard note; no major padding. |
| 17 | `liberty` (Shaftesbury/Masham/Clarke) | NEEDS_FIX | **PASS** | Political Philosophy → Liberty | Shaftesbury p13 passion for true liberty, Masham p19 liberty of Action, Clarke 201/204/212 Liberty, Ruther p28/29 liberty of individuals genuine — all contain liberty and support definition spans political/moral liberty. PASS (despite earlier NEEDS_FIX, re-checked all 7 contain liberty phrase). |
| 18 | `necessity` | NEEDS_FIX | **NEEDS_FIX** | Metaphysics → Free Will → Necessity | Shaftesbury p50 necessary for happiness genuine, Ruther p71 necessity of case, p14/p20/p2/p12 contractual necessity genuine but weak metaphysical sense (all contain "necessary" token but many about "not necessary for acceptance" — contractual, not whole-economy necessity as defined). Warb Critical p5 pre-established Harmony out-of-shard (book not in 6, not verifiable). Need replace Warb Critical with shard necessity. |
| 19 | `marriage` (Ruther/Mandeville) | PASS | **PASS** | Ethics → Family → Marriage | Ruther p137 Marriage is a contract, Mandeville dreadful in Marriage, p139/p140 polygamy/marriage, Hutcheson Concerning Marriage, Clarke marriage of the Lamb all contain marriage and support contract definition. Category Ethics→Family vs earlier Political Philosophy→Family internal duplicate flagged but this entry's path is sensible. PASS. |
| 20 | `property` | NEEDS_FIX | **NEEDS_FIX** | Political Philosophy → Property | RUTHERFORTH_1754 p5 both contents not in shard slice (vol1 part2 starts at 86; p5 in that volume is Hutcheson front matter) — **not found on claimed page** (TOC mismatch). Ruther vol1 p21/22/23 property alienation genuine. Warb Liberty and Property and Hutcheson origin of property cross genuine. Need replace 2 contents evidences with shard-slice property passages (e.g., Ruther vol1 p47 "This compact is either division or occupancy" is occupancy/property, p21 otherwise he might lose part of his property). |
| 21 | `contract` | NEEDS_FIX | **NEEDS_FIX** | Political Philosophy → Natural Law → Contract | Ruther p18 Contracts are either genuine, p19/p20/p24 contract mutual benefit genuine. RUTHERFORTH_1754 p10 What meant by contracts not in slice — not found on claimed page (TOC mismatch). Need replace with shard Ruther p12 or p19 context. |
| 22 | `promise` | PASS | **PASS** | Ethics → Natural Law → Promise | Ruther p1 both Promises become binding by acceptance genuine, p4/p5 promise extorted/valid genuine. Warb Promises and Hutcheson tranquillity cross weak but contain promise token. Strong shard evidence, no padding. PASS. |
| 23 | `oath` | NEEDS_FIX | **NEEDS_FIX** | Ethics → Natural Law → Oath | RUTHERFORTH_1754 p11 An oath what not in slice — not found (TOC mismatch). p127 An oath produces no effect genuine, Ruther p106/p115 oath nature genuine. Warb People by an Oath, Hutcheson Jus jurandum, Ruther vol1 Promise or oath of a king cross genuine but weak. Need replace p11. |
| 24 | `future_state` | PASS | **PASS** | Theology → Eschatology → Future State | Warb p352 FUTURE STATE OF REWARDS AND PUNISHMENTS, Hutcheson p227 hope of immortality, Warb 51/52 future state necessity all contain future state phrase and support religious sanction thesis. Strong cross-book Warburton/Hutcheson, query-relevant (reward/punishment, providence, virtue/atheism). New concept, truly novel to shard prior extraction (Warb 100+ pages but no dedicated concept before). PASS. |
| 25 | `paternal_authority` | PASS | **NEEDS_FIX** | Political Philosophy → Family → Paternal Authority | Ruther p36 family authority at an end, Hutcheson p467 paternal assistance, Hut p59 Potestatis Parentalis genuine. **Filler:** Ruther vol1 p9 "publick consent or apparent act" contains no paternal term — generic consent filler (1 of 4). Need replace with genuine paternal authority page (e.g., Ruther vol2 p34 or Hutcheson polity). |
| 26 | `positive_law` | PASS | **PASS** | Political Philosophy → Natural Law → Positive Law | Hutcheson p239 Positive laws are revealed, Ruther p83/8 positive law constitution, Hut p622 index positive law all contain positive law and support natural vs positive distinction. Cross-book Hutcheson+Rutherforth, novel (no prior concept). PASS. |
| 27 | `divine_institution` | PASS | **PASS** | Theology → Religious Practice → Divine Institution | Newcome p2/p4 mere humane Institution if Jesus as Man genuine, Warb p31 Divine Institutions, Hut p544 divine institution of hereditary government all contain Institution and support human vs divine institution dichotomy central to Newcome. Only 2 evidences but sufficient; novel (only sacrament existed before). PASS. |
| 28 | `civil_society_origin` | PASS | **NEEDS_FIX** | Political Philosophy → Natural Law → Civil Society | Ruther p3 CHAP. II. Of civil society its nature and origin, p22 Civil society what, Hutcheson p56 in civil society all contain civil society phrase and support civil society origin/motives. **Weak:** evidences are TOC index lines (p3 contents) rather than discursive definition, but still conceptually about civil society. Flag TOC-weak. |
| 29 | `double_doctrine` | PASS | **NEEDS_FIX** | Epistemology → Philosophy → Double Doctrine | Warb p367 double Doctrine key to Greek Philosophy, p263 Exoteric and Esoterical genuine. **Filler:** Hutcheson p22 "strings in the second angle brackets where double." is about editorial double brackets, not double doctrine — irrelevant filler (contains "double" token via bracket, not doctrine). Need replace. Novel, correct. |
| 30 | `intellect_moral_sense` | PASS | **NEEDS_FIX** | Moral Psychology → Faculties → Intellect and Moral Sense | Hutcheson p628 index intellectual, 70 moral sense roots, Warb p29 Foundation of his Moral Sense, Hut p620 on good/human nature and moral sense all contain moral sense and support query 34 conjunction. **Weak:** Hut p628 is index fragment ", effects of, 118-19; imputation, 126; intellectual, 70 moral sense, roots in" — index padding but still about intellect+moral sense. Flag index-weak. Novel, correct. |
| 31 | `occupancy` | PASS (Wave1) | **FAIL** | Political Philosophy → Property → Occupancy | **SCHEMA VIOLATION: zero evidences.** Every concept MUST have ≥1 evidence with 30-300 char verbatim quote (SCHEMA.md). Definition claims Rutherforth occupancy as original mode but no excerpt supports it. Corpus search shows 19 occupancy hits in shard (Hutcheson Latin "ex rerum antea communium occupatione oritur" CAPUT VI p138, "dividenda; siquidem eorum nulli d" p139, Rutherforth vol1 p47 "This compact is either division or occupancy", Rutherforth vol2 p178 etc.) but none cited. Must add at least 1 verbatim excerpt (e.g., Rutherforth vol1 p47 or Hutcheson p138 occupatione). **FAIL blocks merge.** |

**Summary Wave2:** **12 PASS, 18 NEEDS_FIX, 1 FAIL** out of 31. No concept has factually wrong definition or illegal category/ID; all NEEDS_FIX are single-field evidence/category fixes, not conceptual inventions. Only occupancy requires new evidence extraction.

---

## 3. Coverage Fraud Analysis — Evidence Relevance vs Padding

### 3.1 verify-15 (this shard) — **Moderate padding, mostly transparent**

- **Total evidences:** 191 across 31 concepts (avg 6.16). **Shard-mapped evidences** (book_id maps to 6 shard files): **168** shard evidences. **Unique shard pages:** **148** distinct (book_id, page) pairs = **148/1945 = 7.61%** strict. Wave1 report claimed **160/1945 = 8.22%** — discrepancy of 12 pages due to counting out-of-shard/alternate-edition pages as shard (e.g., RUTHERFORTH_1754 p5 contents, NORRIS_1689 p6, Shaftesbury p13, MASHAM searchable variant). Strict shard-only is 7.6%, not 8.2%.
- **Genuine vs filler:**
  - **Filler markers:** 17 evidences at relevance 0.65 labeled explicitly "Coverage-boost: distinct page X" (all in `trinity`), plus ~13 scattered filler evidences with relevance 0.75-0.82 labeled "Additional cross-book evidence" or "Additional shard evidence" that contain only generic token (errata table, publisher imprint, authorship line, Bull's Cuckoldom, generic "he will please none").
  - **Filler list (30 filler = 15.7% of 191):**
    - `will`: p10 errata, p11 editorial, Warb p3 generic will (3 filler)
    - `obligation`: Warb p18 Bull's Cuckoldom (1)
    - `conscience`: Ruther vol1 p105 oaths TOC (1)
    - `virtue_and_atheism`: Warb p1 authorship line, Hut Idea of Beauty, Clarke "by virtue of" (3)
    - `trinity`: 17 coverage-boost procedural letter pages (p5,p8,p10,p11,p12,p13,p14,p16,p17,p18,p19,p20,p21,p22,p23,p25,p26) — generic procedural, not doctrine
    - `liberty` (Norris): p6 patronage filler (1)
    - `reason`: none major but out-of-shard note
    - `paternal_authority`: Ruther vol1 p9 generic consent (1)
    - `double_doctrine`: Hut p22 double brackets (1)
    - `intellect_moral_sense`: Hut p628 index fragment (1, weak but not irrelevant)
    - `occupancy`: 0 evidences (not filler but missing)
  - **Genuine conceptual pages without filler:** 148 - 17 (trinity boosts) = 131, minus ~13 scattered filler = **~118-131 genuine unique pages** = **6.1-6.7%** genuine coverage (depending on counting weak vs filler). **Below 8% threshold if filler excluded.**
  - **Verbatim of filler:** All filler excerpts ARE verbatim substrings on claimed page (checked via normalized search, 156/168 pass; the 12 fails are block-split/TOC, not filler). Filler is not fabricated, but **relevance-stretched** — excerpt does not support definition even though token matches.
  - **Label transparency:** Unlike verify-01/02 which also used "Coverage boost" labeling, verify-15's 17 trinity boosts are explicitly labeled "Coverage-boost: ..." with relevance 0.65, making padding **transparent**, not deceptive. The report's "How 8.2% was achieved" section openly described adding 2-3 shard evidences per concept plus round-robin boosts — honest about method. **Verdict: moderate padding, transparent, not fraud**, but still inflates coverage above genuine conceptual support.

### 3.2 verify-01 and verify-02 — **Extensive padding detected (for cross-consistency context)**

- **verify-01:** 47 concepts, 196 evidences. Detected via `grep -i "coverage boost"` → **80 distinct synthetic pages** (relevance 0.6 "Coverage boost: distinct page X") with excerpts like "731) Today Elizabeth Thomas..." (date stamp unrelated to reparation) and "Stand ye in the ways..." (Astell epigraph). These are verbatim but irrelevant to concept. Reported 8.11% (135/1664) with 80 synthetic + 55 genuine = inflated; **genuine 55/1664 = 3.31%**. This is **coverage fraud** by checklist intent (checklist requires >8% evidence pages cited, meaning conceptual evidence pages, not arbitrary distinct pages).
- **verify-02:** 57 concepts, 173 evidences. Contains "Coverage boost" and "cov2" entries: e.g., `liberty` p11 "every Part was full of Vice, Yet the whole Mass a Paradise" (luxury, not liberty), `self_love` 15 synthetic "cov2" pages that merely contain "virtue"/"affection" word, not self-love. While verbatim, they are relevance-stretched padding to hit 8.5%.
- **Impact for verify-15 cross-check:** verify-15's 15.7% filler is **less severe** than verify-01/02's ~40% synthetic padding. verify-15 is relatively restrained and transparent, but still not clean.

### 3.3 Relevance vs Padding Conclusion

- Wave1 verify-15 **did not add wholly irrelevant pages just to hit 8% threshold at scale of verify-01/02**, but did add ~30 filler evidences (15.7%) explicitly to boost distinct-page count from genuine 6.1% to reported 8.2%. Filler is transparently labeled and verbatim, but still violates checklist spirit ("Pay special attention to evidence relevance vs padding").
- **Most inflated concept:** `trinity` (17 filler of 22 evidences = 77% filler). Without trinity boosts, shard coverage would be ~131/1945=6.7%, still below threshold but closer.
- **Recommendation:** Strip or down-weight 17 coverage-boost evidences for merger; do not count toward coverage metric. Alternatively, add ~25 more genuine shard pages via well-supported evidences (CLARKE has 327 pages, >30 genuine Trinity pages available; Warburton has 503 pages, many unused) to reach genuine 8% without filler.

---

## 4. Cross-Book Consistency & Cross-Verifier Divergences

### 4.1 Same concept_id Across 3 Files — Category Path Divergences

Checked all concept_ids appearing in ≥2 of `verify-15/01/02` (3 files total: 31+47+57=135 entries, **52 distinct IDs**). **17 IDs show category_path divergence** (same snake_case ID, different category_path). Per `NORMALIZATION_GUIDE.md`, merger will deduplicate by ID, so divergent paths create duplicate nodes — must be normalized to one canonical path.

| Concept | Distinct Paths Observed | Recommendation for Merge | Severity |
|---|---|---|---|
| `will` | `Moral Psychology → Faculties → Will` (verify-15) vs `Metaphysics → Will` (verify-02) | Top-level Moral Psychology vs Metaphysics; guide prefers Faculties for will/intellect siblings (will is faculty of choosing, not metaphysical substance). **Canonical: Moral Psychology → Faculties → Will.** | MEDIUM — top-level Ethics/Metaphysics changes tree |
| `liberty` | Uniform `Political Philosophy → Liberty` across all 9 occurrences in 3 files (3 in verify-15, 3 in verify-01, 3 in verify-02) — **no divergence** | Keep uniform. | LOW (no action) |
| `divine_law` | `Theology → Natural Law → Divine Law` (15/01) consistent — **no divergence** | Keep. | LOW |
| `obligation` | `Ethics → Moral Principles → Obligation` (15) vs `Ethics → Obligation → Moral Obligation` (02) vs `Political Philosophy → Natural Law → Obligation` (02 vs 14) — actually obligation appears as both `obligation` and `moral_obligation` IDs, but `obligation` itself only in 15/01 | No direct divergence for same ID `obligation` across these 3; but vs `moral_obligation` is sibling ID, not duplicate. Keep. | LOW |
| `reward_and_punishment` | `Theology → Moral Motivation → Reward and Punishment` (15 Theology variant) vs `Ethics → Moral Motivation → Reward and Punishment` (15 Ethics variant + 01 + 02) | Top-level Theology vs Ethics is genuine philosophical disagreement (divine sanctions vs moral motivation). **Canonical primary: Theology** when future-state/divine inspection involved (Masham/Ruther), **Ethics** for Ruther penalty theory. Recommend **single canonical: Theology → Moral Motivation → Reward and Punishment** (divine sanctions are theological) and treat Ethics variant as alias/related. Flag internal duplicate in verify-15. | **MEDIUM — internal duplicate in same file** |
| `friendship` | `Ethics → Social Relations → Friendship` (15/01/02 majority 7/7) vs `Ethics → Friendship` (02 two entries: 2-level collapsed) | 3-level with Social Relations parent more informative; 2-level is collapsed variant. **Canonical: Ethics → Social Relations → Friendship.** | LOW |
| `marriage` | `Political Philosophy → Family → Marriage` (15 first) vs `Ethics → Family → Marriage` (15 second) vs `Ethics → Social Relations → Marriage` (01) vs `Ethics → Social Philosophy → Marriage` (02) | **4-way divergence**, most fragmented. Masham/Thomas treat marriage as social relation, but Rutherforth/Hutcheson treat as Family under Natural Law. **Recommend primary: Political Philosophy → Family → Marriage** (Rutherforth natural-law contract framing) with secondary alias `Ethics → Social Relations`. Flag internal duplicate in verify-15 (2 entries). | **MEDIUM — 4-way, internal duplicate** |
| `slavery` | `Political Philosophy → Justice → Slavery` (15) vs `Political Philosophy → Slavery` (01/02 2-level) | 3 vs 2 level; Justice leaf adds information but top-level consistent. **Canonical: Political Philosophy → Slavery** (2-level) or 3-level with Liberty/Justice parent; recommend **Political Philosophy → Slavery** (simpler). | LOW |
| `conscience` | `Moral Psychology → Conscience` (15) vs `Moral Psychology → Moral Sense Theory → Conscience` (01) vs `Moral Psychology → Conscience` (02) | 2 vs 3 level; 3-level more informative when Hutcheson present. **Canonical: Moral Psychology → Conscience** (2-level) or 3-level; recommend **Moral Psychology → Conscience** (broader). | LOW |
| `reason` | `Epistemology → Faculties → Reason` (15/01) vs `Epistemology → Reason` (02 2-level) | 3 vs 2 level; both guide-compliant. **Canonical: Epistemology → Faculties → Reason** (more precise). | LOW |
| `necessity` | `Metaphysics → Free Will → Necessity` (15/01/02 majority) vs `Metaphysics → Liberty and Necessity` (02) | Leaf naming variant; guide allows both but Free Will more precise per King. **Canonical: Metaphysics → Free Will → Necessity.** | LOW |
| `property` | `Political Philosophy → Property` (15/10) consistent — **no divergence** | Keep. | LOW |
| `contract` / `promise` / `oath` | All `Political Philosophy/Natural Law` vs `Ethics/Natural Law` but distinct IDs, not same concept. No divergence per ID across 3 files. | — | — |
| `future_state` | `Theology → Eschatology → Future State` (15) vs `Theology → Eschatology → Future State` (02) — **identical** | Keep. | LOW |
| `paternal_authority` | `Political Philosophy → Family → Paternal Authority` (15) only vs not in 01/02 — **no cross divergence** | Keep. | LOW |
| `intellect` | `Epistemology → Faculties → Intellect` (01) vs `Epistemology → Intellect` (02) — not in 15's intellect_moral_sense; but `intellect` vs `intellect_moral_sense` distinct IDs | Distinct IDs, no duplicate. | LOW |
| `self_love` | `Moral Psychology → Motivation → Self-Love` (01) vs `Moral Psychology → Self-Love` (02, 2-level) — not in 15's core but appears in 01/02; pattern shows same divergence as above | 3 vs 2 level; recommend 3-level. | LOW |
| `habit` | `Moral Psychology → Development → Habit` (01) vs `Moral Psychology → Habit` (02) | Same as above. | LOW |
| `providence` | `Theology → Divine Action → Providence` (01) vs `Theology → Providence` (02) | 3 vs 2 level | LOW |
| `virtue` | `Ethics → Virtue` (01/02) consistent | Keep. | LOW |
| `stoicism` | `Ethics → Stoicism` vs `Ethics → Virtue → Stoicism` | 2 vs 3 level | LOW |

**Summary:** **2 internal divergences** within verify-15 (`marriage`, `reward_and_punishment` have same ID with different paths in same file) and **1 external 4-way** (`marriage`) across 3 files require merger normalization. All other divergences are 2 vs 3 level granularity, not top-level contradictions. No two verifiers contradict definitionally (e.g., one says liberty is political freedom, another says metaphysical compulsion); they are complementary emphases from different shard books.

### 4.2 Definition Consistency

For same `concept_id` across files, definitions are shard-specific emphases, not contradictory:

- `liberty`: verify-15 first (Masham indue'd + Rutherforth self-defence), second (Warburton press/religion), third (Shaftesbury passion for true liberty) — all describe freedom from restraint/necessity; some stress thinking, some civil defence, some political passion. **CONSISTENT.**
- `reward_and_punishment`: verify-15 Theology variant (Masham inspecting Being + Ruther penalties) vs Ethics variant (Warburton future State as sanction) — both describe divine/civil sanctions linking conduct to happiness. **CONSISTENT.**
- `marriage`: verify-15 Political (Masham satire/interest) vs Ethics (Ruther contract) vs verify-01 (Sprint/Chudleigh obedience) vs verify-02 (ANON perfect friendship, Chapone coverture) — all treat marriage as consent-based contract/state with friendship/slavery tensions. **CONSISTENT.**
- `friendship`, `virtue`, `habit`, `divine_law`, etc. all show same pattern: same core concept, different book emphasis. **No cross-verifier definition contradictions that would warrant FAIL.**

**Related concepts:** No invalid relations; all use controlled vocabulary and are supported.

### 4.3 Internal Duplicates in verify-15

- `liberty` appears 3 times with **same** path `Political Philosophy → Liberty` but different definitions/books — valid but merger must dedup to one node with `books` union (MASHAM/Rutherforth/WARBURTON/Norris/Shaftesbury/Clarke etc., 10 books, 21 evidences union), `aliases` union, definition merged (longest or combined). If not merged, concept_graph will have duplicate nodes for same ID.
- `reward_and_punishment` appears twice with divergent paths (Theology vs Ethics) — must canonicalize to single path (recommend Theology) and union evidences (14 evidences).
- `marriage` appears twice with divergent paths (Political vs Ethics) — must canonicalize (recommend Political Philosophy → Family → Marriage) and union (13 evidences).
- If not merged, merger deduplication by ID will arbitrarily keep last-write-wins, losing evidences.

---

## 5. Whole-Shard Verdict: Was Wave 1 Verification Thorough?

**Short answer: Thorough on re-reading and conceptual correctness, but not fully thorough on evidence relevance vs padding, and not merge-ready due to one schema violation and three internal duplicates.**

| Criterion | Wave1 Performance | Wave2 Assessment |
|---|---|---|
| **Reading proof** | Re-read 1945 pages, 15441 blocks — claimed 3392734 chars; re-verified exactly 1945 pages, 15441 blocks, 3379225 chars (0.4% delta due to markdown fence counting). 3+ key passages per book proved read. | **PASS — thorough.** No pages skipped; line-by-line not sampled. |
| **Concept verification (23 overlapping)** | Checked all 23, found 10 NEEDS_FIX (missing shard evidence, contents pagination), 13 PASS; added 46 evidences. | **PASS with notes.** 10 NEEDS_FIX correctly identified (6 missing shard evidence, 4 contents-page mismatches). Fixes added were genuine shard pages, verified verbatim. Wave2 finds 12/168 shard evidences still not on claimed page due to block-split/hyphenation (e.g., Warb 200 "advantageous" split "ad- vantageous"), plus 3 filler, but core verification was diligent. |
| **Category / ID / query checks** | All 23 IDs snake_case, categories 2-4 sensible, definitions grounded, queries valid. | **PASS.** No illegal IDs, no invented queries, controlled vocabulary relations. |
| **Evidence verbatim** | Claimed 100% pass (excerpt substring found via normalized search). Added 46 shard evidences. | **PARTIAL.** 156/168 (92.9%) pass on claimed page; 12 fail due to stitched sentences (Warb 200), hyphen split, TOC formatting (RUTHERFORTH_1754 p5 not in slice). Plus 1 zero-evidence FAIL (occupancy). Not fabricated, but not 100% verbatim contiguous. Wave1 was slightly optimistic. |
| **Coverage quantity (>8%)** | Claimed 8.22% (160/1945) via adding 2-3 evidences per NEEDS_FIX + round-robin boosts; "How 8.2% was achieved" transparent. | **PARTIAL — inflated.** Strict shard-only unique pages 148/1945=7.61% (not 8.22%); genuine without filler 118-131/1945=6.1-6.7% (<8%). 17 trinity coverage-boosts + 13 scattered filler (15.7% filler) inflate count. Wave1 met letter via transparent padding, not spirit. Other shards padded more (verify-01 80 boosts, 3.31% genuine), so verify-15 is relatively restrained but still not genuinely >8%. |
| **Coverage relevance (fraud check)** | Added filler but labeled "Coverage-boost" explicitly. | **NEEDS_FIX — moderate padding, transparent not fraud.** 30 of 191 evidences (15.7%) are filler (errata table, publisher imprint, authorship line, Bull's Cuckoldom, generic procedural). While verbatim, they do not support definition. Task says "Flag any padding... irrelevant pages added just to hit 8% threshold." Padding exists. Not egregious fraud like verify-01/02 (40% synthetic) but still flag. |
| **Novelty / re-extraction (8 new)** | Extracted 8 new concepts cross-book: future_state, paternal_authority, positive_law, divine_institution, civil_society_origin, double_doctrine, intellect_moral_sense, occupancy. Searched Lipsius (0 hits), Seneca, Stoic. | **PASS with 1 FAIL.** 7 of 8 well-supported, truly novel to prior 356 (none in raw except future_state existed in limited form via reward_and_punishment). `occupancy` has **zero evidences** — SCHEMA violation, must be fixed. `double_doctrine` Hut p22 filler should be replaced. Other 6 are strong cross-book, query-relevant (future_state for reward/punishment & virtue/atheism, paternal_authority for marriage/slavery, double_doctrine for esoteric doctrine). Lipsius 0 hits confirmed via grep across 6 books (0), not a miss — correct handling. |
| **Cross-verifier consistency** | Not addressed in Wave1 report beyond own shard. | **NEEDS_FIX.** 2 internal duplicate IDs with divergent paths, 17 cross-file category divergences (mostly 2 vs 3 level). Wave1 left for merger without normalization attempt. Per guide, merger should have one canonical path per ID. |
| **Double-audit readiness** | 13 PASS, 10 NEEDS_FIX corrected, 8 new, 0 FAIL claimed. | **CONDITIONAL PASS: 12 PASS clean, 18 NEEDS_FIX minor, 1 FAIL (occupancy).** No concept factually wrong definitionally, but 19 require single-field edits (replace filler evidences, fix 12 verbatim stitched/split, canonicalize 2 divergent categories, add occupancy evidence). After fixes and 3 internal dedups, shard is merge-ready. |

**Overall Wave1 thoroughness:** **CONDITIONAL PASS (75% thorough).** Factually diligent on re-reading, concept checking, and cross-book extraction; transparent about coverage method; but not even more thorough than required — final double-audit still found **one schema violation (occupancy zero evidence), 12 verbatim stitched/split mismatches, 30 filler evidences (15.7% padding), and 3 internal duplicate IDs** requiring pre-merge fixes. Compared to verify-01/02 which had 80 filler and 3.31% genuine coverage, verify-15 is **more honest and less padded**, but still not clean. It prioritized threshold-meeting via modest padding over purely conceptual coverage, which the double-audit flags.

### 5.1 Recommendations Before Merge

1. **Fix occupancy FAIL immediately:** Add at least 1 verbatim excerpt, e.g., Rutherforth vol1 p47 "This compact is either division or occupancy" (occupatione context) or Hutcheson CAPUT VI p138 "Dominium quod ex rerum antea communium occupatione oritur" — verify on claimed page and add to evidence list. Without this, concept fails SCHEMA and must be excluded.
2. **Replace 30 filler evidences** (listed §3.1) with genuine conceptual pages:
   - `will`: replace 4 errata/generic auxiliaries with Hutcheson faculties pages (e.g., Hutcheson p70 intellect+moral sense, Rutherforth vol2 p28/29 liberty of individuals)
   - `obligation`: replace Bull's Cuckoldom with Rutherforth obligation passage (e.g., Rutherforth vol2 p29 natural liberty without consent)
   - `virtue_and_atheism`: replace authorship line and "by virtue of" homonyms with Warburton atheism polemic pages (e.g., Warb p24 Cabal context extended, p16/17 already used but need genuine atheism pages like p24/25)
   - `trinity`: **strip 17 coverage-boost evidences** (relevance 0.65) and replace with genuine CLARKE Trinity exegesis pages (CLARKE has 327 pages, >30 unused; e.g., p6,7,24 already used but many more available — use p8-15 genuine)
   - `liberty` (Norris): replace p6 patronage filler with genuine Norris liberty page
   - `paternal_authority`: replace Ruther vol1 p9 generic consent with genuine paternal authority (Ruther vol2 p34/36, Hutcheson p59)
   - `double_doctrine`: replace Hut p22 double brackets with genuine Warb double doctrine page (e.g., Warb p367, p263 already used, add p410 details)
3. **Fix 12 verbatim stitched/split mismatches:**
   - Warb 200 `reward_and_punishment`: split stitched excerpt into two separate evidences: "There was a Necessity of teaching some things to the Initiated, not expedient for others to know." and "There were many Truths, which it was not advantageous to the State to be generally known" (second via Varro quote p200).
   - RUTHERFORTH_1754 p5 `property`/`contract`/`oath`: replace with shard-slice equivalents (Ruther vol1 p21-23 property alienation, p12 occupancy)
   - `conscience` p105 TOC, `positive_law` p8, `civil_society_origin` p3, `liberty` p7, Ruther vol2 p5 all TOC formatting — keep but note page is contents, not discursive; acceptable if flagged as TOC but still contains concept term.
4. **Canonicalize 2 internal duplicate category_paths:**
   - Collapse `marriage`×2 → single node `marriage` with `category_path` **Political Philosophy → Family → Marriage** (Rutherforth/Hutcheson natural-law contract framing), `books` union (MASHAM/Rutherforth/Mandeville/WARBURTON/Hutcheson/NEWCOME), `evidence` union (13), `aliases` union.
   - Collapse `reward_and_punishment`×2 → **Theology → Moral Motivation → Reward and Punishment** (divine sanctions primary), `books` union, `evidence` union (14 evidences, after stripping p200 stitch and p6 filler).
   - Collapse `liberty`×3 → single node with union (21 evidences after stripping 2 filler, 10 books).
   - This reduces 31 lines to **28 distinct IDs** (27 unique + occupancy fix) for merger.
5. **Normalize 17 cross-verifier divergent category_paths per §4.1 table** (e.g., `will` → Faculties→Will, `marriage` 4-way → Political→Family, `slavery` → Slavery 2-level, `conscience` → Conscience 2-level). Update `merged/category_tree.json` to single node per ID.
6. **Coverage decision:** If project enforces >8% strictly, add ~25 more genuine shard pages via additional well-supported concepts (CLARKE Trinity alone can supply 20+ genuine pages; Warburton future state/double doctrine 10+) — **do not add synthetic filler**. If honesty prioritized, accept genuine 6.1-6.7% and note that honest shard + work-family variant counting exceeds 8% project-wide (as verify-14 noted). Flag verify-01/02 padding for down-weighting rather than penalizing this relatively honest shard.
7. **Lipsius query (42):** Confirm null result — 0 Lipsius hits across 1945 pages (case-insensitive grep verified). Keep `seneca_reference` proxy via double_doctrine/future_state; do not invent Lipsius concept.

---

## 6. Files Written & Validation

- `Concept Maps/verified/verify-15-wave2.jsonl` — **31 lines** (one per Wave1 concept, original fields preserved plus added `verification_wave2`); `wc -l` = 31, `python -m json.loads` all 31 succeed; **12 PASS, 18 NEEDS_FIX, 1 FAIL** per verification_wave2.verdict.
- `Concept Maps/verified_reports/verify-15-wave2-report.md` — this file.

Validation:
```
python3 -c "import json; [json.loads(l) for l in open('Concept Maps/verified/verify-15-wave2.jsonl')]; print('JSON OK')"
# JSON OK
wc -l Concept\ Maps/verified/verify-15-wave2.jsonl  # 31
python3 -c "import json; print({v:sum(1 for l in open('Concept Maps/verified/verify-15-wave2.jsonl') if json.loads(l)['verification_wave2']['verdict']==v) for v in ['PASS','NEEDS_FIX','FAIL']})"
# {'PASS': 12, 'NEEDS_FIX': 18, 'FAIL': 1}
```

Evidence verbatim rechecked via `blocks[].text` whitespace-normalized exact substring against `page_number`; cross-verifier divergence table built from 3 files' `category_path`; novelty checked against 356 raw `concept_id`s (104 distinct) and shard's 6 books via case-insensitive grep for Lipsius (0), Seneca (Warbruton 67, Hutcheson 0-16 Latin occupatione), Stoic (Warb 67, Hut 41).

---

## 7. Appendix: Verbatim Re-check Method (for reproducibility)

```python
import json, re, os, glob
base='/store/shuvam/BMoral'
shard_files = [
  'outputs/full_set/WARBURTON_Divine-legation-of-moses/WARBURTON_Divine-legation-of-moses.pages.jsonl',
  'outputs/corpus/Hutcheson, Francis (1694–1746)/Hutcheson Philosophiae Moralis Institutio Compendiaria with A Short Introduction to Moral Philosophy/Hutcheson Philosophiae Moralis Institutio Compendiaria with A Short Introduction to Moral Philosophy.pages.jsonl',
  'outputs/full_set/NEWCOME_1738_0_The-Plain-Account-of-the-Nature-and-End-of-the-Sacrament-PartII/NEWCOME_1738_0_The-Plain-Account-of-the-Nature-and-End-of-the-Sacrament-PartII.pages.jsonl',
  'outputs/full_set/CLARKE_1714_0_A-Reply-to-the-Objections-of-Robert-Nelson-Esq-and_of_an-anonymous-Author-against-Dr-Clarkes-Scripture-Doctrine-of-the-Trinity/CLARKE_1714_0_A-Reply-to-the-Objections-of-Robert-Nelson-Esq-and_of_an-anonymous-Author-against-Dr-Clarkes-Scripture-Doctrine-of-the-Trinity.pages.jsonl',
  'outputs/corpus/Rutherforth, Thomas (1712–1771)/Rutherforth Institutes of Natural Law vol. 1 part 2/Rutherforth Institutes of Natural Law vol. 1 part 2.pages.jsonl',
  'outputs/corpus/Rutherforth, Thomas (1712–1771)/Rutherforth Institutes of Natural Law vol. 2 part 1/Rutherforth Institutes of Natural Law vol. 2 part 1.pages.jsonl'
]
def norm(s): return re.sub(r'\s+', ' ', s).strip()
# Load page_number -> text
book_texts = {}
for rel in shard_files:
    bn=os.path.basename(rel)
    book_texts[bn]={}
    for line in open(os.path.join(base,rel)):
        obj=json.loads(line)
        pg=obj.get('page_number') or obj.get('page')
        txt=' '.join(b.get('text','') for b in obj.get('blocks',[]))
        book_texts[bn][pg]=txt
# Map book_id to basename
mapping={
  'WARBURTON_Divine-legation-of-moses':'WARBURTON_Divine-legation-of-moses.pages.jsonl',
  'Hutcheson Philosophiae Moralis Institutio Compendiaria with A Short Introduction to Moral Philosophy':'Hutcheson Philosophiae Moralis Institutio Compendiaria with A Short Introduction to Moral Philosophy.pages.jsonl',
  'NEWCOME_1738_0_The-Plain-Account-of-the-Nature-and-End-of-the-Sacrament-PartII':'NEWCOME_1738_0_The-Plain-Account-of-the-Nature-and-End-of-the-Sacrament-PartII.pages.jsonl',
  'CLARKE_1714_0_A-Reply-to-the-Objections-of-Robert-Nelson-Esq-and_of_an-anonymous-Author-against-Dr-Clarkes-Scripture-Doctrine-of-the-Trinity':'CLARKE_1714_0_A-Reply-to-the-Objections-of-Robert-Nelson-Esq-and_of_an-anonymous-Author-against-Dr-Clarkes-Scripture-Doctrine-of-the-Trinity.pages.jsonl',
  'Rutherforth Institutes of Natural Law vol. 1 part 2':'Rutherforth Institutes of Natural Law vol. 1 part 2.pages.jsonl',
  'Rutherforth Institutes of Natural Law vol. 2 part 1':'Rutherforth Institutes of Natural Law vol. 2 part 1.pages.jsonl',
}
def find_bn(book_id):
    for k,v in mapping.items():
        if k.lower() in book_id.lower() or book_id.lower() in k.lower():
            return v
    return None
# For each evidence where find_bn != None:
#   check norm(excerpt) in norm(book_texts[bn][page])
#   if not found, search all pages of that bn for excerpt (page mismatch) or check hyphen split "ad- vantageous"
# Result: 156/168 strict pass on claimed page; 12 fails are stitched/hyphen/TOC (see §2); 1 zero-evidence FAIL (occupancy).
# Out-of-shard evidences (MASHAM, ASTELL, CLARKE_1708, NORRIS_1689, etc.) not checked against these 6; spot-checked in own files all verbatim.
# Lipsius/Seneca counts: case-insensitive grep for "Lipsius" (0 hits across 6), "Seneca" (Warb 67, Hut 0), "\bStoic" (Warb 67, Hut 41) verified.
```

All 6 books re-read via this method; no sampling. Report generated after independent re-parse, not trusting Wave1 counts.

---

*Double-audited by verify-15-wave2 after independent re-read of all 1945 pages (15441 blocks, 3379225 chars). All shard-relevant evidences re-verified verbatim; 156/168 pass on claimed page, 12 block-split/TOC mismatches, 1 zero-evidence FAIL (occupancy), 30 filler evidences flagged (15.7% padding, transparent). Cross-verifier consistency checked across verify-15/01/02; 2 internal divergences + 17 cross-file divergences flagged for merger. 8 new concepts: 7 well-supported, 1 FAIL (occupancy). Genuine conceptual coverage 6.1-6.7% without filler (7.61% with filler, not 8.22%). Wave1 was factually thorough but not fully thorough on relevance vs padding and not merge-ready pending 19 single-field fixes and 3 dedups.*

