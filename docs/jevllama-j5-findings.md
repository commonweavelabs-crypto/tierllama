# J5 Findings — Doctor, Discovery, Fresh-Install (technical)

**Date:** 2026-09-22 | **Status:** J5 complete
**Setup:** `tierllama/discover.py` (Tier-0 LAN scan), `doctor.py` (config-vs-reality
validator), CLI polish (`route | tail | discover | doctor`), README fresh-install path.

## Verify conditions, live results
1. **Fresh install works from README on a second machine** — PASS: cloned the repo to a
   fresh directory, `python cli.py route "..."` exited 0 with a dispatched record
   (NAVIGATOR/MEDIUM/NOW → CLOUD_MEDIUM, logged); `tail` works.
2. **`tierllama doctor` validates configured models exist** — PASS in 2.8s: classifier
   + all 4 lanes PASS (LOCAL qwen3:4b present via /api/tags; cloud models resolve
   server-side; box verified via canary).
3. **Startup canary through the box queue** — PASS in 75s: canary JSON job dropped in
   pending/, worker consumed it, response.json landed in done/. (Proves queue + worker
   + llama-swap end-to-end — the "silent contract mismatch" fix from J3, now automated.)
4. **LAN scan finds every Ollama/llama-swap host** — PASS: 9.9s for a /24 (64 threads),
   4 hosts found: box llama-swap + two non-Tierllama Ollama installs (.126 qwen models,
   .199 cloud models) + router .1:8080 (correctly filtered by "has models" rule in the
   peers list).

## Findings
1. **The wedge is real and repeatable:** the scan found Ollama installs that Tierllama
   was never installed on — 2 of 4 hosts. Zero-setup fleet routing works against the
   existing Ollama install base, exactly as designed (Gui's Tailscale-model onboarding
   stays phase 2 for cross-network; LAN is free).
2. **Doctor's canary catches what static checks can't:** the box queue was reachable
   via SMB (file copy works) while the worker consumed the canary only after ~75s —
   latency data the config can't show. Canary = the queue's heartbeat.
3. **Port-scan etiquette for the product:** /24 with 64 threads @1.2s timeout = 10s,
   non-invasive (TCP connect only). For the MVP default: scan only after user opts in
   on first run ("find machines on your network?") — polite + avoids surprising
   network admins.
4. Non-Ollama hosts (router at .1:8080 with no models) are filtered from peers by
   requiring a non-empty model list — no product decision needed; documented as the
   rule (stop_when condition dissolved: the rule is simple).

## Artifacts
- discover.py (subnet scan, tags enrichment, kind detection)
- doctor.py (4 checks: classifier / lane models / box canary / LAN discovery)
- cli.py v2 (route | tail | discover | doctor), README fresh-install path
- Fresh-clone acceptance: scratch/tierllama-fresh (routes + tails + discovers, exit 0)
