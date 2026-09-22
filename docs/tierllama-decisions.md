# Tierllama — Spec Decisions Log (spec-first, rounds 1-2)
#project/tierllama #spec

## Locked (Gui-confirmed, rounds 1-2, 2026-09-21)
1. NAME LOCKED: **Jevllama** (Gui, 2026-09-21 eve: "Jevllama it is! If ollama wants its
   O inserted they can buy us!"). Internal joke: "Jev-O-llama". Rename safety valve:
   if TypeSafe objects to "Jev", single rename + release (config string + repo name).
1. STANDALONE product, own repo(s) under commonweave GitHub org. Open-core (Linux-model):
   mature open release + enterprise/beta closed tier. NOT internal-only.
2. Open core (Apache-2.0): router core, Jev-class classifier integration, box queue +
   priority scheduler, CLI. Enterprise/beta: managed cloud routing pass-through w/ margin,
   team dashboards, analytics, experimental features.
3. Name: Tierllama (Gui leaning; avoids Jev trademark; "Jev-powered" in README).
   Backup: Jevllama. NOT OpenJev (SemIf's former name).
4. Architecture: decision app on Windows (GPU, SemIf-style 4B logit scoring, ~0.2s);
   box = executor only. Users choose local-or-cloud classifier (cloud = TypeSafe w/
   attribution + easy-connect for hardware-poor users); hardware-warning UX if local fails.
5. MVP providers (test setup): Ollama (Ornith 9B local), box (slow CPU 27B), cloud API
   (GLM/OpenRouter) as "hard" lane. Kimi-class = any OpenAI-compatible cloud endpoint.
6. Routing = MULTI-DIMENSIONAL, one classifier pass: difficulty (easy/med/hard),
   timing (now/later/overnight), type (chat/code/analysis/archive/creative).
   + hardware hooks (~200 tok: free VRAM, machine busy, queue depth) injected per request.
   Gui's constraint honored: workhorse machine preference (don't wake Ornith when
   ComfyUI owns VRAM) = user-configurable per-machine policy.
7. Escalation ladder: retry-count + confidence nudge tiers up (his drag-scroll-bug story
   = the motivating example: 4-6 retries should auto-escalate).
8. Deferred to phase 2: hardware auto-discovery (MVP = config + health checks);
   blockchain sign-in/attestation (MVP = signed local telemetry, revisit if trust
   problem appears). Real-vs-provider benchmark tracking = phase 2/3 differentiator.
9. First consumer: Hermes/Telegram. Video UI chat = adapter #2. Core is consumer-agnostic.
10. Monetization: enterprise tier + optional cloud plans; MARKET RESEARCH JOB queued
    (box, tonight): competitor pricing + cost-model break-even math for tiered routing.
11. Footer pages (bug report/donate/support) noted for M-G monetization of Video UI.

## Market research job (dispatched with tonight's batch)
- competitor pricing landscape (OpenRouter/model pricing by class)
- cost model: always-best vs tiered routing, break-even math, honest caveats
