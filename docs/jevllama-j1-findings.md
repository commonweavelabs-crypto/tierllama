# J1 Findings — Router Core Skeleton (technical)

**Date:** 2026-09-21 | **Project:** Tierllama (working name Jevllama) | **Status:** J1 complete
**Setup:** qwen3:4b via Ollama; 120-message golden set (5 roles × difficulty × timing,
incl. 20 designed ambiguity traps); router skeleton = classifier + 4 lanes + decision log
(append-only JSONL with ts, message, role/difficulty/timing + per-dim confidence, lane,
latency).

## Finding 1: Rule elaboration plateaus — few-shot examples break through

Prompt-iteration ladder (same 120-message set where comparable, 20-msg live set for finals):

| Prompt version | Role accuracy | Notes |
|---|---|---|
| v1 rubric (role definitions only) | 86.7% | 16 misses; DIRECTOR under-routed (estimates/schedules → TEACHER) |
| v2 (+ "vague → DIRECTOR" rule) | 82.5% | overcorrection: swallowed creative/editing asks |
| v3 (+ estimate disambiguation) | 85.0% | rules traded one confusion for another |
| v4 (balanced rubric) | 90.0% (20-set) | role fixed; difficulty collapsed to MEDIUM-hedging |
| v5 (big rules block for difficulty) | 75.0% (20-set) | LONGER prompts ≠ better; regressed role |
| v6 (+ 13 few-shot example routings) | 95% (20-set) | **the lever** |
| final (v6 persisted) | **100% (20-set), 0.46s avg** | acceptance run |

Lesson (twice-confirmed): **adding worked examples beats adding rules.** Over-specified
rule text causes overcorrection; the model trades one confusion class for another. Prompt
iteration alone has diminishing returns — measure per version, keep the winner.

## Finding 2: Difficulty is the weak dimension (MEDIUM-hedging)

Difficulty accuracy ranged 50–85% across prompt versions while role reached 90–100%.
The model anchors on MEDIUM as the hedge class. Errors are mostly ONE-lane slips
(EASY↔MEDIUM = local $0 vs cloud ~$0.15/Mtok) — cheap errors, acceptable for MVP.
Escalation-ladder and logprob work (J2+) attack this; difficulty anchors (concrete
examples per tier) helped; self-reported difficulty confidence did not (see J2 findings).

## Finding 3: The residual misses are the DESIGNED fallback cases

Taxonomy of the 16 rubric-v1 misses: ambiguous executive commands ("review my project
end to end and fix what's wrong" → routed DIRECTOR, gold BUG_REPORTER), vague commands
("just do the next obvious step"), TEACHER/BUG boundary ("Why did my scene format fail?").
These are the inputs the M-F router architecture intentionally routes through a fallback
chain (main LLM decides), not through the classifier's argmax. The classifier's job is
to recognize ambiguity, not solve it — confirmed by the failure modes themselves.

## Finding 4: Multi-dimensional scoring in one call works

Single constrained-JSON call returning {role, difficulty, timing} + confidences ran at
0.14–0.2s warm with no cross-dimension accuracy penalty in the J1 acceptance config.
(Separate note: the 3-dim one-call scored WORSE than single-dim in early tests — fixed
by the few-shot rubric; keep the rubric + examples in every call.)

## Finding 5: Latency budget holds

Live router end-to-end (classify → lane decision → JSONL log write): 0.46s avg incl.
classifier call on 5070 Ti / qwen3:4b. Well under the sub-second interactivity budget;
classifier alone ~0.2s; logprob path (J2) ~0.08s.

## Artifacts
- `tierllama/` repo: config.py, classifier.py, router.py, cli.py, README; git history ffa95db+
- Golden set: 120 messages labeled (role/difficulty/timing), 20-msg live acceptance set
- Decision log: logs/decisions.jsonl (per-record full schema)
- Bench history: jevllama-bench-01.md (model ladder), jevllama-j2-findings.md (confidence)

## Plain-language version (for video/blog)
See: `tierllama/docs/J1-FINDINGS-PLAIN.md` — "Why we stopped writing rules and started
writing examples".
