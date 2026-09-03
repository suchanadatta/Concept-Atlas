#!/bin/bash
# Poll until corpus re-enrichment finishes, then finalize (verify + rebuild archive).
cd /store/shuvam/BMoral
while ! grep -q "CORPUS RE-ENRICH DONE" log/run_reenrich_corpus_wrapper.log 2>/dev/null; do
    sleep 300
done
sleep 30
exec ./log/finalize_after_reenrich.sh
