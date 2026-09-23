# Competitive positioning: Tierllama vs cloud-only routers
_Researched 2026-09-22 from OpenRouter docs + blog. Use this when making our
case in ads, README, or conversations._

## What OpenRouter's Auto Router does (verified, their docs)
- Classifies prompts into ~30 task types with a fast classifier
- Ranks models by **7-day community spend share** ("wisdom of the market")
- `cost_tier` low -> max = cheapest-capable -> most-capable (mirrors our
  PRICE/QUALITY optimizer modes)
- Provider fallbacks, conversation memory, model restrictions
- `:nitro` (speed) / `:floor` (cost) model-string shortcuts

## Where we SUCCEED / EXCEED (the case we make)
1. **Local-first economics** - our cheapest lane is $0 (user's GPU); theirs
   never is. The 77.8% measured savings depends on local-first routing that
   cloud routers structurally cannot do.
2. **Hardware fleet** - we route to the user's Ollama machines, llama-swap
   boxes, overnight queues. They route to *their* cloud only.
3. **Measured-per-machine data** - 5-probe bench (cold load + steady tok/s) on
   the user's actual silicon vs aggregate market spend. Our recommendations
   are true on THEIR hardware, not on average.
4. **Privacy** - classifier + routing run locally; decision log stays on disk;
   no third party receives prompts. (Their router sees every prompt.)
5. **Transparency + control** - visible decision tree, per-tier provenance
   (seed/measured/user), per-tier override consent. Theirs is a black box.
6. **Optimizer intent** - explicit PRICE vs QUALITY modes with preview diffs.

## Honest concessions (where they lead)
- Market-spend signal >> our seed table for cloud model ranking
  (our answer: telemetry flywheel, opt-in, phase 2)
- Battle-tested provider fallback chains
- Zero-infra convenience: one key, no local setup

## Strategic stance
OpenRouter = a LANE in our provider grid, not a rival. Easy work goes to free
local models they cannot see; hard work escalates to their 500+ model catalog.
We are the layer ABOVE them when the user owns hardware, and the privacy-first
alternative when they don't.

## Other providers researched 2026-09-22
- NVIDIA NIM: OpenAI-compatible, free trial tier - candidate 10th provider
- Amazon Bedrock / Azure OpenAI: NOT natively OpenAI-compatible (AWS SigV4 /
  Azure auth) - would need dedicated adapters; deferred until demand


## CORRECTION (Gui caught it, 9/22): the REAL Jev
Gui remembered videos about Jev's creator. Verified:
- **Jev = TypeSafe AI's System One model** (released 9/15/2026, $40M seed led
  by DCVC), founded by **Diogo Almeida - ex-OpenAI, co-creator of RLHF
  (the method behind ChatGPT)**
- Jev cannot generate text: it returns TYPED DECISIONS (choice/score/
  probability) with calibrated confidence in 70-500ms. Zero hallucination
  by construction.
- Pricing: $0.042/Mtok input, OUTPUT FREE (~$0.00002/decision)
- API: POST https://api.typesafe.ai/v1/systemone, Bearer TYPESAFE_API_KEY,
  model jev-latest (early access, rolling waves)

### Why this matters to our story
We INDEPENDENTLY built a Jev-style router (typed decisions from a tiny
classifier) and named it after the idea. The name was prescient.
Quantified differentiator vs OpenRouter: their Auto Router spends LLM tokens
per routing decision; a Jev-style classifier costs ~$0.00002/decision.

### Built (J11): the featured Jev card
- Full-width top card in Providers tab: what Jev is, LOCAL brain (qwen3:4b,
  free, status dot) vs JEV CLOUD (official TypeSafe, secure key input)
- tierllama/jev_cloud.py: native /v1/systemone adapter (3rd protocol) as
  classifier fallback for users without hardware; logs to costs.jsonl
- Local brain source: ollama registry qwen3:4b (content-addressed digests =
  hash-verifiable pulls)
- Note: TypeSafe API is early-access (keys in waves)
