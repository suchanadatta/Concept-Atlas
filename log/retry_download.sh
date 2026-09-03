#!/bin/bash
# Retries the Drive folder download with backoff until complete.
export UV_CACHE_DIR=/store/shuvam/uv-cache UV_PYTHON_INSTALL_DIR=/store/shuvam/uv-python
cd /store/shuvam/BMoral
WAIT=1800  # start with 30 min backoff
for attempt in 1 2 3 4 5 6; do
    echo "=== download attempt $attempt $(date) ==="
    .venv/bin/gdown --folder --continue \
        "https://drive.google.com/drive/folders/1Xkwt8yd4cDOs1kXaRaVdTEujRWVwfWUL" \
        -O data/drive_pdfs >> log/gdown_retry.log 2>&1
    rc=$?
    n=$(find data/drive_pdfs -name "*.pdf" | wc -l)
    echo "attempt $attempt: exit=$rc, pdfs=$n"
    if [ "$rc" = "0" ]; then
        echo "=== DOWNLOAD COMPLETE $(date) ==="
        break
    fi
    echo "waiting ${WAIT}s before retry..."
    sleep $WAIT
    WAIT=$((WAIT * 2))  # exponential backoff
done
echo "=== retry loop finished $(date); total PDFs: $(find data/drive_pdfs -name '*.pdf' | wc -l) ==="
