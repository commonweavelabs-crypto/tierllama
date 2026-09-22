# J4 Findings — Escalation Ladder (technical)

**Date:** 2026-09-22 | **Status:** J4 complete
**Setup:** `tierllama/ladder.py` wired into `router.route()`; every dispatch failure now
runs the ladder; every step recorded in the decision log (separate `escalation` events
+ inline trace on the record).

## Ladder design (as built)
1. **Retry on same lane** (2 attempts): cheap; covers transient errors (404s on
   restarting models, timeouts).
2. **Retry-with-rephrase reclassification** between attempts: re-ask the classifier
   with the logprob path (J2) — catches "the phrasing confused it" cases without
   paying a stronger model.
3. **Lane escalation**: LOCAL → CLOUD_MEDIUM → CLOUD_HARD (order = cost ladder).
4. **Final fallback**: FALLBACK lane (main LLM; cloud-medium stand-in until J5).
Adapters never raise (J3 finding) — failures are data the ladder reads.

## Live acceptance (forced failure)
Broke the LOCAL lane's model name deliberately → routed "hi":
- attempt 1 LOCAL → 404 (0.02s) → rephrase_reclassify (TEACHER, p=1.0) → attempt 2 →
  404 → **lane escalation LOCAL→CLOUD_MEDIUM** → served in 2.09s. **End-to-end 2.9s.**
- Decision log recorded all 5 escalation steps with triggers + outcomes.

## Finding 1: escalation adds seconds only when it must
Clean routes pay ZERO ladder overhead (no extra calls). The forced-failure route paid
2.9s total — two 0.02s failed probes + one reclassify + one real cloud call (2.09s).
The ladder's cost = the failed probes' milliseconds, not the escalated lane's latency.

## Finding 2: the designed-ambiguous case needs NO escalation
"Review my project end to end and fix what's wrong" (the J2 miss case) routed
CLOUD_HARD on the first try with the final rubric — the ambiguity resolved upward by
the classifier itself. Escalation is for ERRORS; ambiguity is increasingly handled at
classification (rubric v6). Confidence-gated fallback stays wired but the gate rarely
fires with logprob p_top saturated — retry-with-rephrase is the live defense.

## Finding 3: latency reality of full runs
End-to-end escalated route: 2.9s. Clean hard route: up to 37s (CLOUD_HARD cold start
through llama-swap routing). The ladder is NOT the bottleneck; lane cold starts are
(J5 keep_alive tuning + "model is waking up" UX).

## Artifacts
- ladder.py (retry → reclassify → escalate → fallback; every step logged)
- router.py rewired clean (dispatch failures escalate; dispatch=False = log-only mode)
- Decision log: escalation events as first-class records
