# Tierllama (powered by Jev)

**A Jev-powered router that always picks the best model for the job — and saves you money doing it.**

> **Status: v0.9-beta** — core routing, tuning, 9 providers, and installers are real and measured. We're hardening the classifier rubric against real traffic before calling it 1.0. See [STAGE-ASSESSMENT.md](docs/STAGE-ASSESSMENT.md).

## Our mission
Make compute available to everyone by using our resources better. Tierllama routes
every AI call to the cheapest model that can do the job — your local GPU first, cloud
only when it earns its cost — so people get the most out of their own hardware AND their
subscriptions. Less waste, cheaper AI, for everyone.

*(Easter egg: yes, we considered "Jev-o-llama". Gui won.)*

## What it does
A fast Jev-class classifier (qwen3:8b) reads every incoming message, decides what kind of request it
is (role/difficulty/timing) with REAL probabilities read from token logits, and routes
it to the right lane: local model, cheap cloud, expensive flagship, or overnight batch
queue. Failures auto-escalate up the ladder. Every decision logged.

**Measured savings: 77.8% token-cost reduction** on our 120-message real-world
workload (Sep 21-era classifier; may vary with traffic mix — every assumption
published in [docs/REAL-SAVINGS-PROOF.md](docs/REAL-SAVINGS-PROOF.md)). Classifier
accuracy: 94.2% @ ~80ms was the original 4b rubric v1; the current brain is
**qwen3:8b (80.0% exact-tier on the 211-case bench, ~3s median on GPU)** —
see [docs/JEV-BRAIN-DECISION.md](docs/JEV-BRAIN-DECISION.md) for the full
decision record and why the brain grew.

## Fresh install (Windows)
    git clone https://github.com/commonweavelabs-crypto/tierllama.git
    cd tierllama
    # requires: Python 3.11+, Ollama 0.35+ running locally with the Jev brain pulled
    ollama pull qwen3:8b        # the Jev brain (5.2GB, Apache-2.0)
    python cli.py route "click export and set format to mp4"
    python cli.py discover    # find every Ollama/llama-swap on your LAN (no accounts!)
    python cli.py doctor      # validate config + box queue canary
    python cli.py tail        # decision log (masked)

## Layout
    tierllama/config.py      lanes, models, confidence threshold
    tierllama/classifier.py  JeV-class classifier (qwen3:8b, logprob scorer, injection-hardened)
    tierllama/router.py      message -> classify -> lane -> dispatch/escalate -> log
    tierllama/adapters.py    LOCAL / CLOUD / BOX dispatch adapters
    tierllama/ladder.py      escalation ladder (J4)
    tierllama/discover.py    Tier-0 LAN discovery (J5)
    cli.py                   route | tail | discover | doctor
    logs/decisions.jsonl     decision log (stays local — see docs/PRIVACY.md)
    docs/                    findings + specs (tech + plain-language per milestone)

## Minimum system requirements
- ~5.2GB disk + ~6GB free VRAM for the Jev classifier brain qwen3:8b (any CUDA/Apple GPU; auto-unloads after 5 min idle; a hardware gate in the dashboard reports real VRAM state)
- Python 3.11+ and [Ollama](https://ollama.com) (free) 0.35+ with the Jev brain pulled — no accounts, no API keys
- Optional: more Ollama machines on your LAN (auto-discovered), cloud keys for non-Ollama providers
- Full details: docs/REAL-SAVINGS-PROOF.md

## License
Apache-2.0 (open core). Enterprise tier: managed cloud routing + dashboards (later).

## Web dashboard

python cli.py serve -> http://127.0.0.1:8848

## Tierllama vs. cloud-only routers (OpenRouter & friends)

Cloud routers like [OpenRouter](https://openrouter.ai) are great at what they do — and Tierllama deliberately rides them as one lane among nine. But their Auto Router is **cloud-only by definition**:

| | Tierllama | Cloud-only routers |
|---|---|---|
| **Local models** | ✅ Routes to your GPU first — cheapest lane is often **$0** | ❌ Cloud-only; every call costs money |
| **Your hardware fleet** | ✅ Your machines, your box, overnight queues | ❌ No concept of "your GPU" |
| **Routing data** | Measured **on your machine** (cold loads, real latency) + benchmarks | Market spend-share (what others pay for) |
| **Privacy** | Routing local, log local — no third party sees prompts | Every prompt transits their API |
| **Transparency** | Visible, editable decision tree + provenance per tier | Black-box router |

**The short version:** cloud routers optimize *other people's* cloud models. Tierllama optimizes **everything you have** — starting with the hardware you already own.

