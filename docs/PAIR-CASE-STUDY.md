# NVIDIA PAIR (Personal AI Router) — Tierllama case study + feature extraction

_File added 2026-09-25. Source: NVIDIA/Personal-AI-Router (GitHub, Apache-2.0, Go,
★1,503, pushed 2026-09-23) + nvidia.com PAIR pages + NVIDIA developer blog (Sep 3,
2026). Archive entry: ig-ddc44crwjl2x (Hermes-Shared link-archive, verdict worth-it)._

## Why this is the strongest external validation we have

NVIDIA — the company that ships the silicon most of our users route to — has
productized "route inference across a home fleet of heterogeneous machines." That is
Tierllama's hardware-fleet thesis (COMPETITIVE-POSITIONING.md, "Hardware fleet" point 2),
now official. We should use PAIR three ways: as a **market-validation citation**, as a
**reference architecture** for specific Tierllama features, and as a **dogfood target**
on Gui's own desktop + MacBook Air network.

## License posture (Apache-2.0 — what we may and may not do)

Apache-2.0 is permissive: we MAY study, run, fork, embed, and ship derivatives inside
Tierllama, commercial included, with NOTICE/attribution preserved (keep NVIDIA
attribution in any derived files; do not use NVIDIA trademarks to imply endorsement).
Practical rule for us: **port ideas into our own architecture, don't import the Go
codebase** — Tierllama is Python/TS and we want one codebase. Inspiration-first, same
as the Cookbook call.

## What PAIR does (verified, the design surface worth mining)

- Node discovery on the LAN (machines join a home cluster)
- Manages supported inference engines per node
- Presents **Ollama-compatible + OpenAI-compatible proxy endpoints** — existing apps
  and agents work unchanged
- Routes **independent requests** across devices (request-level scheduling; a model
  instance runs on one device per request — not tensor-parallel splitting)
- All prompts/files/agent context stay on the home network (privacy stance matches ours)

## Actions for Tierllama (ordered, concrete)

**T1. Citation in COMPETITIVE-POSITIONING.md (do now, ~15 min).**
Add a short "Adjacent products" note: OpenRouter = cloud lane; PAIR = NVIDIA's
home-fleet router (validated our fleet thesis; LAN-only, no tier pricing, no cloud
providers). Frame: "the layer ABOVE both" — PAIR proves the hardware-fleet lane,
OpenRouter proves the cloud lane; Tierllama uniquely prices/tiers across both. No
code dependency.

**T2. Case study / use-study doc (docs/PAIR-CASE-STUDY.md) — the "why us vs PAIR" page.**
- Where PAIR stops and Tierllama starts: tier-based routing (PRICE/QUALITY modes),
  measured-per-machine bench (5-probe), decision-log transparency, cloud escalation
  with one key. PAIR has none of those — it's a scheduler, we're a policy layer.
- Positioning line for README/ads: "PAIR pools your machines; Tierllama decides
  what each request is worth and sends it to the right tier — local fleet first,
  cloud when justified."
- This doc is also Compute-Fund-adjacent evidence: a frontier lab shipping a local
  router is a market signal for the Compute Fund narrative.

**T3. Feature: fleet discovery + Ollama-compatible proxy (inspired-by, port the pattern).**
Our existing `tierllama-local` proxy (dogfooded on :8846) grows a discovery module:
- SSDN/mDNS-style LAN discovery of Ollama/llama.cpp nodes (PAIR's discovery is the
  reference; implement in our stack)
- Register nodes into the existing provider grid with a `local-fleet` provenance
  (fits the per-tier provenance model we already have: seed/measured/user)
- No fork of PAIR needed — we already speak Ollama; discovery is the missing piece.

**T4. Feature: request-level scheduling in the proxy.**
PAIR routes independent requests to the best device. Our proxy currently fronts one
local llama-swap/Ollama; add multi-node dispatch with our existing decision log:
per-request tier choice → node → record in the visible decision tree. This composes
with T3 (fleet) and stays consistent with our transparency differentiator.

**T5. Dogfood: point Hermes's local endpoint at a PAIR-managed cluster (2-machine test).**
Gui's desktop (5070 Ti) + MacBook Air both run Ollama. Install PAIR, point Hermes
config at its Ollama-compatible endpoint, measure: does request-level routing beat
our single-box defaults for overnight multi-agent work? Write results into
REAL-SAVINGS-PROOF.md as a PAIR section. (Also answers the 89-open-issues question
empirically before we depend on anything.)

**T6. Watch item, not blocker.**
89 open issues, project is young but NVIDIA-official. Revisit cadence at Tierllama
router-work resume (J12+). If PAIR gains tier/cost policy, re-evaluate positioning.

## What we can NOT take from PAIR

- Tensor-splitting: it doesn't do it; not a feature to chase.
- Their Go code: Apache-2.0 permits it, but we stay Python and port patterns only.
- LAN-only assumption: our design intentionally spans local + cloud tiers — keep that
  as the differentiator, never narrow it.

## Where this lands in the Tierllama roadmap

- T1: immediate (positioning doc)
- T2: docs task, fits the next doc batch (mini-box overnight job candidate)
- T3+T4: J12+ router milestones (after current telemetry/oracle work)
- T5: standalone experiment, any evening; feeds REAL-SAVINGS-PROOF.md