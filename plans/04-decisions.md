# 04 — Decisions / Discoveries / Reversals

## Strategy validation (2026-08-13, OCR setup task)

USER STRATEGY (restated): "Setup the Unlimited-OCR [repo] with the GLM-OCR model, connected correctly, to parse the extracted PDF corpus."

VALIDATION: **PARTIALLY FLAWED as literally stated — cannot run Unlimited-OCR software with GLM-OCR weights.**
- Unlimited-OCR (Baidu): DeepSeek-OCR lineage — DeepEncoder + R-SWA MoE decoder, vocab 129,280, own tokenizer/modeling code. [VERIFIED: HF config.json + wheel code]
- GLM-OCR (Zhipu): GLM-V + CogViT + MTP, vocab 59,392, different tokenizer/config/modeling (glm_ocr in transformers≥5.3). [VERIFIED: HF config.json + local weights]
- The two are architecturally incompatible: weights, tokenizers, and code are NOT interchangeable.
- Additionally, Unlimited-OCR weights were never downloaded (only its repo); GLM-OCR weights ARE in models/GLM-OCR.

WORKABLE INTERPRETATION (adopted): set up the **GLM-OCR self-hosted pipeline** (the model we have) to parse the 61-PDF corpus. This satisfies the evident intent (OCR the corpus now) with what is actually present. Unlimited-OCR can be set up separately if the user wants it (needs its own 6 GB weight download + separate stack).

## Decisions
| ID | Decision | Rationale | Rejected |
|----|----------|-----------|----------|
| D7 | vLLM server (pip) as OCR backend | README primary path; MTP speculative support; OpenAI-compatible API the SDK expects | SGLang (no MTP recipe for this model in repo), transformers-direct (SDK needs a server) |
| D8 | Dedicated uv venv (Python 3.12.8) at .venv | Isolate from system python 3.10/transformers 4.57.6; GLM-OCR README uses 3.12 | upgrading system env |
| D9 | uv cache redirected to /store/shuvam/uv-cache | /store/uv/sdists-v9 owned by other user (gautam, 0700) — permission denied | fighting /store/uv perms |
| D10 | Docker vLLM image | NOT USED — no nvidia-container-toolkit → no GPU passthrough | docker pull vllm/vllm-openai |
| D11 | Background install via setsid nohup + log | Long multi-GB download; session must not block; survives tool timeouts | foreground install |
| D12 | --max-model-len 32768, gpu-mem-util 0.85, port 8080, served-model-name glm-ocr | Matches SDK config; A100 80GB has ample headroom | 128K ctx (unneeded for layout-cropped regions, wastes KV memory) |

## Discoveries
| ID | Finding | Impact | Status |
|----|---------|--------|--------|
| F11 | A100 80GB available; driver 610 / CUDA 13.3 UMD | GPU path viable; cu13 wheels compatible | closed |
| F12 | uv pip resolves vllm with nvidia-*-cu13 wheels | No system CUDA toolkit needed | closed |
| F13 | GLM-OCR README requires vllm>=0.19.0 + transformers>=5.3.0 (PyPI: 0.27.1 / 5.15.0 exist) | Version targets verified live | closed |
| F14 | glmocr default config has maas.enabled: true | Must flip to false for self-hosted | closed (config.yaml written) |

## Open Qs
| ID | Question | Prio | Status |
|----|----------|------|--------|
| O5 | Does vllm 0.27.1 still support GLM-OCR MTP spec-config? | high | pending server smoke test |
| O6 | PP-DocLayoutV3_safetensors download at first layout run | medium | pending |
| O7 | Full-corpus runtime estimate (11,064 pages) | medium | measure on test run |
