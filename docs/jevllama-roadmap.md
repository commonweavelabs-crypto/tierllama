# Jevllama Roadmap (v1 — 2026-09-21)

> Built from the 2026-09-21 working session. Companion docs: `SPECS/tierllama-decisions.md`,
> `SPECS/jevllama-bench-01.md`, `SPECS/tierllama-market-research.md`, `JEV-CLASS-ROUTER-BRAINSTORM.md`.
> Name: **Tierllama** is my pick, **Jevllama** is Gui's locked call (rename valve if TypeSafe
> objects; "Jev-o-llama" stays the README easter egg either way).

## Manifesto (one paragraph)
AI access is bloated: every message hits the biggest model by default, users pay for
compute they don't need, and providers profit from the waste. Jevllama flips it: a
sub-second Jev-class classifier reads each message, scores it against your available
models, and routes it to the CHEAPEST model that can do the job — local first, cloud only
when it earns its cost. Measured on our own hardware: 86.7% routing accuracy at 0.2s,
free, on a 4B model that fits 4GB VRAM. Tiered routing saves 40–80% (market research:
64.8% base case). We commoditize intelligence: users keep their money and their hardware
works for them, instead of renting a data center. Open core, Apache-2.0; enterprise =
managed cloud routing + dashboards. *Jev's paradox says efficiency increases consumption —
we make that consumption cheap and local.*

## Where we are (evidence, not plans)
- **Ecosystem proof:** browser-use/jev-ultrafast (17.7K★, MIT, entry 272) = a shipping
  product on our exact mechanism (TypeSafe Jev typed decisions over an indexed table,
  one round trip). Validates the architecture AND the category's momentum.
- Classifier: qwen3:4b + rubric v1 = **86.7% @ 0.196s** on the 120-message golden set
  (5 roles × difficulty × timing, incl. 20 ambiguity traps). Rubric tuning: v1 > v3 > v2 —
  over-specification overcorrects; prompt iteration has diminishing returns.
- 0.6B rejected (50%). 8B adds VRAM, not accuracy. **4B = the floor and the pick.**
- Residual errors are GENUINELY ambiguous asks — exactly what the confidence-threshold
  fallback to the main LLM is for. Next lever: SemIf-style logit probabilities.
- Multi-dim scoring proven in ONE call: {difficulty, timing} pairs, 0.23–0.45s.
- Market research (box): 40–80% savings, robust to misroutes; >95% accuracy = enterprise bar.
- Pricing anchors (verified 2026-09-21): local $0 | deepseek-v4.1-flash $0.15/$0.60 |
  kimi-k3 $3/$15. Perfect routing ≈ $1.00/M tokens vs $6.00 always-best = **83% savings
  ≈ $5,000/B tokens**. At 88% classifier: 77% savings. Every accuracy point ≈ $30/B tokens.

## MVP definition (the only goal that matters right now)
**MVP = a working local router that classifies every incoming message into (role, difficulty,
timing) and dispatches it to the right lane in < 1 second, with a confidence fallback.**
In scope: CLI + config (machines, models, lanes), 4B classifier w/ structured output,
4 lanes (local-easy / cloud-medium / cloud-hard / overnight-box), confidence-gated
escalation ladder, decision log (local JSONL). OUT of scope until after MVP: WebGPU,
auto-discovery, team dashboards, cloud pass-through billing, landing page, name tests.

## Milestones
- **J1 — Router core skeleton** (Hermes-side python): message in → classifier call →
  lane decision + confidence → dispatch + log. Runs on this machine. Done = end-to-end
  routing of 20 live messages with a decision log on disk.
- **J2 — Classifier hardening**: logprobs-based confidence (llama.cpp/Ollama logprobs or
  SemIf-style logit read), threshold tuning on the 120-set, ambiguity → fallback path.
  Done = confusion rate on clear-cut messages ≈ 0; ambiguous ones escalate by design.
- **J3 — Lane adapters**: local (Ornith/other Ollama), cloud (OpenAI-compatible API),
  overnight box queue (existing job system). Done = one message routed to each lane live.
- **J4 — Escalation ladder**: retry-count + confidence nudge up a lane; decision log with
  per-decision cost estimate. Done = a failing easy-route auto-escalates and logs why.
- **J5 — CLI + config polish + Tier-0 discovery** (`tierllama route/bench/doctor`).
  NEW: Tier-0 LAN-scan discovery at startup — find every Ollama/llama-swap on the
  subnet (measured: 3 servers in 6s), each becomes a lane automatically, no accounts.
  This is the competitive wedge for the existing Ollama install base ("download one
  app, your whole fleet routes"). Done = fresh install works from README on a second
  machine AND finds LAN peers automatically.
- **Phase 2 (post-MVP): account-secured cross-network fleet** — download-and-connect
  onboarding (Tailscale-model), same-account peer matching, agent on each machine.
  Needs identity backend; rides Tailscale/token for transport. (Gui confirmed split
  2026-09-22: scan-and-find = MVP, account matching = phase 2.)
- **J6 — MVP release polish** (COMPLETE 2026-09-22: 4 security findings fixed incl.
  HIGH path-injection; README+mission+topics live; fresh-clone regression PASS): security/bug sweep (input validation, prompt
  injection surface, path traversal, secrets), README final (mission statement +
  "powered by Jev" + savings story), repo description/topics, decision-log privacy
  check (never log user content unmasked in shared exports).
- **J7 — Web UI dashboard** (Gui 2026-09-22: users expect an interface; Ollama has one):
  local web app showing fleet (available machines), per-lane latency/cost stats, memory
  usage, decision log browser, cloud-provider linking (incl. TypeSafe account), config
  editor. Tech: FastAPI + small SPA (reuse comfyui-video-ui patterns). First-time UX:
  "model is waking up" indicator.
- **J8 — Oracle v1** (design: docs/SPECS/custom-routing-and-oracle.md): capability
  data file (versioned, URL-refreshable — never scraped), `tierllama bench` (on-device
  speed for every discovered model), auto-suggest on discovery, suggestion logging.
  PLUS TypeSafe/Jev account linking + enterprise console.
- **J10 — Providers v2 + Seed refresh**: OpenAI/xAI/Anthropic TOML descriptors,
  key management, per-provider cost tracking; EXPERT tier (4th difficulty).
  Seed-refresh pipeline: versioned+signed seed-table.json at stable URL, startup
  check + hot-reload, never overwrites user edits, weekly cadence (free tier).
  Community-refined seeds (opt-in telemetry) ride the same channel; live oracle
  API = enterprise tier. (post-UI): managed cloud
  classifier option in-UI, team dashboards, usage analytics.
- **J9 — Installers/distribution** (post-UI): one-click install per OS, auto-update,
  bundled Ollama bootstrap for non-Ollama users.

## Monetization (after MVP proves the router)
- Free open core: router + classifier + box scheduler + CLI (Apache-2.0).
- Enterprise tier (subscription): managed cloud-classifier + cloud routing pass-through
  (Kimi/GLM/OpenRouter with margin), team dashboards, usage analytics, SSO, mixed-fleet
  hardware consistency. Users can always opt out and run local only.
- Competitive wedge vs Ollama/OpenRouter: they serve models; we DECIDE where each call
  goes, and prove the savings per decision in the log. Routing accuracy is the product.

## Standing decisions (locked)
Open-core split per spec; classifier runs on the local GPU (sub-second), not the box;
cloud classifier = enterprise bundle option, opt-out local; Hermes/Telegram first consumer,
Video UI adapter #2; no blockchain sign-in for now; hardware auto-discovery = post-MVP.

## Risks
- Judge-loop over-fitting on our own golden set → keep a held-out slice + real-traffic eval.
- Ollama logprobs API limits → fallback to llama.cpp server for the classifier only.
- Name/trademark: Jev (TypeSafe) + Llama (Meta) — rename valve armed; A/B decides.


## Added 9/22 (wrap-up day): the road to v1.0

### J12 — rubric hardening + beta polish (NEXT)
- Standing regression suite (start: 9 timing cases from today's bug; grow to
  100+ golden cases, run before every rubric change)
- Dogfood hardening: real-traffic misroute tracking in proxy.jsonl
- Provider smoke tests with real keys (Groq + DeepSeek first - cheapest)
- Mac dogfood week: real N>1 usage data
- Target: v1.0-beta

### J13 (BRAINSTORM, Gui): Jev as a SCHEDULER
Question: can Jev route a SCHEDULE? "do this by Friday" -> task placed ON
Friday, not just LATER?
Architecture sketch (Jev's calibrated-confidence makes this uniquely cheap):
1. Classifier gains a 4th dimension: WHEN (date/deadline extraction with
   confidence) - still one ~80ms logprob read, still ~free
2. Low confidence -> clarify-or-ask rule (never silently guess a date)
3. Router gains a TIME dimension: jobs with deadlines enter a timed queue
   (box lane already has the queue bones; add due_at + retry policy)
4. The scheduler is NOT an LLM - it's a plain cron/heap of (task, due_at,
   lane) that Jev populates. Jev classifies; dumb code schedules. That's the
   System One philosophy: cheap decisions, boring reliable execution.
Feasibility: HIGH. Risk: date ambiguity ("Friday" = this Friday?) - solved by
the same confidence threshold + explicit confirmation in the UI.
Value: Tierllama becomes not just a router but an agent brain - jobs that
schedule themselves onto the cheapest capable lane at the right time.

### Later (unchanged)
- Telemetry flywheel (opt-in) -> community seeds
- Enterprise oracle API
- Adaptive retry (Jev learns from misroutes)
