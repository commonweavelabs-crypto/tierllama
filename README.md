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

Measured: 94.2% classification accuracy @ ~80ms; 83% token-cost savings at perfect
routing; fresh install routes in under a minute.

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

## License
Apache-2.0 (open core). Enterprise tier: managed cloud routing + dashboards (later).
