# Re-Verification Checklist — All Verifiers MUST Complete

## Reading Verification (Prove You Read Everything)
- [ ] Read EVERY page of EVERY book in your shard (use Read with offset for large JSONL, iterate line by line, count pages)
- [ ] Report: `total_pages_read`, `total_blocks_read`, `total_chars_read` for your shard
- [ ] Report: `evidence_pages_cited` / `total_pages` = coverage % (must be >8%, not 2% like before)
- [ ] For each book, list 2-3 key passages (page + quote) proving you read it — not just evidence for concepts

## Concept Verification (For Each Previous Concept Touching Your Books)
Previous concepts are in `Concept Maps/raw/agent-*.jsonl` (356 concepts). Filter to those where `books` overlaps your shard's book_ids.

For EACH such concept:
- [ ] Verify `concept_id` is snake_case singular, `category_path` is 2-4 levels and sensible
- [ ] Verify `definition` is accurate to the books you read (not generic)
- [ ] Verify EVERY `evidence` entry: is `text_excerpt` verbatim substring of that page's block text? Check with exact string search. Flag mismatches.
- [ ] Verify `related_concepts` relations make sense and are supported by the books
- [ ] Verify `query_relevance` tags are correct
- [ ] Verdict: `PASS` / `FAIL` / `NEEDS_FIX` with reason
- [ ] If FAIL, provide corrected version

## Re-Extraction (Find What Was Missed)
- [ ] Re-scan ALL pages of your shard for concepts the first pass missed
- [ ] Specifically check for the 43 queries — especially the ONE uncovered: `Citations or references to Lipsius's work` (check for "Lipsius", "Seneca", "Stoic" mentions)
- [ ] Extract 5-10 NEW concepts that were missed, or confirm none missing with evidence
- [ ] Focus on cross-book connections: concepts that link multiple books in your shard (e.g., a concept appearing in both a Hutcheson and a Shaftesbury book with different perspectives)

## Output
Write to `Concept Maps/verified/verify-XX.jsonl` — one JSON per line for verified/new concepts with added `verification` field:
```json
{
  "concept_id": "self_love",
  "verification": {
    "verifier": "verify-03",
    "verdict": "PASS",
    "pages_read_proof": "Read all 1403 pages across 7 books; evidence pages now 140/1403 (10%)",
    "evidence_verbatim_check": "PASS — all 3 excerpts verified as substrings",
    "category_check": "PASS — Moral Psychology is correct",
    "new_evidence_added": 2
  },
  ... rest of original fields plus any fixes ...
}
```

Also write a report to `Concept Maps/verified_reports/verify-XX-report.md` with:
- Reading stats table
- Verification table (concept, verdict, issues)
- New concepts added
- Coverage improvement

## Double-Audit Requirement
You will be RE-DEPLOYED a second time after this wave. Your verified output will be checked by a different verifier. Make it thorough now so second pass is clean.

