#!/bin/bash
cd /store/shuvam/BMoral
# text-only archive: jsonl + json + md, max compression, all threads
find outputs -type f \( -name "*.jsonl" -o -name "*.json" -o -name "*.md" \) \
    | tar -c -I 'xz -9 -T0' -f outputs-text.tar.xz -T -
echo "TEXT TAR EXIT: $?"
ls -la outputs-text.tar.xz
