# 01 — Research

## Topic: baidu/Unlimited-OCR — repo + model + paper

Queries:
1. GitHub API repo metadata → https://api.github.com/repos/baidu/Unlimited-OCR (live, this session)
2. HuggingFace model API → https://huggingface.co/api/models/baidu/Unlimited-OCR (live)
3. HF config.json → https://huggingface.co/baidu/Unlimited-OCR/resolve/main/config.json (live)
4. arXiv paper → https://export.arxiv.org/api/query?id_list=2606.23050 (live)
5. Repo content: README.md, infer.py, CONTRIBUTING.md, LICENSE, .gitignore, Unlimited-OCR.pdf (pdftotext), wheel/ (unzipped, 3073 files)

## Findings
- Repo: MIT license, Python, 23,654 stars / 2,427 forks, created 2026-06-18, last push 2026-07-29, default branch main, 13 commits (all README updates since "Initial commit"). (Source: GitHub API)
- Repo contains only 10 files: README.md, infer.py, LICENSE, CONTRIBUTING.md, .gitignore, Unlimited-OCR.pdf (the paper), wheel/sglang-*.whl (12 MB custom SGLang build), assets/ (3 images). Weights are NOT in the repo — they live at HF baidu/Unlimited-OCR (2.88M downloads, 4,043 likes, single safetensors + custom modeling code). (Source: GitHub + HF APIs)
- Paper (arXiv 2606.23050, published 2026-06-22): "Unlimited OCR Works — Welcome the Era of One-shot Long-horizon Parsing", Baidu Inc.
- Core contribution: R-SWA (Reference Sliding Window Attention). Each decode token attends to ALL prefix tokens (visual + prompt, "reference" set P, length L_m) plus a causal sliding window of width n=128 over generated output (D_n(t)). KV cache size C(T) = L_m + min(n,T) ≤ L_m + n — constant during decode. (Source: paper §3.4, Eq. 1-9)
- Architecture: DeepSeek-OCR baseline. DeepEncoder (SAM-ViT + CLIP-ViT cascade, 16× token compression; 1024×1024 → 256 tokens) + MoE LLM decoder (paper: 3B total, 0.5B activated), all attention replaced with R-SWA. Trained 4,000 steps, batch 256, seq 32K, 8×16 A800, DeepEncoder frozen, AdamW lr 1e-4, cosine, DeepEP EP=4, Megatron-LM. (Source: paper §3-4)
- Data: ~2M samples, 9:1 single:multi-page, PaddleOCR annotations, coords normalized 0-1000, multi-page synthesized 2-50 pages with <page> separator. (Source: paper §4.1)
- Results (paper): OmniDocBench v1.5 overall 93.23 (vs DeepSeek-OCR 87.01, +6.22); v1.6 overall 93.92 (SOTA, vs Qianfan-OCR 93.90). Long-horizon: 40+ pages → Distinct-35 96.90%, Edit 0.1069. 5,580 TPS @512 concurrency (vs 4,951, +12.7%). At 6K output tokens, TPS advantage 35%. (Source: paper Table 1/3/4)
- SGLang integration (wheel): sglang/srt/models/unlimited_ocr.py (464 lines) — UnlimitedOCRForCausalLM: SAM ViT-B + CLIP-L encoders, MlpProjector, DeepseekForCausalLM backbone (V1, non-MLA), prefill-aware SWA. get_attention_sliding_window_size() → config value; is_prefill_aware_swa() → True. Scheduler sets req.swa_evict_floor = prefill_len - prefix_token_count after prefill (scheduler.py:2627) so prefill KV slots are never evicted; eviction only affects the decode window gap. Also touches chunk_cache.py, pure_swa_radix_cache.py, schedule_batch.py. (Source: wheel code, read this session)
- Custom logit processor: DeepseekOCRNoRepeatNGramLogitProcessor — blocks n-gram repetition within a sliding window (ngram_size=35, window_size=128/1024) by banning tokens in a window scan. (Source: wheel custom_logit_processor.py:140)
- Deployed model config (HF config.json, VERIFIED): model_type unlimited-ocr; LLM: hidden 1280, 12 layers, 10 heads (head_dim 128), vocab 129,280, max_pos 32,768, MoE 64 routed + 2 shared experts, top-6, moe_intermediate 896, first_k_dense_replace 1, use_mla False; sliding_window_size 128; DeepEncoder image_size 1024; tile_tag 2D. NOTE: wheel's UnlimitedLanguageConfig class defaults (4096/30/102400) are just class defaults — actual values come from config.json.
- HF custom code files: modeling_unlimitedocr.py, deepencoder.py, modeling_deepseekv2.py, configuration_deepseek_v2.py, conversation.py, processor_config.json (verified via HF API file listing).
- Inference paths: (1) HF transformers (AutoModel trust_remote_code, infer/infer_multi, gundam/base modes); (2) vLLM (official recipe, docker images vllm/vllm-openai:unlimited-ocr[-cu129]); (3) SGLang (local wheel + kernels pin, fa3 attention, custom logit processor); (4) infer.py batch script (ThreadPoolExecutor concurrency, auto server start, retries, TPS stats).
- Image modes: gundam (base_size 1024, image_size 640, crop_mode True, dynamic resolution, single page) vs base (1024×1024, multi-page/PDF).

## Conflicts
- Paper says "3B-A0.5B MoE" and "30 layers" implied by DeepSeek-OCR baseline; deployed config.json shows 12 layers / hidden 1280 / 64 experts (~2B-ish). The wheel class defaults (30 layers, 4096) also differ. Resolution: paper reports the nominal model family; config.json is ground truth for the deployed checkpoint. Flagged, not resolved — no weights downloaded (would be ~6 GB) to count exact params.
- Paper §3.4.3 mentions FlashAttention v3 kernels; SGLang recipe uses fa3 backend — consistent.

## Conclusion + confidence
- [VERIFIED: GitHub/HF/arXiv APIs + local files] Repo contents, model identity, paper claims, deployed config.
- [DERIVED] R-SWA mechanics from paper equations; SWA eviction floor mechanism from wheel source.
- [HIGH-CONF] Training details as reported by the paper (not independently reproduced).

## Open
- Exact parameter count of deployed checkpoint (would need 6 GB weight download).
- HF-side R-SWA implementation details (modeling_unlimitedocr.py not fetched; lives on HF, not in repo).

## Topic: zai-org/GLM-OCR — repo + SDK + model (clone #2, 2026-08-13)

Queries:
1. GitHub API → https://api.github.com/repos/zai-org/GLM-OCR (live)
2. HF model API → https://huggingface.co/api/models/zai-org/GLM-OCR (live)
3. HF config.json → https://huggingface.co/zai-org/GLM-OCR/resolve/main/config.json (live)
4. arXiv → https://export.arxiv.org/api/query?id_list=2603.10910 (live)
5. Local: README.md, README_zh.md, pyproject.toml, glmocr/ (11K lines Python, 39 files), examples/, skills/, apps/, .github/workflows/

Findings:
- Repo: Apache-2.0, Python, 7,269★ / 658 forks, created 2026-02-02, last push 2026-04-21, 110 commits, v0.1.5, CI (ci/pre-commit/release actions). (Source: GitHub API + git log)
- GLM-OCR = Zhipu's multimodal OCR model: GLM-V encoder–decoder architecture, MTP (Multi-Token Prediction) loss + full-task RL training, CogViT visual encoder, lightweight cross-modal connector with token downsampling, GLM-0.5B language decoder. Two-stage pipeline: layout analysis (PP-DocLayout-V3) + parallel region recognition. (Source: README)
- Claims: 94.62 on OmniDocBench V1.5 (#1 overall), 0.9B params, vLLM/SGLang/Ollama deployment. (Source: README)
- Deployed config (HF config.json, VERIFIED): model_type glm_ocr, GlmOcrForConditionalGeneration; vision: hidden 1024, patch 14, image 336 (CogViT-style); text: hidden 1536, 16 layers, 16 heads/8 KV heads, vocab 59,392, intermediate 4608, max_pos 131,072 (128K ctx), tie_word_embeddings False. No MTP keys in config (training-time loss; inference uses vLLM speculative MTP method per README).
- HF repo: 3.3M downloads, 1,977 likes, single model.safetensors + tokenizer + eval results (mdpbench.yaml, olmocrbench.yaml). (Source: HF API)
- arXiv 2603.10910 "GLM-OCR Technical Report" published 2026-03-11. (Source: arXiv API)
- SDK (glmocr pkg, v0.1.5): two modes — MaaS (Zhipu cloud API passthrough, GPU-free) and Self-hosted (local vLLM/SGLang + in-SDK pipeline). Pipeline = 3-stage async: PageLoader (images/PDF→pages) → PPDocLayoutDetector (PP-DocLayoutV3 object detection, batch inference, NMS/unclip/merge post-processing) → OCRClient (OpenAI-compatible or ollama_generate API) → ResultFormatter (JSON + Markdown). 3 worker threads + bounded queues + health watchdog + ordered emission (preserve_order). CLI (glmocr parse), Python API (GlmOcr/parse), Flask server (python -m glmocr.server, port 5002), agent Skill mode (skills/glmocr/SKILL.md), custom pipeline extension points. (Source: repo code, read this session)
- Extras: examples/ (finetune via LLaMA-Factory, mlx-deploy for Apple Silicon, ollama-deploy, multi-gpu-deploy, self-host server+client), apps/ (Flask backend + frontend web app, docker scripts), skills/ (glmocr, -formula, -handwriting, -table agent skills), tests (test_unit.py 2,655 lines, test_integration.py 477).

Conflicts:
- README says "GLM-0.5B language decoder" and total 0.9B params; config shows 16L/1536h — consistent with ~0.9B total (not independently counted; would need 2 GB download).
- MTP claim: not visible in deployed config.json; supported via vLLM speculative-config method "mtp" per README — [HIGH-CONF] from README only.

Conclusion: [VERIFIED: APIs + local code] repo contents, SDK architecture, deployed config, paper identity. [HIGH-CONF] benchmark claims and MTP training details (from paper/README, not reproduced).

Open: exact param count; GLM-OCR technical report details (not fetched); MTP inference path internals.
