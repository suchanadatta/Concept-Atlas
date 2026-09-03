#!/bin/bash
# Wait for the full-set re-enrichment chain to finish, then run the corpus chain.
cd /store/shuvam/BMoral
while ! grep -q "RE-ENRICH DONE" log/run_reenrich.log 2>/dev/null; do sleep 120; done
./log/run_reenrich_corpus.sh > log/run_reenrich_corpus.log 2>&1
