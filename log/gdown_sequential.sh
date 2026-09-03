#!/bin/bash
export UV_CACHE_DIR=/store/shuvam/uv-cache UV_PYTHON_INSTALL_DIR=/store/shuvam/uv-python
cd /store/shuvam/BMoral
# sequential folder download — skips existing files, resumes cleanly
.venv/bin/gdown --folder --continue "https://drive.google.com/drive/folders/1Xkwt8yd4cDOs1kXaRaVdTEujRWVwfWUL" -O data/drive_pdfs
echo "GDOWN EXIT: $?"
find data/drive_pdfs -name "*.pdf" | wc -l
