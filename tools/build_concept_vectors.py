#!/usr/bin/env python3
"""Embed all 202 concept definitions with Jasper -> models/jasper_index/concepts.npy

Enables query->concept semantic matching for the dynamic query graph.
"""
import json, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent.parent
MODEL = REPO / "models" / "Jasper-Token-Compression-600M"
OUT = REPO / "models" / "jasper_index"
GRAPH = REPO / "Concept Maps" / "final" / "concept_graph.jsonl"

def main():
    import torch
    from sentence_transformers import SentenceTransformer
    device = sys.argv[1] if len(sys.argv) > 1 else ("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    model = SentenceTransformer(str(MODEL), model_kwargs={"torch_dtype": dtype, "attn_implementation": "sdpa", "trust_remote_code": True}, trust_remote_code=True, device=device)

    ids, texts = [], []
    for line in open(GRAPH, encoding="utf-8"):
        d = json.loads(line)
        if d.get("type") != "node":
            continue
        # embed label + definition + aliases as one doc
        doc = f"{d['label']}. {d.get('definition','')[:800]}"
        ids.append(d["id"])
        texts.append(doc)
    print(f"embedding {len(texts)} concepts on {device}…")
    emb = model.encode(texts, normalize_embeddings=True, compression_ratio=0.3333,
                       batch_size=32, convert_to_numpy=True, show_progress_bar=True)
    np.save(OUT / "concepts.npy", emb.astype(np.float16))
    (OUT / "concepts_meta.json").write_text(json.dumps(ids))
    print(f"saved {len(ids)} concept vectors -> {OUT/'concepts.npy'}")

if __name__ == "__main__":
    main()
