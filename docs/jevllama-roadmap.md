# Jevllama Roadmap

## PROJECT BOUNDARIES (Gui, 2026-09-23 — hard rule)
Tierllama ≠ comfyui-video-ui. This roadmap contains ONLY router-product work:
classification, lanes, providers, oracle, telemetry. No video-workspace
features, no role personas (the 5-role taxonomy was removed 9/23 — see
docs/SPECS/role-taxonomy-lineage.md). comfyui-video-ui keeps its own canonical
roadmap (docs/ROADMAP.md there) including ITS OWN Jev-class usage (M-F role
router). Shared between projects: only the Jev-class TECHNIQUE (logit-read
classifier), never features or vocabulary. When brainstorming crosses projects
and ownership is unclear: STOP and ask Gui which lane it belongs to. (v1 — 2026-09-21)

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

### J13 (SPEC'D 9/24 — beta feature, OFF by default per Gui): Jev as a SCHEDULER — full spec: docs/SPECS/jevllama-j13-scheduler.md (4th WHEN dimension, clarify-or-ask, dumb file-backed scheduler, night windows, shove cap, worker classes + saturation offload = v2; pushback + OSS inspiration documented; golden set v2 gate)
**V1 LANDED 9/25** (beta, gate OFF by default — verified). Commits:
- `f3ae7bb` — UI wiring (Scheduler tab, /api/schedule + resolve/toggle endpoints), config gate + WHEN enum + scheduler.py + lane_for (J13 v1 1/3 was `815155d`: classifier 4th dim, file-backed queue, due loop, 3-try retry, night-window check)
- `b3a87ee` — beta-gate toggle bugfix (OFF was a silent no-op when file said True — regex only matched False; how the gate got stuck ON) + gate-path tests (10)
- `f599eff` — golden set v2: WHEN 88.9% (18 cases), phrase 94.4%, 5 DEADLINE phrases parse via dumb regex; J12 regression root-caused (rubric-edit shift, 5 cases) and anchors fixed on data: difficulty 71.0 / timing 95.2 / full 67.7 — all above J12 floors and above pre-J13
- `b6bb404` — persistence E2E: real cross-process (subprocess enqueue → fresh import → tick → dispatched), corrupt-file reset, midnight wrap, start==end window
- `8edf48c` — dashboard polish: toggle reads authoritative gate state (no string-matching); clarify cards + upcoming table + honest OFF-state text verified
Golden set v2 gate: PASSED (floors met, improvements recorded). 55/55 tests OK.
**V2 LANDED 9/29** (Gui-approved goal, 3 tasks):
- `dfeb462` — **task 1 per-action confidence thresholds**: NEW `tierllama/actions.py` (query=0.60 / schedule=0.85 / destructive=0.95; unknown action → safest 0.95); router gates BEFORE lane branch (below-threshold DEADLINE clarifies even when lane_for routes FALLBACK; guess surfaced, never executed); `lane_for` DEADLINE gate now uses the schedule threshold. 22 tests incl. live-router golden boundary cases (0.85 schedules, 0.84 clarifies w/ guess, query 0.65 dispatches).
- `4caddb1` — **task 2 worker classes**: NEW `tierllama/worker_classes.py` (adapted from NVIDIA Personal-AI-Router Apache-2.0 node-availability windows): PROVISIONAL lane→class mapping (BOX=night_only, others always_on; J16 machine_profile replaces — placeholder documented); night_only jobs due outside window get a VISIBLE shift (due_at → next window open + `rescheduled_reason`), never silent deferral; unknown lanes default always_on (never block user deadlines). tick() returns `shifted` events. 13 tests.
- `7a2d22d` — **task 3 shove logic**: NEW `tierllama/shove.py` (spec capacity/priority section): coarse duration classes (quick/medium/long/overnight; J14 outcome signals refine later), `shove()` + `shove_history` + user-notified reason, weekly `shove_cap_week` cap (capped jobs NOT moved again — collision reported), `insert_priority()` shoves latest-due first, stops when need met, never silent. 8 tests.
Integration smoke verified (gate↔lane_for consistency, BOX night-gating, cap honored). **Suite: 89/89 OK.**
**V2 remaining (deferred)**: saturation offload (needs J16 machine classes + PAIR dispatch); relative-phrase rubric refinement ('later today'/'this week' with '?' → DATE_UNCLEAR vs DEADLINE); rescheduling heuristics beyond the coarse duration classes (J14 outcome signals). Source of task 1: Simon Scrapes' Jev walkthrough yt-2dai1jvyd5m — per-action thresholds set by cost-of-being-wrong.

## Side-note: heterogeneous backend fleet + secure exposure (Gui idea, 2026-09-29 evening, researched — NOT committing to a milestone yet)

**Obsidian tags:** #tierllama #shared-exposure #niche-analysis #phase2

**The idea (Gui):** Tierllama shouldn't require Ollama. Serve ALL local inference apps —
llama-swap, LM Studio, llama.cpp server, vLLM, Jan, KoboldCPP, GPT4All — as first-class
fleet members. Two directions: (1) CONSUME: find + route to whatever users already run;
(2) EXPOSE: Tierllama itself acts as the discoverable, secured network server those apps
(and Hugging-Face-GGUF model pulls) connect to — the thing they're all missing.

**Market research done 2026-09-29 (real docs checked, not vibes):**
- Unified proxy layer is CROWDED: LiteLLM, OpenRouter (cloud), and **Olla**
  (thushan/olla — Go, unified model discovery across backends + failover, closest to this
  idea; no cost policy/scheduler/decision log though).
- NO existing app does secure auto-discovery + encrypted cross-machine routing across
  **heterogeneous** backends. Nothing advertises itself: Ollama/LM Studio/llama-swap all
  listen on ports but are invisible to each other (llama-swap = manual config only; LM
  Studio has a headless server, no discovery; llama.cpp server = 1 model, LAN-exposed, no
  auth). Gui's niche = real and unclaimed: **secure exposure is the gap.**
- Security note (verified): consumer LLM servers bound to the LAN with no auth is a
  documented unsolved risk — our J16/J13 mTLS cluster pattern is the differentiator.

**Phased plan (Gui's call, sequenced):**
1. MVP stays as-is (Ollama-first, works today).
2. **Adapter phase (post-MVP):** LM Studio + llama-swap adapters (both OpenAI-compatible,
   J5 discovery extension: scan known alternate ports, not just Ollama's).
3. **Secure-exposure phase (later, OWN MILESTONE + security review):** Tierllama exposes
   itself as a discoverable, authenticated, encrypted fleet node for non-Ollama engines
   (J9 installer bootstrap: "install Ollama OR point Tierllama at your existing engine").
- **HF note:** Hugging Face = model library, NOT an inference server (no serving daemon).
  Its models reach local machines via Ollama-GGUF integration already — compose, don't
  duplicate. HF itself will never be a fleet node (wrong layer).
- Pairs with jev-triage-style modularity: adapters are plugins, not forks.

## Market-research addendum to the secure-exposure side-note (2026-09-29 midday)
Gui's question: "is the gap unclaimed because there's no use case?" Verdict: **genuine niche**
- **Demand exists:** recurring r/LocalLLaMA threads ask exactly "share my local LLM with other
  devices securely" — answers are all DIY (Tailscale, reverse proxy, VPN). Homelab/self-hosting
  trend ~+40% YoY. Non-Tailscale users are the addressable segment (power users already have it).
- **Incidents prove need:** 1,100-14,000+ Ollama instances found exposed to the open internet
  with zero auth (cybersecuritynews, malwarepatrol); compute theft + model exfiltration
  documented; multiple 2026 CVEs (SSRF etc.); "Shadow MCP" = same unsecured-surface problem
  arriving at protocols. Risk is real, not theoretical.
- **Why incumbents punted (3 structural reasons, not "no use case"):**
  1. wrong layer — each owns runtime/chat/config; the between-machines layer belongs to nobody;
  2. punt is rational for small teams (localhost default is safe; secure pairing UX is weeks of
     unglamorous work with no punishment for shipping the footgun);
  3. monetization — secure routing is invisible plumbing (OpenRouter's $140M ARR is the visible
     cloud routing meter; no local meter exists yet — note: that IS the Compute Fund thesis gap).
- **Positioning:** security = trust layer under the headline ("install one app, your whole fleet
  routes, and it shows its reasoning"), not the headline itself. LAN-only secure exposure +
  supporting Tailscale for off-network = full coverage without rebuilding a VPN company.

## J25-adjacent research note: secure LAN exposure — difficulty corrected downward (2026-09-29 morning)
Follow-up to the heterogeneous-fleet side-note. Gui asked: "how hard is the security problem,
does LAN-only solve it, do we need a big model for it?" Research findings:
- **Ollama did NOT solve it — it punted.** Default = localhost-only. Exposing to LAN
  (OLLAMA_HOST=0.0.0.0) opens the port with NO authentication; official docs direct users
  to reverse proxies. LM Studio + llama-swap same pattern. Everyone punts - no one shipped
  secure exposure for consumers. Niche stands.
- **LAN-only removes more than half the threat** (kills internet-scale attacks by design)
  but NOT the rest: discovery protocols have no built-in auth; name-resolution spoofing
  (mDNS/LLMNR poisoning) is documented and unauthenticated — a compromised LAN device can
  impersonate a node. Trust must come from pairing, not from network presence.
- **Cryptography is solved (not cutting-edge):** mutual TLS + cert pinning is old, proven,
  standard-library-supported; PAIR does it, SSH-style pinning does it. The "hard part"
  is product UX: pairing flow, untrusted-device handling, cert rotation policy.
- **Difficulty honest call:** normal-model engineering with human review; NOT a
  frontier-model task. Cryptography off-the-shelf; threat model documented; pattern
  proven live 2026-09-29 (PAIR cluster mTLS both directions on our own hardware).
- **Caveat:** threat-model details not guaranteed complete from memory; milestone ships
  behind a security review checklist (J16/J13 mTLS precedent).

### J24-SEC (spec skeleton 9/29, Gui-approved planning): Secure Fleet — secure exposure + pairing
Full skeleton: docs/SPECS/jevllama-j24-secure-fleet.md. One toggle: node keypair at install
(zero-touch), 6-char pairing-code handshake -> mutual cert pinning (pattern proven live
via PAIR cluster), mTLS fleet transport LAN-bound default OFF. Threat model: discovery
spoofing/plaintext interception in scope; public exposure OUT (review-gated); off-network =
Tailscale-supported. MVP cut + security review checklist in the spec. Ships after debug
session + polish backlog. Monetization mapped: free core / ~$10 household tier (secure fleet +
multi-device + scheduler pro) / enterprise (J8) / cloud referral via Compute Fund. Market
sanity: ~1M households w/ local LLM (est.) x 1-3% capture x $10 = $1-3M ARR consumer-only.

### Shared module: jev-triage (filed 2026-09-29, Gui's call — own repo, cross-project)
**Repo:** github.com/commonweavelabs-crypto/jev-triage (MIT, skeleton committed 75d789e). Jev-powered
submission triage (bug/feature/complaint/question + severity + subsystem split + intent routing,
per-action thresholds, clarify-or-ask, audit trail) as a HOST-AGNOSTIC module: built once, consumed
by comfyui-video-ui first (support tab, MVP-adjacent), then exported to tierllama (proxy error reports
+ support intake) without a rewrite. Milestones JT-1 (core engine) → JT-2 (video-UI consumer) → JT-3
(pip packaging + tierllama export) live in that repo's docs/PLAN.md. Tierllama's role: second consumer
+ the Jev layer it calls may BE our local proxy/classifier (dogfood synergy). Also links to J14:
triage verdicts = free labeled outcome data for the capability ledger.
Question: can Jev route a SCHEDULE? "do this by Friday" -> task placed ON
Friday, not just LATER? **Answer (v1, live-verified): yes — DEADLINE conf .95 → queued due Oct-02 17:00; vague "soon" → clarification, guess surfaced but never executed.**
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

### J16 (SPEC'D 9/24 → LANDED 9/29): hardware census & worker-class fit — feeds J13 v2
Full spec: docs/SPECS/jevllama-j16-hardware-census.md. All 4 gaps closed 9/29:
- `48f5783` — **Gap A**: NEW `bench_keys.py` — bench_key=model@host, 24 pre-J16 records migrated (host=localhost, documented assumption, idempotent), load_bench_by_key. THE bug fixed: same model on 2 machines was indistinguishable.
- `787c426` — **Gap B**: NEW `machines.py` — machine_profile {host, name(user-given), class(user-confirmed), windows, pairs} one JSON per machine in logs/fleet/; CONSENT BOUNDARY (class requires explicit user answer, class_confirmed_by=user, no inference anywhere — spec hard rule).
- `bf04351` — **Gap C**: NEW `pair_labels.py` — pair labels {timing_fit, max_fit, tok_s, cold_load_s} host-scoped from bench; pair_worker_class spec mapping (NOW+HARD on workhorse -> workhorse; LATER+HARD -> user-picked class; cloud -> cloud_scheduled); best_pair_for_lane. Rank-direction bug caught by tests pre-commit.
- `53913dc` — **Dashboard Machines tab**: /api/machines + /api/machines/class (the only path that sets a class), class picker with honest not-set state + user-confirmed badge, discovery-merged unprofiled hosts.
- `db05f54` — **J13 hookup**: scheduler BOX jobs consult the box host machine_profile; user-confirmed class wins over PROVISIONAL mapping; corrupt/missing -> documented fallback. Tests only, no behavior change without a profile.
**Suite: 119/119 OK.**
- **Gap D (future)**: hardware×model RECOMMENDATION pre-purchase = J17 candidate, needs community seed data (opt-in telemetry flywheel, already roadmapped).

### Later (unchanged)
- Telemetry flywheel (opt-in) -> community seeds
- Enterprise oracle API
- Adaptive retry (Jev learns from misroutes)


### J14 (SPEC'D 9/29 → v1 LANDED 9/29): capability feedback loop — failure-driven bumping
Spec: docs/SPECS/jevllama-j14-capability-loop.md (write-up from this goal's spec-first pass). Landed:
- `28683b2` — spec + CAPABILITY config block (BETA gate OFF; bump_after_failures=3, cooldown_h=12, max_moves_per_day=1, min_samples=10, canary_pct=0)
- `8c71b5e` — **task 1 outcome signal**: NEW `outcomes.py` — MVP truth taxonomy (error/empty=failure, ok+content=success, queued=unknown, user retry-in-session=failure signal); outcomes.jsonl with msg_key HASHED (J6 privacy rule, test-enforced)
- `f981f66` — **task 2+3 ledger + bump rule**: NEW `capability.py` — rolling ledger keyed model@host|difficulty|timing|when (classifier dims only, no embeddings per spec); consecutive-failure streaks (success breaks, unknown neutral); evaluate_bump = +1 tier FOR THAT CLASS ONLY with J15 guards (cooldown, rate 1/day, min-samples); DRY-RUN SAFE (decisions computed regardless of gate; caller applies only when CAPABILITY.enabled)
- `6219858` — **task 4 canary probes**: NEW `canary.py` — sample canary_pct of HARD traffic down a tier; bench-style deterministic usability grading; promotion after N usable outputs; consent-gated (gate OFF = never fires); rng=0.0-is-valid-roll bug caught by tests
- `696e4bf` — **task 5 dashboard**: /api/capability + toggle (consent pattern, block-scoped so SCHEDULER gate untouched — e2e verified); overview card with honest OFF copy + outcome counts + bump list; load_recent_bumps transparency
**Suite: 153/153 OK. Both beta gates verified OFF.**
**J15 next**: its guardrails are already designed (roadmap conflict section + J14 cooldown/rate/min-samples are the class-side); J15 = MODEL-level reputation on top of J14's ledger, waiting on J14's live data.
**J14 v2 would add**: semantic outcome via user thumbs up/down; embedding-based prompt clustering (replacing dimension-tuple keys); cross-user aggregation (J15 territory, needs telemetry consent).
Gui's idea: when a model keeps FAILING on a class of prompts the classifier
labels EASY/MEDIUM, flag it and bump that prompt-class to a stronger tier
(gradually: EASY -> MEDIUM -> HARD -> EXPERT). And the reverse probe: every
once in a while, send HARD-labeled work down a tier as a canary — if the
output is actually usable, promote ("this model can do that").

What ALREADY exists (verified in repo):
- J4 escalation ladder (HARD fail -> EXPERT retry at higher thinking)
- dispatch retry logic in adapters.py
- per-call logs (proxy.jsonl / decision log) — but NO outcome field

Missing pieces (the actual work):
1. OUTCOME SIGNAL: dispatch must record task success/failure. Proxy-only
   truth: HTTP errors + empty content are automatic; semantic success needs
   the user's app to report (thumbs up/down, retry-by-user, or output
   validation). MVP: explicit retry-within-session = failure signal.
2. CAPABILITY LEDGER: per (model, difficulty, prompt-class) rolling stats —
   failure rate, avg latency. Lives in logs/, feeds bench.py.
3. GRADUAL BUMP RULE: N consecutive failures on class X -> tier += 1 for
   that class only (data-driven, per prompt-class via classifier embedding
   or role+keyword cluster). Never global jumps.
4. CANARY PROBES (Gui's downgrade idea): sample p% of HARD traffic to the
   tier below; usable output (validated) N times -> promote class. Consent-
   gated like Optimize; never silently.
5. UI: capability report in dashboard (which classes bumped/promoted, why).

This closes the loop with J13 (scheduler) + telemetry flywheel: real user
failures become the measured data that outranks the seed table.


### J15 (BRAINSTORM, Gui 9/22 late): MODEL-level promotion/demotion + brain evolution
Gui's additions + the conflict question he raised:

1. MODEL-level bumps (beyond prompt-classes): a model suggested as EXPERT
   that keeps failing on expert work across MANY users gets DEMOTED
   (expert->hard-capable). The model itself has a reputation, not just tiers.
   Inverse of the canary: strong performers get promoted.

2. Gui's collision question (real design risk - think before building):
   - Loop A (prompt bump up) + Loop B (model demote down) can feed each
     other: failures bump the class up, the class keeps hitting the same
     failing model, model demotes, next model fails too, class bumps again
     -> runaway. Mitigations to design:
     a. SEPARATE the two clocks: class bumps use consecutive-failure streaks;
        model reputation uses long-window aggregate rates (not streaks)
     b. Hysteresis + cooldowns: no tier moves within N hours; require
        minimum sample size before any demotion (n>=20 for model-level)
     c. Bounded oscillation: class can move at most 1 tier per day; model
        reputation changes max 1 level per week
     d. EL NINO/feedback-loop detector: if class-bump rate and model-demote
        rate correlate, freeze both and flag for human review
   - Answer to "will the model keep dropping": not with (a)-(d) in place -
     the guardrails make loops self-limiting instead of runaway

3. The BRAIN (rubric) itself must be versioned data: same discipline as the
   signed seed file - rubric updates ship as versioned, signed files, staged,
   preview-diff, user-approved Re-scan ( NEVER silent), rollback. Real user
   failures -> rubric amendments proposals -> maintainer curates -> ships.

4. CLOUD JEV rules: the /v1/systemone protocol takes questions + criteria
   per call - so the rubric ships AS THE REQUEST PAYLOAD (criteria are the
   rules). Same versioned rubric file drives local (prompt text) and cloud
   (criteria JSON) - ONE source of truth. Confidence calibration may differ
   (their model is better calibrated) - threshold can differ per brain.

Open questions to answer in J12-J15 sequence: who curates the community
rubric? How do per-user edits merge? Telemetry consent scope for rubric data?

## Box Queue Policy v2 (Gui 2026-09-29 late night, pushback accepted — supersedes "box = overnight only" framing)

**Gui's correction:** the box is NOT the night machine; it's the cheap-slow-workhorse lane.
"Overnight" was a framing accident — the product is a JOB QUEUE, not a schedule-locked window.

**The v2 policy (Gui's spec, verbatim intent):**
- LATER-classified work (MEDIUM or HARD or EASY) -> BOX queue IMMEDIATELY (throw it at
  the queue; the box starts when it starts — no night-window gating for the box lane)
- Deadlines ("by Friday") remain the exception: deadline work routes to cloud if the
  box queue can't make the deadline (queue-depth check), or SHOVES existing box jobs
  when there's room. Priority work escalates to cloud when the box is full. Standard.
- Night window remains a preference for the WORKER (when the box is free of human
  competition), not for ACCEPTING work.

**Existing pieces (verified):** LATER->BOX routing exists (`lane_for`); shove priority
insert exists (`shove.py`); night-window gate exists in `worker_classes.py` (the piece
that flips to per-machine preference instead of hard gate); cloud escalation for
deadline-miss exists conceptually (J4 ladder + J13 deadline handling).

**Compare-versions clause (Gui):** when we build v2, FIRST compare against (a) the
overnight-window v1 (built, `4caddb1`), (b) this queue-first v2 spec, (c) any other
documented version; pick by measured behavior, not preference. No silent replacement.

**Decomposition pre-step (new idea from this same discussion, filed here):**
- Jev does NOT decompose long/compound prompts — it one-glance classifies (cheap,
  fixed questions, no reading). Breaking a long message into tasks = LLM job.
- Cost guard chain (Gui's brainstorm, ordered cheapest-first):
  1. pure-code length check vs Jev context (no model cost)
  2. below threshold: ONE small-local-model pass for decomposition, ONLY for
     multi-sentence/multi-request-looking messages (single-action messages skip entirely)
  3. Jev then classifies each decomposed piece (fan-out — cheap per piece)
  4. pieces route to the machine that can serve them (image model exists on exactly
     one fleet node — routing respects capability, ties to J16 pairs)
- Attribution: speculative fan-out pattern (validated by Simon Scrapes Jev walkthrough,
  yt-2dai1jvyd5m); Tierllama application of it is original.

**Filed as T5-image candidate job:** draw the full Tierllama blueprint — every node,
description per node, real icons (not emoji) — as the first overnight test job for
the decomposition path. (Also satisfied by docs/feature-graph.html today, but a
rendered-graph version tests the image lane.)

**Status:** roadmap item queued for a J13-v2-remainder / J15-adjacent session; not
committed to code tonight. Compare-versions rule active.

## J12+ feature candidates from NVIDIA PAIR (added 2026-09-25, see docs/PAIR-CASE-STUDY.md)

**Code study done 2026-09-25 (repo cloned, read, pattern-ranked): docs/PAIR-CODE-STUDY.md.**
Top port-picks: (1) EWMA α=0.35 GPU-pressure with asymmetric hysteresis bands + stale→neutral
(job-scheduler) — the missing continuous health signal for our measured tier; (2) reservation
lifecycle (reserve-at-dispatch, release-on-end, move-on-failover, one lock) for T4; (3)
commit-at-first-body-byte + dispatch budget/deadline; (4) activity-vouching liveness for T3
(busy nodes stay listed); (5) manifest-driven engine addition. Confirmed absent in PAIR's
code: pricing/tier/cost policy, per-machine bench, user-visible decision log, cloud tier —
all four remain ours.

### LANDED (2026-09-25 goal run, all PAIR-inspired + Apache-2.0 attribution in-module)
- **T1 health signal** — `12acf89`: `tierllama/health.py` (NodePressure EWMA α=0.35,
  bands 0-3, asymmetric downward 35/65/80, stale >10s → neutral 1, never-sampled →
  neutral 1; FleetPressure ranking pressure→stable-id + snapshot w/ staleness).
  11 tests. Also fixed scheduler.py NameError (SCHEDULER→_SCHEDULER()) from
  uncommitted J13 wiring.
- **T3 fleet discovery** — `9f1934c`: `tierllama/fleet.py` (file-backed registry,
  provenance local-fleet, zeroconf `_ollama._tcp` browse optional-dep with J5 TCP
  sweep fallback, PAIR anti-flap liveness: evict after 12 missed scans, inference-
  bytes vouching 60s, enrichment vouch 10s, all-lost-is-our-fault suppression 6
  scans). 8 tests incl. vouch/suppression expiry.
- **T4 request-level dispatch** — `e734ddb`: `tierllama/dispatch.py`
  (Reservations one-lock: reserve-at-dispatch, release-at-end, atomic move-on-
  failover — fixed a deadlock in first draft; budget 3 rounds + 90s deadline;
  retryable-status rules; least-pressured-first ordering via health module;
  ReservationContext releases all at end). 8 tests.
- **T4b manifest engines** — `d90e808`: `engines/` schema + llamacpp example
  manifest + `tierllama/engines.py` loader stub (validation only; auto-detect/
  start-stop out of scope this milestone). 5 tests.

**Total: 4 modules, 32 tests, 4 commits.** Remaining from the port-pick list:
EWMA pressure wired into the proxy's live GPU sampling (nvidia-smi poll — module
ready, poller not written), zeroconf live-LAN smoke test (mocked tests pass;
untested against a real second machine), dispatch not yet wired into proxy.py's
`/v1/chat/completions` (module ready, integration pending).

- **Fleet discovery + Ollama-compatible proxy expansion (T3):** LAN discovery of
  Ollama/llama.cpp nodes, registered into the provider grid with `local-fleet`
  provenance. PAIR's node discovery is the reference pattern; implement in our stack.
- **Request-level scheduling in the proxy (T4):** per-request tier choice → node →
  decision-log entry. Composes with T3; keeps the transparency differentiator.
- **Dogfood experiment (T5):** install PAIR, point Hermes's local endpoint at its
  Ollama-compatible endpoint, pool desktop (5070 Ti) + MacBook Air, measure
  request-level routing vs our single-box defaults; results → REAL-SAVINGS-PROOF.md.
- **Positioning citation (T1, done 2026-09-25):** COMPETITIVE-POSITIONING.md
  "Adjacent products" section. Case study: docs/PAIR-CASE-STUDY.md (T2).
