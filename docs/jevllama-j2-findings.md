# J2 Findings — Confidence Calibration & Logprob Classification (technical)

**Date:** 2026-09-22 | **Project:** Tierllama (working name Jevllama) | **Status:** J2 complete
**Setup:** qwen3:4b via Ollama on RTX 5070 Ti; 120-message golden set (5 roles, difficulty,
timing, incl. 20 ambiguity traps); OpenAI-compat /v1/chat/completions + /api/chat endpoints.

## Finding 1: Self-reported confidence is unusable (calibration failure)

Method: full 120-set through the enum-constrained classifier recording `*_conf` per
dimension; bucketed self-confidence vs measured accuracy.

Result: **all 120 messages self-report role_conf >= 0.95** (single bucket, zero spread)
while measured accuracy is 91.7%. There is no correlation between the verbalized
confidence and correctness. Same pattern for difficulty/timing confidences.

Interpretation: chat-model verbalized confidence is a style artifact of RLHF-style
training, not a probability estimate. This matches known LLM overconfidence literature.
Implication: any architecture that gates on the model's self-reported confidence is
building on a void signal. We did exactly that in the J1 draft (fallback gate at 0.75
on self-report) — the gate was effectively never going to fire.

## Finding 2: Token logprobs ARE usable — SemIf-style logit read works on Ollama

Method: Ollama's OpenAI-compat endpoint honors `logprobs: true, top_logprobs: N`.
Assistant prefill ("ROLE:") forces the first generated token to be the role word; the
top-20 token distribution at that position IS the role distribution. Multi-token roles
(DIRECTOR, SCREENWRITER, BUG_REPORTER) require merging top_logprobs across the first 2-3
tokens, tracking prefix probability mass.

Result: **94.2% role accuracy @ ~80ms warm** (vs 91.7% enum-constrained), 98% coverage.
Shipped as `tierllama/classifier.py` v2 — dual-endpoint: /v1 for logprob roles, /api/chat
for difficulty/timing dims.

## Finding 3 (negative result): confidence does NOT discriminate the error tail

Method: threshold sweep on p_top (logprob-derived argmax probability).

Result: residual errors (7/120 = 5.8%) are **confident errors** — p_top = 1.0 even when
wrong. Calibration of the logprob signal is also saturated: threshold sweeps from 0.5 to
0.99 keep 98% of messages with no accuracy change. Miss taxonomy:
- 4/7 over-routed to DIRECTOR ("Run the workflow with the new slot values" → DIRECTOR)
- 2/7 TEACHER-vs-BUG_REPORTER boundary ("Why is my render slower than the estimate?")
- 1/7 ambiguous executive command ("review my project end to end...")

Interpretation: qwen3:4b argmax is near-deterministic on this prompt; a single forward
pass does not encode "I'm unsure". Confidence-gating as the ONLY ambiguity defense is
dead. Defense must be architectural: escalation ladder (J4) — retry-with-rephrase,
second-pass verification, or an N-sample agreement check (sample k times, if
disagreement > x → escalate). The ambiguity traps in the golden set were designed to land
exactly here; the designed fallback path covers them.

## Finding 4: few-shot examples >> rule elaboration (carried from J1, confirmed)

Five prompt iterations: rule-tuning plateaued 85-90%; 13 example routings (few-shot)
jumped role accuracy to 100% on the 20-message live set / 91.7-94.2% on 120. Difficulty
calibration remains the weak dimension (MEDIUM-hedging); those errors cost one lane
(EASY vs MEDIUM = $0 vs $0.15/Mtok) — cheap errors, acceptable at MVP.

## Artifacts
- `tierllama/` repo: classifier.py v2 (logprob + dims), config.py (v1_endpoint), router.py, cli.py
- Calibration data: scratch/j2_calibration.json, scratch/j2_logprobs_full.json
- Bench history: jevllama-bench-01.md (0.6B/4B/8B ladder, rubric v1-v3, J1, J2)
- Golden set: 120 messages, 5 roles, labeled — promoted in repo

## Plain-language version (for video/blog)
See: `tierllama/docs/J2-FINDINGS-PLAIN.md` (repo) — "The model that's always sure of itself".
