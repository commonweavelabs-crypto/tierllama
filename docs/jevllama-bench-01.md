# Jevllama Classifier — First Real Benchmarks (qwen3 via Ollama)
#project/jevllama #benchmark

> 2026-09-21, live runs on Gui's Windows machine (RTX 5070 Ti, Ollama 127.0.0.1:11434).
> Golden mini-set: 8 labeled video-app routing messages. This is directional data (n=8),
> the full golden set (100+) comes next.

## Setup evolution (what we learned live)
- qwen3 emits a hidden 'thinking' field even with /no_think in raw generate -> thinking
  chains of 200-600 tokens = 0.5-84s calls. FIX: /api/chat + think:false.
- First-token is often a newline -> naive first-word parsing fails. Enum-constrained
  structured output (format enum) is the Ollama equivalent of SemIf's logit read.
- Cold load dominates first call (84s CPU load on 0.6b; model stays warm after).

## Results (chat API, think:false, enum-constrained JSON)
| Model | Accuracy | Avg latency (warm) |
|---|---|---|
| qwen3:0.6b | 4/8 (50%) | 0.14s |
| qwen3:4b   | 6/8 (75%) | 0.20s |

Failures at 4B: "Plan the render sequence" -> NAVIGATOR (expected DIRECTOR, close but
wrong), "structure a 90-second short" -> TEACHER. Both plausibly fixable with a
better rubric prompt - the prompt was bare (no role definitions). NEXT: rubric prompt.

## Multi-dimensional routing (the Jevllama decision shape) - 4B, works
- "Rewrite docs for 13 routes, no rush, overnight" -> {MEDIUM, LATER} @ 0.45s ✓
- "App crashing right now, user waiting" -> {EASY, NOW} @ 0.23s (difficulty arguable)
Two dimensions in ONE call, sub-half-second, enum-locked. The router core works.

## Implications
- Latency is a NON-ISSUE: 0.1-0.5s per decision via plain Ollama chat (SemIf's
  logit-read would be even faster + gives real probabilities, not just argmax).
- Accuracy needs the rubric + real probabilities (SemIf) + bigger golden set before
  trusting thresholds. 0.6B is NOT good enough for classification (50%).
- GPU contention check pending: model stays loaded; 4B ~2.5GB VRAM alongside ComfyUI.


## Round 2 results (same 8-msg set, same machine)
| Model | Bare prompt | With role rubric | Rubric latency |
|---|---|---|---|
| qwen3:0.6b | 4/8 (50%) | not tested (ruled out) | — |
| qwen3:4b | 6/8 (75%) | **8/8 (100%)**, reproduced at temp=0 | 0.20-0.44s |
| qwen3:8b | 4/8 (50%) — WORSE than 4B bare | 7/8 (88%) | 0.13-0.56s |

## THE HEADLINE: the rubric is the model
Bigger did NOT mean better (8B was worse than 4B with the bare prompt). Quality came
from the ROLE RUBRIC (one line per role defining scope). 4B + rubric = 8/8 twice,
0.2s per decision. This is a prompt-engineering result, not a params result.

## Hardware footprint (Gui's 6GB-RAM question)
- 4B model = 2.5GB weights, needs ~3GB VRAM/RAM. Works on machines with 6-8GB free.
- 0.6B = 522MB (but 50% accuracy - NOT viable as classifier).
- With 4B + 8B BOTH loaded + ComfyUI-era desktop usage: 11.8/16.3GB VRAM on 5070 Ti.
  Router-only machines need just the 4B (~3GB).
- Enterprise cloud classifier = TypeSafe (waitlist) or a bigger cloud model via enum
  JSON - same interface, bundled as enterprise convenience feature (Gui's idea, sound:
  multi-machine fleets get one consistent classifier without local hardware).

## Next
1. Full golden set (100 messages, labeled by me + spot-checked by Gui).
2. SemIf-style true logit probabilities (confidence thresholds need real numbers,
   not just argmax) - via llama.cpp logprobs or SemIf scorer on the 4B.
3. Box queue as 4th lane integration test.


## The value of accuracy points (Gui's question: does 88% vs 100% matter in $?)
Real tier prices (Ollama cloud, verified live 2026-09-21): local easy $0 |
gpt-oss:20b $0.07/$0.30 | deepseek-v4.1-flash $0.15/$0.60 (MED) | kimi-k3 $3.00/$15.00 (HARD).
Mix 60/25/15, 4:1 in:out, half of easy on local:
- Always-hard baseline: $6.00/M tok blended.
- Tiered (correct routing): ~$1.00/M tok = 83.3% savings, ~$4,996 saved per BILLION tokens.
- 12% misroute rate (8B-classifier scenario, 4x cost per misrouted task via wrong
  tier/retries): effective $1.37/M = 77.2% savings, ~$4,635/B tok.
- DELTA between 88% and 100% classifier: ~$360 per billion tokens (~6 margin points).
Verdict: accuracy points are worth real money at scale, but the rubric got 4B to 100%
at 0.20s - the cheap 4B is the product default; 8B's extra points don't justify 2x memory.
Enterprise cloud classifier (TypeSafe/bigger cloud model) = convenience tier (Gui's idea).

## Market scale anchors (for the margin model)
- Ollama: 52M monthly downloads (search snippet, UNVERIFIED - page 404'd).
- Ollama cloud pricing VERIFIED: Pro $20/mo ($60 credits), Max $100/mo ($300), Team
  $500/mo ($1,000 shared credits), Enterprise custom. The neighborhood Jevllama's
  enterprise tier competes in - and none of these plans route intelligently.


## Full golden-set run (n=120, live, 2026-09-21)
Golden set: 120 labeled messages across 5 roles (25/23/30/20/22), 3 difficulty tiers,
NOW/LATER timing, incl. 20 ambiguity traps ('hi', 'you know what to do', 'just do the
next obvious step'). Data: scratch/golden_set.json (promoted to repo below).

| Rubric | Accuracy | Avg latency |
|---|---|---|
| v1 (basic roles) | 86.7% | 0.196s |
| v2 (+vague->DIRECTOR) | 82.5% | 0.178s |
| v3 (+estimate disambiguation) | 85.0% | 0.215s |

**Winner: rubric v1 (86.7%).** v2/v3 taught: over-specifying rules causes overcorrection;
the model trades one confusion for another. Prompt iteration has diminishing returns.

## The architecture insight (confirms the original design)
The residual misses are AMBIGUOUS commands ('review my project end to end and fix what's
wrong' - bug_reporter or director?) - exactly the messages the M-F router design sends
to the FALLBACK chain (main LLM decides). The classifier doesn't need to solve ambiguity;
it needs to recognize it. That's what SemIf's true probabilities (vs argmax) will give us:
low max-probability = escalate. Accuracy on clear-cut messages is near-perfect.

## Updated verdict for the product
- qwen3:4b + rubric v1: 86.7% @ 0.2s locally, free. Good enough for the MVP router with
  confidence-threshold fallback to the main LLM.
- Path to >95%: SemIf logit probabilities -> confidence gating -> ambiguous to fallback.
- 8B adds latency, not accuracy (88% on 8-msg set vs 4B's 100% there - noise at small n,
  and on the 120-set it's not worth re-running until SemIf probabilities are in).


## J2: logprob classifier (SemIf-style, 2026-09-21)
Ollama's OpenAI-compat /v1/chat/completions supports logprobs + top_logprobs. Assistant
prefill ("ROLE:") forces the first token to BE the role word; top-20 logprobs merged into
a role probability distribution. Self-reported confidence PROVEN junk (all 120 msgs
self-report 0.95+; actual acc 91.7%). Logprob classifier: **94.2% @ ~80ms warm** (up from
91.7%), 98% coverage. BUT: residual errors are CONFIDENT errors (p_top=1.0 when wrong) -
confidence doesn't discriminate the ambiguous tail. Defense = escalation ladder (J4):
retry-with-rephrase, 2nd-pass verification. Threshold gate kept at 0.75 (harmless).
Committed in tierllama repo. Shipped: classifier.py v2 (dual-endpoint: /v1 for logprobs,
/api/chat for dims).
