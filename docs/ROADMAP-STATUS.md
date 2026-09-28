# Tierllama — Roadmap Status (one-page, generated 2026-09-29)

Source of truth: `docs/jevllama-roadmap.md`. This page summarizes where every
J stands so Gui can see the whole picture without reading the full file.

## The count

**16 J-numbers exist. They are NOT sequential work — they're numbered in the
order ideas were brainstormed (9/22 night produced J14/J15 out of order).**

| Status | Count | Which |
|---|---|---|
| ✅ DONE | 11 | J1 J2 J3 J4 J5 J6 J7 J8 J9 J10 J11 |
| ✅ DONE (v1+v2 core) | 1 | J13 |
| ✅ DONE (PAIR port-picks) | 4 modules | T1/T3/T4/T4b (health, fleet, dispatch, engines) |
| 📋 SPEC'D, NEXT | 1 | **J16** |
| 💡 BRAINSTORM, no spec | 2 | J14, J15 |
| ⏸ Deferred v2 remainder | — | J13 saturation offload (needs J16+PAIR), rubric relative-phrases |

**Bottom line: 12 of 16 J-numbers are done. 1 spec'd (J16). 2 are brainstorms
that DEPEND on J16's data (they can't be built properly before it). So J16 is
the only thing standing between us and the full v1.0 feature set.**

## Where we are vs MVP

**MVP (defined in roadmap): local router, <1s classify, 4 lanes, confidence
fallback, decision log.**
👉 **MVP IS DONE.** J1–J6 shipped it (evidence: 86.7% classifier @ 0.2s,
4 lanes live, escalation ladder, decision log, security sweep, fresh-clone
regression PASS). Everything since J7 is post-MVP: dashboard, oracle,
providers v2, installers prep, scheduler (beta), PAIR modules.

**The savings math (verified):** perfect routing ≈ 83% savings ≈ $5,000/B
tokens; at our 88–95% classifier: 77%+ savings. This is the product story.

## The remaining path (recommended order)

1. **J16 — hardware census** (SPEC'D, ready): machine_profile, worker-class
   fit, model@machine bench keys. Feeds J13 v2 remainder + J14.
2. **T5 PAIR dogfood** (staged, 1 evening): 2-machine fleet benchmark →
   REAL-SAVINGS-PROOF.md. Independent of J16.
3. **J13 v2 remainder**: saturation offload (after J16+PAIR dogfood).
4. **Debug session with Gui as first user** (your idea — scheduled next):
   you use the app, we log every rough edge → becomes the polish backlog.
5. **J14 capability loop** (spec next): outcome signals → failure-driven
   bumping + canary probes. Needs J16's machine classes.
6. **J15 brain evolution**: model reputation, demote/promote guardrails
   (design already thought through — see roadmap conflict section).
7. **Post-MVP track**: telemetry flywheel, community seeds, enterprise oracle
   API, J9 installers, jev-triage JT-1→JT-3 (shared module).

## Feature graph

Open `docs/feature-graph.html` (in repo) — node graph of every module:
classifier → router → lanes → scheduler → PAIR modules → future loop.