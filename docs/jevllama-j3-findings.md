# J3 Findings — Lane Adapters (technical)

**Date:** 2026-09-22 | **Status:** J3 complete
**Setup:** dispatch layer (`tierllama/adapters.py`) wired into `router.route()`; every
routed message now EXECUTES on its lane and records the dispatch result in the decision
log (status, model, latency).

## Lane verification (live, one per lane)
| Lane | Model | Result | Latency |
|---|---|---|---|
| LOCAL | qwen3:4b | "J3-LOCAL-OK" | 3.0s cold / ~9-10s in end-to-end runs |
| CLOUD_MEDIUM | glm-5.3-flash:cloud | "J3-CLOUD-OK" | 2.0s standalone / 23s in run |
| BOX | job queue enqueue | job-...-j3-lane-test.md written to pending/ | 0.03s |
| CLOUD_HARD | glm-5.3-flash:cloud (stand-in) | ok | 28s |

## Finding 1: The "cloud lane" needed NO API keys — Ollama serves cloud models
Hermes's own stack already runs `glm-5.3-flash:cloud` through local Ollama's cloud
routing (provider ollama-launch, base_url 127.0.0.1:11434/v1). The J3 design worry
("stop when a cloud credential is missing") dissolved: CLOUD lanes dispatch through the
SAME Ollama server, model name carries the `:cloud` suffix. Kimi/GLM direct-API paths
remain for the enterprise tier later (config supports any OpenAI-compatible endpoint).
Zero-config cloud dispatch = a real product advantage for MVP users.

## Finding 2: Lane-model mismatches were config errors, not code errors
First run: LOCAL tried ornith-1.5:9b (not in this machine's default store -> 404) and
CLOUD tried "deepseek-v4.1-flash" (not a local Ollama model). Fix = config update
(qwen3:4b local, glm-5.3-flash:cloud cloud). Lesson: lane adapters should VALIDATE the
configured model exists (api/tags) at startup - `tierllama doctor` (J5) will do this.

## Finding 3: Latency is dominated by cold starts, not the classifier
End-to-end latencies (9-28s) are inflated by model load times (local qwen3:4b reload
after idle; cloud model cold-start through llama-swap-style routing). Classifier stays
~0.08-0.2s. For the product: keep classifier + router hot; lane execution latency is
inherent to the target model. Ollama keep_alive settings will fix most of this (J5).

## Finding 4: BOX lane semantics clarified
HARD+LATER work routes to CLOUD_HARD (sync, expensive, now), not BOX - the box lane is
for explicitly queued batch jobs, not for "hard but deferrable." Decision tree:
- timing=LATER AND difficulty!=HARD -> BOX (overnight queue, async)
- difficulty=HARD -> CLOUD_HARD regardless of timing (user is asking, answer needed)
A future refinement (J4): let the escalation ladder offer the user "queue this for
overnight instead?" when HARD+LATER is detected - saves the expensive call.

## Finding 5: dispatch never raises (J4-ready)
All adapters return {status: ok|queued|error, ...}; router records the raw result.
The escalation ladder (J4) can now read dispatch failures as an escalation signal.

## Artifacts
- adapters.py: dispatch_local / dispatch_cloud / dispatch_box / dispatch(lane, msg)
- router.py: dispatch=True by default; decision log now includes dispatch results
- config.py: LANES corrected to actual available models
- Decision log: 25 records incl. 5 live-dispatch acceptance records
