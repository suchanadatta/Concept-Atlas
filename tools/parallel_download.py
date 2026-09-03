#!/usr/bin/env python3
"""Parallel Google Drive downloader for the remaining corpus files.

Reads the manifest (id<TAB>name) produced from the gdown folder log and
downloads all remaining files with 6 concurrent workers. Skips files that
already exist on disk with non-zero size.
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

GDOWN = "/store/shuvam/BMoral/.venv/bin/gdown"
OUT_DIR = "/store/shuvam/BMoral/data/drive_pdfs/collection/pdf"
MANIFEST = "/tmp/opencode/remaining.tsv"


def download(fid, name):
    out = os.path.join(OUT_DIR, name)
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return name, "SKIP"
    url = f"https://drive.google.com/uc?id={fid}"
    try:
        subprocess.run(
            [GDOWN, "--continue", url, "-O", out],
            capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        return name, "TIMEOUT"
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return name, "OK"
    try:
        os.remove(out)
    except OSError:
        pass
    return name, "FAIL"


def main():
    todo = []
    with open(MANIFEST) as f:
        for line in f:
            line = line.rstrip("\n")
            if line:
                fid, name = line.split("\t", 1)
                todo.append((fid, name))
    print(f"{len(todo)} files to download", flush=True)

    os.makedirs(OUT_DIR, exist_ok=True)
    ok = skip = fail = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(download, fid, name): name for fid, name in todo}
        done = 0
        for fut in as_completed(futures):
            name, status = fut.result()
            done += 1
            if status == "OK":
                ok += 1
            elif status == "SKIP":
                skip += 1
            else:
                fail += 1
                print(f"FAIL {name} [{status}]", flush=True)
            if done % 10 == 0 or done == len(todo):
                print(f"progress {done}/{len(todo)}: ok={ok} skip={skip} fail={fail}", flush=True)
    print(f"DONE ok={ok} skip={skip} fail={fail}", flush=True)


if __name__ == "__main__":
    main()
