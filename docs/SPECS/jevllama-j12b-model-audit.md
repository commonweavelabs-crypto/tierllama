# J12-B: Classifier Model Audit — Laya / FastJev / openJev vs our qwen3:4b
#project/jevllama #benchmark #model-audit

> 2026-09-23. Authored for Gui's question: "is it worth switching the brain?"
> Scope: the Tierllama CLASSIFIER (the Jev-class decision head), not the lanes.
> Status quo: qwen3:4b via Ollama, enum-constrained JSON, temp 0. J12 roleless
> rubric v7: difficulty 67.7% / timing 91.9% / full 61.3% (±3pt), ~0.2-0.5s warm,
> ~2.6GB VRAM resident (Ollama keeps it loaded; total GPU at audit time 9.1/16.3GB
> with ComfyUI co-resident).

## The three candidates (all verified live via GitHub API 9/23)

### 1. Laya (NandhaKishorM/laya) — 20,824★, Apache-2.0, created 9/18
The "literal copy from China" Gui remembered (convaiinnovations on HF, zh docs).
Non-autoregressive System 1 decision engine: typed choice/score/noul over text
in ONE forward pass, no generated text. Three checkpoints + Router:
- laya (ModernBERT-large, 421M, ctx 512, English)
- laya-multilingual (mmBERT-base, 322M, ctx 1024, 100+ langs, 2x faster)
- laya-typed-decisions (ModernBERT-large, 421M, ctx 1024)
- Measured on T4: 33ms/question single, 7.2ms batched. Windows supported
  (PowerShell venv instructions; ~10x faster loading in 0.3.11). CUDA via
  torch/nix/Docker; GGUF community builds (mys/laya-GGUF 2.4k downloads) run
  on llama.cpp; ONNX port exists.
- Honest head-to-head (their own README, shared benchmark 17,416 questions):
  - Argmax accuracy: Laya 0.766 vs Jev 0.727 (Laya wins top-1)
  - Soft accuracy (probability quality): Jev 0.580 vs Laya 0.471 (Jev wins)
  - Raw calibration: Jev ECE 0.144 vs Laya 0.213 (Jev better uncalibrated;
    Laya reaches 0.081 only after domain temperature fitting)
  - >50 options in one prompt: Jev better (Laya needs shortlist mode)
- Their own benchmark table: English checkpoint XNLI 0.521 / multilingual 0.731.

### 2. FastJev (chengyongru/fastjev) — 18★, MIT, created 9/20
Self-hosted System One-compatible runtime; SemIf fork (same technique our
classifier's design came from). Runs pinned open models via Torch/vLLM/MLX/
llama.cpp/WebGPU; optional System One-compatible HTTP API. Claims: Qwen3-0.6B
0.440, MiniCPM5-2B 0.686, Qwen3.5-4B 0.813 balanced accuracy (their ladder,
native BF16 logit). Zero core deps, extras opt-in. Young/unproven (18★, 3 days).

### 3. openJev-verdict-2.0 (Heman10x-NGU) — 280★, Apache-2.0 (license file
nonstandard = verify), created 9/19
151M ModernBERT+GLiClass decision engine claiming 77.10% acc, 0.0636 Brier,
ECE 1.44%, ~20-25ms/decision, WebGPU edge-ready, beating both Jev and Laya on
JevBench. Single-author claim on own benchmark = treat as unverified until we
run it ourselves.

## Honest audit — is switching worth it?

### What our qwen3:4b actually does that these models don't
1. **Reads conversation context** (last_exchanges) — encoder-only decision
   models take state strings; our classifier gets multi-turn context for free.
2. **Two dimensions in one call** (difficulty AND timing) with arbitrary
   rubric semantics — rubric text is prose the LLM reads natively.
3. **Zero architecture change** — it's already wired: config, confidence
   fallback, decision log, golden set, regression runner, dogfood proxy.

### What Laya would give us (if it works on our golden set)
- ~10x smaller resident footprint (421M vs 4B ≈ 0.9GB vs 2.6GB VRAM)
- ~10-20x faster (33ms vs 200-500ms warm; matters for the local-lane tax)
- Real calibrated probabilities from logits (we fake it with enum-JSON today)
- True head-to-head argmax: 0.766 vs Jev 0.727 — BUT on THEIR benchmark
  questions, not OUR golden set. Our difficulty taxonomy (EASY→EXPERT with
  video-workspace referents) is NOT their benchmark. Unknown until benched.

### What we'd have to change (the cost side)
- Laya: pip install laya + a new adapter (~1 file) + re-map our 2-dim call into
  their choice/score question shape. Router/lane code untouched. Estimate:
  half a day including bench. NOT a rebuild.
- FastJev: similar (SDK + adapter), but 18★ maturity risk.
- openJev: smallest model, biggest claim, least proven — bench only, no switch
  consideration without reproduction.

### 100x-better test (Gui's bar)
NO candidate is 100x better. Expected realistic outcome: Laya ≈ equal or
slightly better accuracy on OUR set, 10x faster, 3x lighter, worse probability
quality/calibration out of the box. That is a "good upgrade if the bench
confirms", not a "must rebuild" — and our architecture survives either way
because the classifier is behind one interface (classify() -> dims).

## Verdict
1. **Don't switch now.** No evidence of a step-change; switching costs a bench
   first, and our current head is inside the J12 floors and dogfooded.
2. **DO bench (J12-B)**: laya (english + typed-decisions checkpoints) and
   openJev-verdict-2.0 on tests/golden_set_v1.json, same protocol as
   tests/run_golden_set.py. FastJev optional (Qwen3.5-4B ladder claim) —
   lowest priority, maturity risk.
3. **Architecture insurance already in place**: classifier is one file behind
   one function signature. If Laya wins on accuracy AND latency AND memory,
   swapping is an adapter, not a rebuild.
4. Keep Jev-class technique leadership: ours = enum-JSON (SemIf-equivalent
   read); Laya/openJev = native logit heads. If Laya wins, consider hybrid:
   Laya for difficulty, qwen3:4b for context-heavy timing calls.

## Bench protocol (when Gui fires the goal)
1. venv, pip install laya; download convaiinnovations/laya-typed-decisions
2. Map golden set: state = message (+ last exchange), questions = difficulty
   (choice EASY/MEDIUM/HARD/EXPERT) + timing (choice NOW/LATER)
3. Run 62, same scoring code as run_golden_set.py; report same 3 metrics
4. Also record: cold load, warm p50/p95, VRAM while resident
5. Repeat for openJev if its checkpoint loads clean
6. Verdict table vs J12 floors; decision memo to Gui. NO default-flip without
   Gui's explicit approval.