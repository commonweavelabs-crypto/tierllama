# Customizable Routing + Model Oracle + Multi-Provider Linking (design)

**Date:** 2026-09-22 | **Source:** Gui's brainstorm (verbatim intent preserved)
**Status:** design for J7/J8/J10 — no product decisions needed from Gui to start.

## The three features (Gui's framing, verbatim intent)

### F1 — Customizable decision tree (user dropdowns per tier)
Gui: "there should be a drop down for each of Jev's decision and the user can go ahead
and if they don't want the suggested model, they can go ahead and customize their own."

**Design:** the decision tree is ALREADY data, not code — `config.py` LANES maps
difficulty→model. J6 made it a dict; the next step is making it a UI surface:
- Auto-assign on discovery: every discovered model (local via Ollama tags, cloud via
  provider listing) gets pre-filled into the dropdown by the Oracle (F2).
- User override: pick any discovered model for any tier (EASY/MEDIUM/HARD/SUPER-HARD ×
  NOW/LATER). Stored in config; the classifier never changes — only the lane targets.
- This is genuinely small: config already has per-lane model lists; adapters already
  take `model=` kwargs. The work is UI (J7) + config schema (v2, below).

### F2 — The Oracle: model capability + speed data (how to source it)
Gui: "we need to benchmark for speed on the user's hardware. That's very important."

**Two-layer design:**
- **Speed layer = MEASURED ON THE USER'S OWN MACHINE (the hard truth: benchmark scores
  from the internet don't tell you how fast YOUR GPU runs it).** `tierllama bench
  <model>` runs the classifier prompt + a fixed probe set (20 golden-set messages), and
  records tokens/s + decision accuracy into a local `models.json`. This also auto-runs
  once for every model discovered on first use — the "benchmark on discovery" flow.
- **Capability layer = community data (don't scrape, subscribe to it):** the JevBench
  / OpenSourceJev ecosystem already publishes classifier-suitability benchmarks
  (entry 270); for general capability, pull published benchmark tables (SWE-bench,
  MMLU, etc.) into a versioned JSON shipped with releases + refreshable from a URL.
  Structure: model_id -> {capability scores by task-type, context window, license}.
  **Never hard-code in the app** — ship a data file + updater, so new models arrive
  by data refresh, not code releases.
- **Suggestion algorithm (deterministic, auditable):** score = capability(tier) ×
  speed_on_user_hw × price. The router logs WHY a model was suggested — the oracle's
  output is a recommendation, and the log shows the numbers, so users can audit and
  override (F1). This is the transparency pattern we already use for savings.

### F3 — Multi-provider linking (beyond Ollama)
Gui: "we need to think about xAI, other providers that might want to link to this
router for model discovery."

**Design: one adapter interface, N provider configs.** The lane adapter signature is
already provider-agnostic (OpenAI-compatible HTTP). Add provider descriptors:
```toml
[provider.openai]
kind = "openai-compatible"
base_url = "https://api.openai.com/v1"
key_env = "OPENAI_API_KEY"      # key never in config, always env
models = ["luna", "terra", "astra"]   # or pulled from /models at discovery
```
Ollama = the zero-config default (already works); every other provider = a TOML block
+ key in env. The classifier stays qwen3:4b local — only DISPATCH targets change.
Gui's exact scenario works on day one of this feature: OpenAI-only user (Luna→EASY,
Terra→MEDIUM, Astra→HARD), then adds Ollama + a good local model, and LATER-tier tasks
flow to their local box instead of paid API — the Oracle re-suggests automatically
because speed+cost changed, and the user can veto in F1 dropdowns.

## Tier vocabulary change (Gui's "super hard")
Current: EASY/MEDIUM/HARD + NOW/LATER. Add **EXPERT** tier (the "3-trillion-parameter
astronomically expensive" class) — mapped to CLOUD_EXPERT lane, default = user's most
capable cloud model. The classifier gets a 4th difficulty enum + a few-shot example.
Measured impact needed before shipping (J2-style bench on the extended set).

## Milestone mapping (proposed)
- **J7 (Web UI):** F1 dropdowns + provider config UI (TOML under the hood) — the
  decision tree becomes visible and editable here. Include the speed-bench display.
- **J8 (Oracle v1):** capability data file + `tierllama bench` (on-device speed) +
  auto-suggest on discovery + suggestion logging.
- **J10 (Providers v2):** OpenAI/xAI/Anthropic TOML descriptors + key management +
  per-provider cost tracking in the decision log.

## Honest risks
- Benchmark tables scrape-break constantly; that's why the Oracle is a data file with
  a URL refresh, not a scraper.
- Provider model naming drift (Luna/Terra/Astra today, different tomorrow) → pull
  /models live per provider instead of hard-coding names.
- EXPERT tier risks threshold confusion with HARD — needs the measured bench first.


## Additions (Gui, 2026-09-22): thinking levels, learning router, task-type layer

### Model targets = model + thinking-level (J7)
Decision-tree targets are (model, thinking_level) pairs, not just models. Same model
appears at multiple rungs: Astra @ normal-thinking for HARD, Astra @ max-thinking for
EXPERT. The escalation ladder's climb is not always a different model - it can be the
same model at a higher thinking level (more expensive/call, still cheaper than a
stronger model the user doesn't have). Config schema v2:
```toml
[[tier]]
difficulty = "HARD"
target = { provider = "openai", model = "astra", thinking = "normal" }
[[tier]]
difficulty = "EXPERT"
target = { provider = "openai", model = "astra", thinking = "max" }
```

### Learning router (cheap version first)
The decision log already records every escalation. Add a local feedback table:
message-shape -> (tier, attempts-before-escalation). Next similar message retries
fewer times before climbing (e.g. HARD 3 attempts -> 2 for shapes that historically
needed EXPERT). Stored locally, per-user, auditable. Actual classifier fine-tuning
from failures = phase 3.

### Task-type dimension: NOT a classifier dimension (yet) - Oracle data instead
Difficulty already captures most of it (coding is rarely EASY -> lands HARD/EXPERT ->
capable models). Cross-model specialty choice belongs to the Oracle's per-task-type
capability scores (already in F2 design). Sequence: ship task-type in Oracle data,
measure whether routing choices actually change, only then consider a 5th classifier
dimension. Complexity without measured routing delta = rejected for now.


## Additions (Gui, 2026-09-22): auto-tune button + advanced settings

### UI: decision tree moves under Advanced settings
Default UX = zero decisions (install -> scan -> done). Tree editor behind an
"Advanced" panel w/ "tweaks are optional" note. J7.5 polish item.

### The Optimize button (J8 core, Gui's vision)
One button + progress bar: scan hardware -> probe every discovered model
(golden-set through each, graded) -> measure on-device speed -> write suggestion
matrix -> pre-fill the decision tree. User tweaks only if advanced.
Status: speed data ALREADY collecting (proxy.jsonl logs per-call latency per
model per machine: 32 calls logged). Competence score = `tierllama bench`
(golden set through each model once, graded).

### SEED not SIMULATE (pushback accepted-pending)
No synthetic dataset. Cold-start = curated seed table (task-type x difficulty ->
capable models, from public benchmarks, versioned data file w/ URL refresh).
Real user measurements OVERWRITE seed entries as they accumulate. Every
suggestion shows its source: "seed" or "measured (n calls)". Transparency rule
applies to recommendations, not just marketing claims.


## Clarification (Gui, 2026-09-22): "synthetic seed" = public benchmarks + common-sense priors

### The seed table (cold-start recommendations)
- Public benchmark data (never the model's own claims) + common-sense priors
- Common-sense rules baked in:
  1. CLOUD models = default-NOW (expert-run hardware, trust speed; only network
     latency ping, no speed probes)
  2. LOCAL models = default-LATER unless proven fast (5 timed probes: probe 1 =
     cold load, probes 2-5 = steady state)
  3. Ornith case (fast, low-competence 9B) -> EASY/NOW local
  4. Box 27B case (slow, capable) -> LATER jobs, never NOW

### The two-knob matrix (explainable)
- SPEED decides NOW vs LATER (measured, 5 probes, local only)
- COMPETENCE decides EASY/MEDIUM/HARD/EXPERT (per-difficulty graded check)
- "hi" probes != real workload: bench classifies NOW/LATER from probes; job-scale
  data (multi-hour box jobs, tool-heavy prompts) accumulates from real usage

### Phase 2 (aggregate flywheel)
Opt-in anonymized telemetry -> compacted per (model, hardware-class) ->
improves everyone's seed table over time. Real user data condensing into
decisions - Gui's words, the long-term moat.


## J8 additions (Gui, 2026-09-22): combined bench protocol + seed/measured blend

### Combined probe protocol (latency + competence in ONE pass)
Per local model:
1. Cold-load capture (model fully unloaded -> load time measured)
2. EASY probe (short prompt) -> latency + graded answer
3. MEDIUM probe -> latency + graded answer
4. HARD/EXPERT probe (longer, tool-use style) -> latency + graded answer
Single pass yields: cold-load s, steady-state tok/s, per-difficulty competence.
Every probe does double duty - no wasted runs.

### Scale disclaimer (UI)
Progress bar shows per-model estimate: "N models x ~40s each - this can take
~X minutes with N local models." Scan duration scales with model count (5 local
models = fine; 20 = long). Disclaimer shown BEFORE starting + live progress.

### Blending seed vs measured (Gui's averaging question)
- Seed = ordinal prior (which model is generally more capable, from public benches)
- Measured = the ground truth ON THAT HARDWARE - hardware can flip a model's
  real ranking (his point exactly)
- Rule: MEASURED wins when n >= 3 probes; seed only fills gaps (no measurement
  yet). No blind averaging - averaging an ordinal (online bench rank) with an
  interval (measured tok/s) mixes units. Instead: seed sets the starting tree,
  bench results overwrite per (model, machine). Conflict = measured wins, seed
  shown greyed out with its rank for reference.


## J8 addition (Gui, 2026-09-22): data collection - graceful, legal, user-friendly

### Two-tier data story (baked into the scan/optimize flow)
TIER 1 - LOCAL (always on, default): bench results + decision log stay on the
user's machine, used ONLY to improve THEIR recommendations and routing.
Consent wording at first scan:
  "Tierllama saves these results on your machine to improve your routing.
   Nothing leaves this computer unless you allow it."
TIER 2 - SHARED (opt-in, never pre-checked): anonymized telemetry
  (model name+quant, hardware class [GPU model / VRAM bucket / CPU],
  latency + competence scores, NO prompts, NO message text, NO IPs).
  Checkbox at scan: "Help improve Tierllama: share anonymous performance data"
  + link to the telemetry page listing EXACTLY the fields.
Design principles:
- Local-only is the default; sharing is a separate explicit choice (consent at
  the moment it's relevant - when data of value is being created)
- The scan itself asks nothing personal - hardware/model facts only
- Dashboard shows what was shared last ("last telemetry: 3 records, 9/22")
- One-click revoke; data already sent is aggregated+compacted (can't un-send,
  so say so plainly)
- GDPR-friendly shape: explicit, purpose-bound, minimal, revocable
PRIVACY.md updated in the same milestone (J8).
