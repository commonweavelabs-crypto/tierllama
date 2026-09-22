# Tierllama (working name Jevllama)

Jev-powered local model router: a sub-second classifier reads each message and routes it
to the cheapest lane that can do the job - local first, cloud only when it earns its cost.

**Easter egg: yes, we considered "Jev-o-llama". Gui won.**

## Status
J1 (router core skeleton) COMPLETE 2026-09-21: 20/20 role accuracy @ 0.46s avg on the
live acceptance set; decision log at `logs/decisions.jsonl`.

## Usage
    python cli.py route "click export and set format to mp4"
    python cli.py tail

## Layout
    tierllama/config.py      lanes, models, confidence threshold
    tierllama/classifier.py  qwen3:4b one-call scorer (role/difficulty/timing + conf)
    tierllama/router.py      message -> classify -> lane -> decision log
    cli.py                   route | tail
    logs/decisions.jsonl     append-only decision log

## License
Apache-2.0 (open core). Enterprise tier: managed cloud routing + dashboards (later).
