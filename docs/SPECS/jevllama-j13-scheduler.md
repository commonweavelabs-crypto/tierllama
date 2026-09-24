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

## Beta feature policy (Gui, 2026-09-24 — REQUIRED framing)
- J13 ships as a **BETA feature, OFF by default**. No silent enablement: the
  user must knowingly toggle it on, and the UI states plainly what beta means
  here (untested across use cases; date parsing will miss; schedules may need
  manual fixes). Config: `SCHEDULER = {"enabled": false, "beta": true, ...}`;
  the dashboard tab shows a BETA badge + the honest warning while enabled=false
  shows "beta feature - turn on in settings" instead of the UI.
- Rationale: date ambiguity in the wild is unbounded; we've tested 15 synthetic
  WHEN cases, not the 90%-NOW reality of real users; rescheduling heuristics
  (priority shoving) WILL need tuning on real usage.

# Gui's brainstorm 2026-09-24 (documented verbatim-intent, verbatim lessons)

## Insight 1: "later" is not only user-stated — it's PHYSICS-driven
The "recreate the whole universe" case: the router sent it to LATER and was
RIGHT, but for a different reason than the user's wording. Jobs exist that are
"later by nature": the hardware can't do them in the NOW window (minutes/hours),
regardless of what the user asked for. So WHEN has two sources:
- USER-timed: "by Friday" (intent)
- PHYSICS-timed: estimated duration > NOW window (reality)
v1 J13 covers user-timed. PHYSICS-driven timing = the LONG-HORIZON class below.

## Insight 2: LONG-HORIZON jobs need an ask-before-commit gate
Big-scope jobs occupy the machine for hours (they'd occupy Hermes/main agent
24h+; or route to EXPERT frontier models at cost). Before committing, ask the
user: "This looks like a long job (est. ~Xh). Start now and tie up this
machine, route to your overnight box so your day machine stays free, or pick
another resource?" Options surfaced: all user hardware + cloud + agents.
- MVP shape: the LONG_JOB class = scope signal (EXPERT difficulty OR estimated
  duration > 30min) triggers needs_clarification with resource options,
  instead of silently hogging the machine.

## Insight 3: user-defined NIGHT WINDOWS per machine
"By Friday" should be scheduled into the previous nights, inside the user's
night window. Hardware profile in config: a workhorse machine (busy by day) +
night workers (box now; main Windows PC could be opted in later). Settings UI:
which machines work overnight, window start/end (e.g. 00:00-08:00). "By Friday"
= fill night windows between now and the deadline; jobs with 4-5 days of slack
fit earlier nights.

## Insight 4: capacity + priority rescheduling (PROFESSIONAL-grade needed)
- Each job needs a duration ESTIMATE (the hard part; v1 = coarse class:
  minutes/hours/overnight, refined later)
- Schedule capacity per night window; when full: "your schedule is full this
  week - make this a priority?" Priority insert SHOVES other jobs later by the
  new job's duration and tells the user which jobs moved (transparency, no
  silent eviction)

## Open source inspiration (vet before use, ideas-first per license rule)
- APScheduler (Python, BSD) — mature: job stores, executors, misfire/coalesce
  policies = the vocabulary for our due-loop and shove logic
- Prefect / Dagster — workflow engines, too heavy to adopt but their
  retries/backfill/deadline concepts are the right vocabulary
- Celery beat — scheduled tasks pattern (heavier than we need)
- Windows Task Scheduler XML / cron — for the v2 recurring-jobs shape
- We keep zero-dependency posture: v1 borrows APScheduler's CONCEPTS
  (misfire handling, coalescing, priority) in ~200 lines of stdlib, not the lib


## Golden set extension (J13 gate, measured as always)
- Extend tests/golden_set_v1.json with ~15 WHEN-labeled cases (5 DEADLINE,
  5 DEFERRED, 5 DATE_UNCLEAR/ambiguity traps) -> v2 set (62+15=77)
- New scorecard dimension: when accuracy + clarify-precision
  (low-conf cases correctly flagged, never silently guessed)
- Floors for J13 set AFTER baseline measurement (no floors guessed upfront;
  J12 lesson: measure first, then lock)

## Non-goals for v1 (explicit)
- Recurring jobs ("every Monday") — v2+ with cron-shaped concepts
- Duration ESTIMATION by the system — v1 asks the user; J14 outcome signals
  teach real runtimes over time
- Multi-user fairness — v1 is single-user; shoving fairness = v2+
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


---

## Worker classes + saturation offload (Gui, 2026-09-24 — added to spec)

Gui's box insight generalized: workers are not one class. The box is a
**full-time worker** (sits idle, rarely used interactively) that can take
HARD-but-not-EXPERT work day AND night. That's different from a workhorse
machine (busy by day, only free overnight). Worker classes per machine:

| class | meaning | example (Gui's fleet) | takes |
|---|---|---|---|
| `workhorse` | the machine the user actively uses | Windows PC (Hermes host) | NOW-window work only; night-shift opt-in |
| `always_on` | idle-capable, runs jobs any time | the mini box | EASY→HARD (NOT expert; capable but slow) |
| `night_only` | window-restricted worker | box (alt mode), main PC opted in | any lane inside its window |
| `cloud_scheduled` | offload target when locals saturate | user's configured cloud models (e.g. Kimi K3 for later-expert) | HARD→EXPERT |

**Saturation → offload toggle (per user, OFF by default, part of beta):**
when a worker class keeps shoving (hits the weekly shove cap), the scheduler
offers/enacts offload: move queued jobs to `cloud_scheduled` overnight so the
local hardware can catch up. The UI names the target model + its $/M-token
cost BEFORE moving anything ( Gui: "we'll schedule it for KimiK3 — $X per M
tokens"). Nothing moves without the cost shown.

**LONG-HORIZON gate (refined by Gui):** any job estimated >1h (or user-defined
threshold) + HARD → ask: "This will probably take over an hour. Schedule
overnight on the box?" / EXPERT → "schedule to <model> at $Y/M tokens?" —
never auto-commit. Difficulty (HARD vs EXPERT) picks the class asked about;
the user confirms the resource.

## Where this lands in the plan
- v1 (J13 beta core): deadline scheduling + clarify gate + night windows +
  manual priority shoving (shove cap 3/week + warning)
- **v2 (J13 part 2): worker classes + saturation offload toggle + cloud cost
  display.** Reason for the split: v2 depends on per-worker capacity tracking
  (real usage data) which doesn't exist until v1 runs. Gui's own framing:
  "eventually more user data from different hardware lets us extrapolate."
  v2 is where multi-user extrapolation starts.

# Pushback (anti-echo-chamber, Gui requested — 2026-09-24)

Where I'd temper or reshape the brainstorm, honestly:

1. **Duration estimation is the hardest unsolved part.** Estimating "this job
   takes hours" for an LLM task is a research problem, not an engineering one
   (we can't know a frontier model will loop for 24h on 'recreate the
   universe'). v1 should NOT estimate durations; it should ask the user
   (who often knows better) and learn from observed runtimes later (J14
   outcome signals feeding estimates = the real flywheel).
2. **Priority shoving needs transparency + a cap.** Shoving other users' jobs
   is a fairness problem when this becomes a product (multi-user later). v1:
   single-user, shove allowed, but ALWAYS list what moved and cap shoves per
   week (e.g. 3) before demanding a bigger schedule or a later due date.
3. **"Previous night" default is right for Gui, wrong as a rule.** Some users
   want the work the MORNING OF the deadline (latest useful night), others
   ASAP. v1: default = latest night window before due (max freshness of
   inputs), setting to flip to earliest. Gui's preference wins locally via
   his own setting.
4. **Scope guard for v1:** deadline scheduling + clarify gate + night windows
   + manual priority shoving IS the beta. Long-horizon resource-asking is a
   second feature (shares the clarify UI) — ship it behind the same beta
   toggle but as its own sub-toggle. Don't couple their risks.
5. **Don't build a calendar.** The schedule list is a queue with due_at, not a
   visual calendar. A calendar view is post-beta polish if users ask.
