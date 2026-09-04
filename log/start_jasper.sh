#!/bin/bash
cd /store/shuvam/BMoral
export UV_CACHE_DIR=/store/shuvam/uv-cache
exec .venv/bin/python tools/jasper_search_server_v2.py --port 8790 --device cpu
