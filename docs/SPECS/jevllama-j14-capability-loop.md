# J14 — Capability feedback loop (spec)

> Status: SPEC, written 2026-09-29 from the roadmap sketch (J14 section).
>Gui-approved goal. First milestone turning real usage data into routing
> improvements — the loop that makes the router smarter the more it runs.

## The idea (Gui, 9/22 night)

When a model keeps FAILING on a class of prompts the classifier labeled
EASY/MEDIUM, bump that prompt-class to a stronger tier — gradually, per class,
never globally. And the reverse (Gui's downgrade idea): occasionally send
HARD-labeled work down a tier as a canary; if the output is usable, promote
the class.

## What already exists (verified in repo, 2026-09-29)

- J4 escalation ladder (HARD fail -> EXPERT retry at higher thinking) — this
  is REQUEST-level rescue; J14 is CLASS-level learning. Complementary.
- dispatch retry logic in adapters.py
- per-call logs (proxy.jsonl / decisions.jsonl) — but NO outcome field
- J16 machine profiles + model@host bench keys — the ledger keys on these

## The five pieces (roadmap) -> implementation

### 1. Outcome signal (tierllama/outcomes.py)
MVP truth sources — nothing semantic (no "was the answer good" judging;
that's J14 v2 / telemetry flywheel):
- `failure` (automatic): HTTP error on dispatch, or empty content, or
  exception in the adapter
- `failure` (user): explicit retry-within-session of the same message
- `success` (automatic): dispatch returned status ok with non-empty content
  AND no user retry followed
- `unknown`: anything else (never guessed)
Record shape: {ts, model@host, lane, difficulty, timing, when, outcome,
latency_s, reason}. Appended to the dispatch record + decisions.jsonl.

### 2. Capability ledger (tierllama/capability.py)
Per key `(bench_key, difficulty, timing, when)` = model@host x prompt-class:
rolling stats — failure_rate, avg_latency_s, sample_count. Prompt-class is
keyed by CLASSIFIER DIMENSIONS ONLY (no embeddings, no NLP — stdlib tuple;
J14 v2 may add clustering). Storage: logs/capability.jsonl events + in-memory
rolling window (last N=100 events per key, configurable). Feeds bench.py
(read side: ledger stats can annotate bench output).

### 3. Gradual bump rule (in capability.py)
N consecutive failures on class X (same model@host + difficulty) -> tier += 1
FOR THAT CLASS ONLY. J15's collision guards honored (from the roadmap):
- cooldown: no second class move within CAPABILITY.cooldown_h (12h)
- rate: max 1 tier move per class per day
- minimum samples before any move (CAPABILITY.min_samples = 10)
- never global: only the failing class's tier changes, only for routing
  decisions that consult the ledger (see #5 gate)
BETA gate: CAPABILITY.enabled = False. OFF = the bump logic computes but
NEVER changes routing (pure ledger math; dry-run by design).

### 4. Canary probes (Gui's downgrade idea)
Sample CAPABILITY.canary_pct (default 0) of HARD-classified traffic to the
tier below. Promotion rule: usable output (graded by the same probe grading
style as bench.py — deterministic checks where possible) N times
(capability.canary_successes = 3) -> promote that class one tier DOWN.
Consent-gated: canary_pct=0 while gated; UI-flagged; never silent (canary
attempts are logged in the decision log with canary=true).

### 5. UI (dashboard)
Capability panel (on the Overview tab or its own): per-class stats table,
bump/promotion events with reasons, the CAPABILITY gate toggle with honest
copy: "OFF: routing never changes on its own."

## J15 boundary (do NOT build here)

J15 = MODEL-level reputation (demote a model across ALL users). J14's ledger
is the data source J15 will consume, so: keep ledger records model-scoped and
timestamped (J15 needs long-window aggregate rates — separate clock from
J14's streaks). The J15 conflict analysis (runaway loop class-bump x model-
demote) is already in the roadmap; J14's guards (cooldown, rate, min-samples)
are the class-side of that design.

## Non-goals (v1)
- No semantic outcome judging (user thumbs up/down = J14 v2 / telemetry)
- No embedding-based prompt clustering (J14 v2)
- No cross-user aggregation (J15's territory, needs telemetry consent)
- No automatic tier DEMOTION of the classifier's own difficulty label

## Risks
- Runaway loop (J15 analysis): mitigated by cooldown + rate + min-samples +
  the gate being OFF by default. If live data shows oscillation, the gate
  stays OFF until J15's full guard set lands.
- Cold-start: new models/classes have < min_samples -> no bumping happens
  (by design; the ledger just accumulates honestly).