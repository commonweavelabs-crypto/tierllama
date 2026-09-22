# Tierllama (working name Jevllama)

Jev-powered local model router: a sub-second classifier reads each incoming message
and routes it to the CHEAPEST lane that can do the job — local first, cloud only when
it earns its cost. Every decision logged with real probabilities.

**Easter egg: yes, we considered "Jev-o-llama". Gui won.**

## Status (2026-09-22)
J1-J4 complete: router core (100% role acc @ 0.46s), logprob classifier (94.2%),
lane adapters (local/cloud/box live-verified), escalation ladder (2.9s auto-recovery
from forced failure). J5 (doctor + discovery) active.

## Fresh install (Windows)
    git clone <this repo> tierllama
    cd tierllama
    # requires: Python 3.11+, Ollama running locally with qwen3:4b pulled
    ollama pull qwen3:4b
    python cli.py route "click export and set format to mp4"
    python cli.py discover    # find every Ollama/llama-swap on your LAN
    python cli.py doctor      # validate config + box queue canary (up to 5 min)

## Layout
    tierllama/config.py      lanes, models, confidence threshold
    tierllama/classifier.py  qwen3:4b logprob scorer (SemIf-style prefill)
    tierllama/router.py      message -> classify -> lane -> dispatch/escalate -> log
    tierllama/adapters.py    LOCAL / CLOUD / BOX dispatch adapters
    tierllama/ladder.py      escalation ladder (J4)
    tierllama/discover.py    Tier-0 LAN discovery (J5)
    cli.py                   route | tail | discover | doctor
    logs/decisions.jsonl     append-only decision log
    docs/                    findings + specs (tech + plain-language per milestone)

## License
Apache-2.0 (open core). Enterprise tier: managed cloud routing + dashboards (later).
