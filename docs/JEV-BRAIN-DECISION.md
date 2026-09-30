# Jev Brain Decision Record — why qwen3:8b

**Date:** Sep 30, 2026 · **Status:** ACCEPTED (set in stone with Gui, after full test data)
**Decided by:** Gui (operator) + Hermes (bench data) · **Scope:** Tierllama's router brain — classifier (prompts) + matcher (rated models to jobs)

---

## What is Jev? (the name question, resolved)

Jev is **not a set of model weights** — it is a **job description**:

> A small local brain that reads a question and outputs a **number-based verdict**,
> and we never trust the words — we trust the **token probabilities**.

Any small local model *doing that job* (same rubric discipline, same logprob
verdict reads) is a **Jev-class brain**. gemma3:12b was never a "replacement"
for Jev — a model doing the classify job is being Jev. The branding
"**powered by Jev**" refers to the architecture, not a weight file.

**Terminology (Gui, adopted):** Jev **classifies** prompts (easy/hard × now/later).
Jev never "rates" models — models are **already rated by measured data** (bench
tok/s, capability floors, prices). Jev **matches** a rated candidate to a job,
often *descriptor-blind* (no model names — just the numbers). Verified: capable
brains match correctly without names; names add anchoring bias, not signal.

## The experiment trail (all data in `tests/`, commits ba18dc7 + 400e467)

| candidate | classify (diff/timing/exact) | match rated models | med speed | verdict |
|---|---|---|---|---|
| qwen3:4b | 74.6 / 91.4 / 67.9 (n=209) | **CANNOT** — echoes ADEQUATE to everything; blind+think: loops re-reading the problem | — | dead |
| **qwen3:8b** | **78.1 / 87.5 / 71.9** (n=32) | **4/5** (1 miss = borderline 61s-vs-60s call) | **2.0s** | **WINNER** |
| gemma3:12b | 75.0 / 90.6 / 68.8 (n=32) | 3/3 clean probes | 3.0s | quality fallback |

Key falsifications along the way:
- **arm v1 p=0.00 everywhere** = a scoring-script bug (assistant-prefill makes
  Ollama start a NEW assistant message; first-token logprob read was empty), not
  a model property. Fixed in `tests/_onebrain_arm_v2.py`.
- **arm v2 p=1.0 ADEQUATE on everything** = the real 4b verdict: no signal.
  Tested twice, independently — not fixable by shaping the question.
- **qwen3 law (hit 3×): `think` MUST be true** and `num_predict` must be ≥1500 —
  thinking burns the budget silently and the enum-JSON path returns empty.

## Why 8b wins on EVERY axis

- **Size:** 5.23GB (Q4_K_M) — half of gemma3:12b's install, critical for users on
  laptops/slow lines: onboarding download is the #1 drop-off point in local-app UX.
- **Speed:** 2.0s median classify — fastest brain measured; Gemini-tier latency
  for the routing decision itself.
- **Accuracy:** strictly ≥ the 4b it replaces, ≥ parity with gemma3:12b.
- **Consistency/reliability:** think-mode reasoning is stable at 1500+ token
  budget; the one match "miss" in 5 probes was a defensible borderline call
  (3500 tokens @ 57 tok/s = 61s against a 60s limit).
- **License (the business axis): Apache 2.0** — verified in the model file
  itself (`/api/show`), not just web pages. Commercial use, bundling inside a
  closed-source product, redistribution, fine-tuning: all permitted, no revenue
  or user caps. This **rules out gemma3 as the default**: Gemma ships under
  Google's custom Terms of Use with a Prohibited-Use Policy attached to the
  weights. Fine to tinker with; burden to build a company on. qwen3 Max-class
  flagships are the Alibaba-custom-license exception (irrelevant to us at 8b).

## Hardware tiers (tested live, the Gui integration plan)

The feature gate is REAL and measured:
- **GPU user (8GB+ VRAM, any modern dGPU):** 8b classify ~2-5s. Full app,
  every feature, standard.
- **CPU-only / integrated-GPU user (iGPU box, no VRAM):** 8b classify **~66s**
  (2.05 tok/s effective: 205 eval + 1134 prompt tokens). Usable — for
  *interactive chat* — far too slow for a *routing* layer that gates every
  request before it's even sent.

Therefore the **two-tier gate design** (Gui's proposal, refined by data):

1. **Routing (prompt classification)** — the app's core lane-decision: needs the
   FAST brain. On constrained hardware this feature is OFF by default (fallback:
   heuristic default-tier routing, degraded but functional messaging).
2. **Model suggestions (Brain 2 / matcher + rater)** — heavier feature: gated
   behind a toggle. Toggle ON → the UI warns "this feature needs the Jev brain
   (qwen3:8b, 5.2GB download, 8GB+ VRAM recommended)" → user hits Pull →
   progress bar → digest-verify → brain swaps in **globally** (one model does
   both jobs; we never run both — simpler VRAM story, verified parity).
   Hardware check FIRST: if free VRAM < threshold, the toggle shows "Not usable
   on this hardware" instead of promising nothing or lying with "slower but ok".
   The 66s measurement is why honesty beats "just let it run".

Data keeps accruing (real-traffic ledger feeds calibration each milestone); a
future finding that 66s shrinks with quantization (q4→q3) or prompt-trim could
reopen the CPU tier — numbers, not vibes, decide.

## Packaging doctrine (how the dependency ships)

- **Weights NEVER live in the repo.** No 5GB blobs in git, ever.
- Onboarding = **doctor-first**: `doctor.py` checks Ollama installed+running →
  checks `qwen3:8b` present AND digest-matched → if missing, `ollama pull
  qwen3:8b` with live progress. Pull comes from Ollama's registry (which
  mirrors Hugging Face) — one command, resumable, deduped.
- **Pin by digest** (current: `500a1f067a9f…` full hash in config): users get
  the *verified* brain, not registry-drift. Upgrades = digest bump + changelog;
  never force-update (our own Ollama-updater trauma generalized: pin > drift).
- License compliance: repo carries the Apache-2.0 notice file; we don't
  re-distribute weights, we *reference* the official pull — cleanest posture
  Apache 2.0 allows.

## What we keep as fallback

- gemma3:12b stays a *documented fallback* (quality king at matching; also
  Apache-unencumbered via Gemma 4's Apache relicense — check per release).
- qwen3:4b stays in the repo history as benchmarked evidence of the small-model
  floor ("why not smaller? — because it cannot match at all, proven 2×").
- The 4b CAN classify acceptably (74.6/91.4) and could serve a
  classify-only Lite mode someday — documented, not built, not promised.