# J13 — Jev Scheduler (the 4th dimension: WHEN)
#project/tierllama #spec #j13

> Status: DRAFT for Gui's approval. Written 2026-09-24, grounded in the live
> code (proxy.py / router.py / adapters.py / config.py / webapp.py + the mini-box
> queue). No implementation before Gui approves the scope.

## Problem
Today Tierllama routes WHAT work is and HOW URGENT it is (difficulty x timing),
but timing is binary: NOW or LATER (BOX). "do this by Friday" collapses into
"queue it sometime" — the deadline is thrown away. J13 keeps it: a job with a
deadline lands ON its deadline, on the cheapest capable lane.

## Design (System One philosophy: Jev decides, dumb code schedules)

### 1. Classifier gains a 4th dimension: WHEN
- Same one-pass enum-constrained call as difficulty/timing (adds one key to the
  JSON schema; ~same latency; still ~free)
- Output: `when` = one of:
  - `NOW` (default — no date mentioned)
  - `DEADLINE` (a concrete date/time exists: "by Friday", "before Monday 9am",
    "end of month")
  - `DEFERRED` (explicit defer, no date: "overnight", "whenever", "no rush")
  - `DATE_UNCLEAR` (date-ish words but ambiguous: "soon", "this week?", "later today")
- Plus `when_confidence` + `when_raw` (the extracted date phrase, for UI display)
- IMPORTANT: DEADLINE still needs the date resolved to an absolute due_at.
  Resolution is DUMB CODE (no LLM): regex/duckling-style parse of when_raw
  against the current date. If parse fails -> treat as DATE_UNCLEAR.

### 2. Clarify-or-ask rule (never silently guess a date)
- when_conf >= 0.85 AND due_at parsed -> schedule
- when_conf < 0.85 OR parse failed -> the response carries
  `"needs_clarification": {"field": "when", "raw": "friday?", "guess": "<best guess due_at>"}`
  The caller (UI) shows: "Did you mean Friday Sep 25, 17:00? [Schedule] [Now] [Pick date]"
- Guesses are displayed, never executed silently. This is the same
  confidence-threshold pattern as FALLBACK routing (config threshold 0.75).

### 3. The scheduler is a plain file-backed queue (NOT an LLM)
- `logs/schedule.json` — append-only list of
  `{id, created_at, due_at, lane, message, status: pending|due|dispatched|done|failed, tries}`
- A `scheduler.py` loop (thread inside webapp; also runnable standalone
  `python -m tierllama.scheduler`): every 30s, move due jobs pending->due,
  dispatch via existing `adapters.dispatch(lane, ...)`, mark done/failed
- Retry policy (boring): 3 tries on failure, then park `failed` (mirrors box
  worker behavior)
- BOX lane synergy: box jobs already flow C:/jobs/pending/*.json (15s poll,
  SMB). J13 schedules the DROP TIME: scheduler holds the job until due_at,
  then drops it into the box queue (SMB) or dispatches to LOCAL/CLOUD lanes.
- Persistence: JSON file, append-only + compaction on load (no DB — matches
  project's zero-dependency posture)

### 4. lane_for() gains a WHEN input (backward compatible)
```
lane_for(difficulty, timing, confidence, when=None)
# NOW -> existing behavior
# DEADLINE -> difficulty picks the lane; job enters scheduler with due_at
# DEFERRED -> BOX as today (overnight default)
# DATE_UNCLEAR -> dispatch NOW + needs_clarification surfaced
```
Existing golden-set behavior unchanged: when=None reproduces current lanes
exactly (regression runner must stay green).

### 5. Webapp (J11 dashboard): new "Scheduler" tab
- Upcoming jobs (due_at sorted) + status badges + due-in countdown
- Clarification inbox: jobs with needs_clarification get Schedule/Now/Pick-date
- API: GET /api/schedule (list), POST /api/schedule/resolve (confirm/override
  a guessed due_at), DELETE /api/schedule/{id}
- No cron syntax exposure — human language in, date chips out

## Golden set extension (J13 gate, measured as always)
- Extend tests/golden_set_v1.json with ~15 WHEN-labeled cases (5 DEADLINE,
  5 DEFERRED, 5 DATE_UNCLEAR/ambiguity traps) -> v2 set (62+15=77)
- New scorecard dimension: when accuracy + clarify-precision
  (low-conf cases correctly flagged, never silently guessed)
- Floors for J13 set AFTER baseline measurement (no floors guessed upfront;
  J12 lesson: measure first, then lock)

## Non-goals (explicit)
- NOT a general cron (no recurring jobs in v1 — "every Monday" is DATE_UNCLEAR
  until demand exists)
- NOT an LLM loop — the scheduler never calls a model to decide scheduling
- NOT touching J14 outcome signals (separate milestone, composable later:
  failed jobs re-scheduled instead of retried immediately)

## Implementation order (after Gui approves)
1. config: WHEN enum + thresholds (when_conf 0.85)
2. classifier: 4th dim in the same constrained-JSON call; unit smoke
3. scheduler.py: file-backed queue + due loop (pure stdlib)
4. lane_for + router: wire WHEN (golden set must stay green)
5. webapp: /api/schedule* + Scheduler tab (J11 tabbed UI)
6. golden set v2 (77) + scorecard + floors + findings doc
7. commit/push per milestone, verify live end-to-end with a real "by Friday" job

## Risks
- Date parsing edge cases (timezones, "next Friday" vs "this Friday") —
  mitigated by clarify-or-ask; we NEVER guess silently
- LLM latency: 4th dim adds tokens to the constrained JSON (~same single call)
- Scope creep: v1 = one-shot jobs only. Recurring schedules = future J-item.
