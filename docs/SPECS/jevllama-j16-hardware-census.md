# J16 — Hardware census & worker-class fit (feeds J13 v2)
#project/tierllama #spec #j16

> Status: DRAFT for Gui approval. 2026-09-24. Answers Gui's clarification:
> users don't have "the box" — they have THEIR hardware, and Jev needs it
> categorized into worker classes. Spec-first, grounded in current code.

## What already exists (verified — Gui is not stressing over nothing, but
most of this is DONE)
1. **Discovery** (J5, `discover.py`): scans the LAN (~6s /24), finds every
   Ollama/llama-swap host, lists each host's models. EXISTS.
2. **Per-model bench** (J8, `bench.py`): unload -> EASY/MEDIUM/HARD probes ->
   `cold_load_s`, `tok_s`, easy/medium/hard_pass -> two knobs:
   `timing_fit` (NOW if tok/s >= 40 or (>=20 & cold<15s), else LATER) and
   `max_fit` (EASY..HARD, UNRELIABLE). 24 measured entries exist.
   EXISTS — but see Gap A.
3. **Recommendation matrix** (`seed.py recommend`): per tier pick best model,
   measured overrides seed, price/quality modes. EXISTS (J8/J10).

## The gaps (what J16 adds)
**Gap A — machine dimension missing from bench data.** bench.jsonl keys by
model only; the docstring promises model@machine but records don't carry the
host. Two benches of the same model on different machines are indistinguishable.
Fix: bench key = model@host; host discovered via discover.py + probe /api/tags.

**Gap B — worker CLASS missing.** timing_fit/max_fit classify the MODEL.
J13 needs the machine classified: workhorse / always_on / night_only /
cloud_scheduled. Derived from measured knobs + ONE user question per machine
("is this the machine you work on?"). Never guess a workhorse: actively-used
machines are detected by interaction (user-agent activity) + confirmed by user.

**Gap C — model@machine pairing quality.** Gui's box = 4GB-class hardware
running a 27B IQ3_S: slow but quality overnight work. The category is the
PAIR (hardware + model), not hardware alone — bench already measures the pair,
it just doesn't LABEL the pair. J16 labels each pair with
{timing_fit, max_fit, tok_s, cold_load_s} -> J13 worker classes:
- pair NOW-fit + HARD-capable on user's daily machine -> workhorse
- pair LATER-fit + HARD-capable -> always_on or night_only (user picks)
- cloud models -> cloud_scheduled (cost display from J13 v2)

**Gap D — hardware×model RECOMMENDATION (future, Gui's brainstorm).**
"Will this model run well on this machine?" — public communities exist for
this; v1 answer = our own bench (measure, don't guess). A recommendation
engine pre-purchase is POST-J16 (J17 candidate) and needs community seed data
(opt-in telemetry flywheel, already roadmapped).

## Best-practice shape (tangible, simple)
`machine_profile = {host, name(user-given), class(user-confirmed), windows,
pairs: [{model, timing_fit, max_fit, tok_s, cold_load_s}]}` — one JSON per
machine in logs/fleet/. The J13 scheduler reads ONLY machine_profile; the
bench produces the pairs; discover finds the machines. Three modules, three
files, one direction of data flow. No new daemons.

## Non-goals
- No GPU-vendor APIs / wmi deep-dives: Jev's lanes only need tok/s + pass/fail
  + user-confirmed role. Deeper hardware inventory = not needed for routing.
- No auto-categorization without consent (J10 consent pattern applies).
