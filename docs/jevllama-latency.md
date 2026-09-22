# Tierllama Latency — Measured Numbers & Offload Design (technical)

**Date:** 2026-09-22 | **Question (Gui):** How much latency does the classifier add?
Is it always loaded? Can it offload to other machines (box/Mac) or cloud when the local
GPU is busy?

## 1. Classifier latency (qwen3:4b on RTX 5070 Ti, measured live)

| State | Latency | Notes |
|---|---|---|
| Warm (model resident) | **0.026–0.042s** | the number that matters in steady use |
| Cold (unloaded, reload from disk/VRAM) | **2.9s** | after unload; once per idle period |
| First-ever load after Ollama restart | ~13s | full model load |

**Router overhead beyond the classifier: ~0** (lane decision + JSONL log write are
microseconds). So the router's cost to the user = classifier latency only.

## 2. Is the model always loaded? No — Ollama unloads it (Gui's intuition confirmed)

Ollama default keep_alive = **5 minutes** idle, then the model unloads from VRAM and
the GPU is free for other tasks (games, ComfyUI, other models). Verified live: after
explicit unload (`keep_alive: 0`), next call = 2.9s reload, then 0.026s warm.

**Configurable:** `keep_alive` can be set per call or globally. For Tierllama the
product default should be: **unload after 5 min idle** (matches Gui's expectation,
frees VRAM), with a config option `classifier.keep_alive` for always-on users
(traders/streamers who want zero cold starts). A 2.9s reload once per idle period is
acceptable; classify-then-route can even PREFETCH the lane model during reload.

## 3. Offload ladder (Gui's brainstorm → measured + design)

Scenario: local GPU/RAM busy (ComfyUI, game, another LLM). Options measured TODAY:

| Fallback classifier host | Measured latency | Verdict |
|---|---|---|
| Local GPU (default) | 0.03s warm / 2.9s cold | best |
| **Cloud via Ollama (`glm-5.3-flash:cloud`)** | **0.73–0.99s** | EXCELLENT — sub-second, no API key, already proven as dispatch lane |
| Box CPU (llama-swap, tiny prompt) | **24.6s** round trip | useless for interactive routing (CPU prefill ~11 tok/s) |
| Mac (tailscale) | not measured here | viable if it runs Ollama; adds network RTT ~5-30ms + cold load |

**Design: classifier placement ladder (phase 2 feature, config-driven):**
1. Local GPU if free (probe: nvidia-smi free VRAM >= threshold, model cached)
2. Else: any peer machine running the classifier (health-check endpoint, `:cloud`
   not needed — any Ollama host on the tailnet)
3. Else: cloud classifier (Ollama `:cloud` models — measured ~0.8s, adds ~0.7s vs local)
4. Never the CPU-only box for interactive routing (24.6s tiny-prompt floor).

The check itself ("scan my hardware, pick the free one") is a cheap local operation
(<100ms with cached probes); the offload decision adds NO latency when the local GPU
is free, and ~0.7s when falling back to cloud. This directly serves Gui's multi-machine
users (Windows + box + Mac + cloud).

## 4. Product framing
- Default: classifier on local GPU, unloads after 5 min idle (GPU-friendly).
- Multi-machine tier (enterprise or power-user config): classifier placement ladder +
  health checks; box stays an EXECUTION lane only, never the interactive classifier.
- Cloud classifier ~0.8s: still sub-second; acceptable fallback, matches the
  enterprise "cloud classifier" bundle already in the spec.

## Artifacts
- Measured this session on RTX 5070 Ti / Ollama; box via llama-swap v253.
