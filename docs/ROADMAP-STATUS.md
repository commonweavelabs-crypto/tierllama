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
| DONE | 2 | J16 (9/29: all 4 gaps, 119/119 tests) · J14 (9/29: outcomes/ledger/bump/canary/dashboard, 153/153) |
| BRAINSTORM, unblocked | 1 | J15 (needs live ledger data — fills via usage + dogfood) |
| SPEC'D skeleton, queued | 1 | J24-SEC secure fleet (spec `docs/SPECS/jevllama-j24-secure-fleet.md`) |
| ⏸ Deferred v2 remainder | — | J13 saturation offload (needs J16+PAIR), rubric relative-phrases |

**Bottom line: 14 of 16 J-numbers done. J15 needs live ledger data (fills via usage + the
overnight dogfood). NEW: J24-SEC Secure Fleet spec skeleton — the unclaimed niche
(secure heterogeneous exposure), spec at docs/SPECS/jevllama-j24-secure-fleet.md.**

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

1. J16 - hardware census: DONE 9/29 (all 4 gaps, 119/119 tests).
2. **J14 - capability feedback loop** (NEXT): spec it, then build. Machine data now exists.
3. **J15 - brain evolution** (after J14: needs J14's outcome signals).
4. **T5 PAIR dogfood** (staged, 1 evening, INDEPENDENT - can run any night):
   2-machine fleet benchmark -> REAL-SAVINGS-PROOF.md. Not a blocker for J14/J15.
5. **Debug session with Gui as first user**: log every rough edge -> polish backlog.
6. **J13 v2 remainder**: saturation offload (after T5's PAIR dogfood informs it).
7. **Post-MVP track**: telemetry flywheel, community seeds, enterprise oracle
   API, J9 installers, jev-triage JT-1->JT-3 (shared module).

## Feature graph

Open `docs/feature-graph.html` (in repo) - node graph of every module:
classifier -> router -> lanes -> scheduler -> PAIR modules -> future loop. J16 now green.
