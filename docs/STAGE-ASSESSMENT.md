# Product stage assessment (2026-09-22, end of day)

## Verdict: PUBLIC BETA (v0.9-beta) — not yet v1.0

The core is real and measured (J1-J11): 94.2% classifier @80ms, working
routing with live savings, 9 providers, installable PWA, one-command install,
signed seed pipeline. A stranger CAN go zero-to-working.

## Why not v1.0 yet
1. **Rubric maturity** — today's bug proves it: timing misfires on edge cases
   ("...now" on a big task). The rubric needs a standing regression suite
   (started: 9 cases) + daily real-traffic hardening. Target: 2 weeks of
   dogfood with <2% misroute rate.
2. **Real-usage data** — 77.8% savings is measured on OUR workload. v1.0
   wants N>5 users of real data (telemetry flywheel, opt-in).
3. **Provider keys untested in production** — 8 of 9 providers are wired but
   untested with real keys (only Ollama is live). Each needs a smoke test.
4. **Jev Cloud adapter is untested against the live API** (early access).
5. **Onboarding gap** — fresh-user flow (no Hermes, no pre-set Ollama) is
   simulated, not yet watched end-to-end with a real newbie.

## What v1.0 requires (the bar)
- 2 weeks stable dogfood, <2% misroute, zero silent failures
- Golden-set regression suite (100+ cases) in CI
- At least 3 providers smoke-tested with real keys
- Install verified on a machine we don't own

## Version plan
- v0.9-beta = today (this)
- v1.0-beta = rubric hardened + 3 providers live-tested + Mac dogfood week
- v1.0 = public launch: install.bat from a cold machine, telemetry opt-in
- v1.1+ = Jev scheduler (see roadmap), adaptive retry, oracle API
