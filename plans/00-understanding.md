# 00 — Understanding

## Task
Clone https://github.com/baidu/Unlimited-OCR.git and study it.

## Success criteria
1. Repo cloned to /store/shuvam/BMoral/Unlimited-OCR (verified working tree).
2. Complete study of: purpose, architecture, code contents, inference paths, model config.
3. Findings written to disk (plans/) and presented to user.

## Constraints
- Analysis-only task: no code modifications to the cloned repo.
- Do not touch the pre-existing BMoral_pdf_collection.zip (2.1 GB) in the workspace.
- External claims (HF repo, arXiv) verified live per A8.

## Open questions (resolved)
- Q1: What does the repo actually contain? → Model-release repo: inference utilities + custom SGLang wheel + paper PDF. Weights live on HuggingFace.
- Q2: What is R-SWA? → Reference Sliding Window Attention (see 01-research).
- Q3: Where is the model implementation? → SGLang wheel (sglang/srt/models/unlimited_ocr.py) + HF repo custom code (modeling_unlimitedocr.py).

## Date
2026-08-13
