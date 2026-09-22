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
