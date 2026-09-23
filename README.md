# Tierllama (powered by Jev)

**A Jev-powered router that always picks the best model for the job — and saves you money doing it.**

## Our mission
Make compute available to everyone by using our resources better. Tierllama routes
every AI call to the cheapest model that can do the job — your local GPU first, cloud
only when it earns its cost — so people get the most out of their own hardware AND their
subscriptions. Less waste, cheaper AI, for everyone.

*(Easter egg: yes, we considered "Jev-o-llama". Gui won.)*

## What it does
A sub-second classifier reads every incoming message, decides what kind of request it
is (role/difficulty/timing) with REAL probabilities read from token logits, and routes
it to the right lane: local model, cheap cloud, expensive flagship, or overnight batch
queue. Failures auto-escalate up the ladder. Every decision logged.

**Measured savings: 77.8% token-cost reduction** on our 120-message real-world
workload, landing within 0.1% of the theoretical ideal — with every assumption
published in [docs/REAL-SAVINGS-PROOF.md](docs/REAL-SAVINGS-PROOF.md). Classifier
accuracy: 94.2% @ ~80ms (benchmarks with n + scope published — we publish what the
numbers do NOT claim, too).

## Fresh install (Windows)
    git clone https://github.com/commonweavelabs-crypto/tierllama.git
    cd tierllama
    # requires: Python 3.11+, Ollama running locally with qwen3:4b pulled
    ollama pull qwen3:4b
    python cli.py route "click export and set format to mp4"
    python cli.py discover    # find every Ollama/llama-swap on your LAN (no accounts!)
    python cli.py doctor      # validate config + box queue canary
    python cli.py tail        # decision log (masked)

## Layout
    tierllama/config.py      lanes, models, confidence threshold
    tierllama/classifier.py  qwen3:4b logprob scorer (SemIf-style prefill, injection-hardened)
    tierllama/router.py      message -> classify -> lane -> dispatch/escalate -> log
    tierllama/adapters.py    LOCAL / CLOUD / BOX dispatch adapters
    tierllama/ladder.py      escalation ladder (J4)
    tierllama/discover.py    Tier-0 LAN discovery (J5)
    cli.py                   route | tail | discover | doctor
    logs/decisions.jsonl     decision log (stays local — see docs/PRIVACY.md)
    docs/                    findings + specs (tech + plain-language per milestone)

## Minimum system requirements
- ~4GB free VRAM for the classifier (any CUDA/Apple GPU; auto-unloads after 5 min idle)
- Python 3.11+ and [Ollama](https://ollama.com) (free) with `qwen3:4b` pulled — no accounts, no API keys
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

