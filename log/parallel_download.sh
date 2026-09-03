#!/bin/bash
export UV_CACHE_DIR=/store/shuvam/uv-cache UV_PYTHON_INSTALL_DIR=/store/shuvam/uv-python
cd /store/shuvam/BMoral
mkdir -p data/drive_pdfs/collection/pdf

download_one() {
    fid="$1"; name="$2"
    out="data/drive_pdfs/collection/pdf/$name"
    [ -s "$out" ] && { echo "SKIP $name"; return 0; }
    .venv/bin/gdown --continue "https://drive.google.com/uc?id=$fid" -O "$out" > /dev/null 2>&1
    [ -s "$out" ] && echo "OK: $name" || { echo "FAIL: $name"; rm -f "$out"; }
}
export -f download_one

tail -n +1 /tmp/opencode/remaining.tsv | xargs -P 6 -L 1 bash -c 'download_one "$0" "$1"'
echo "=== PARALLEL DOWNLOAD COMPLETE: $(find data/drive_pdfs -name '*.pdf' | wc -l) PDFs on disk ==="
