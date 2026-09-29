# REAL-SAVINGS-PROOF.md — T5 PAIR dogfood (2026-09-29 evening)

## Setup (2-machine PAIR cluster, all facts from live run)
- **Machines:** Windows desktop (5070 Ti, DESKTOP-SHN3HMJ, node b7965584) + MacBook Air (Guilhermes-MacBook-Air.local, node d85360e5). Both ran PAIR v0.1.1 service binaries (installed from ~/pair-bin / pair-win, no system install).
- **Stack wiring (runbook finding):** do NOT hand-run ollama-proxy — run ONLY nvpair-ui-broker under tmux/pty; it spawns and wires the whole stack. All binaries are stdio JSON-RPC and need a live client; tmux holds stdin.
- **Cluster formation:** nvpair-cluster-manager mints certs; trust exchange = `{nodeUuid, certPem}` pin files, filename == nodeUuid, both sides. Pins exchanged via peer DM + Google Drive transport (DM transport mangles base64 — Drive is the reliable path).
- **mTLS + discovery:** automatic via mDNS once pins loaded. mDNS saw the Mac node BEFORE clustering.

## Results (mac-side runner, moondream baseline vs qwen3:4b cross-node)

| Mode | Wall | OK | Notes |
|---|---|---|---|
| baseline (mac-local moondream) | 10-15s | 10-11/12 | 0.05-1.6s latencies, 17-81 tok/s |
| pair 2-machine (qwen3:4b cross-node) | 142s | 5/12 with retry-backoff | short 2.6s / medium 15.9s / long 42.9s, 8-12 tok/s over mTLS |

## Findings (the actual T5 answers)
1. **Capability expansion works:** the cluster made Windows-only models (qwen3:4b) reachable from the
   Mac - a capability single-box does not have. Cross-node round trip verified BOTH directions
   conceptually: Mac requested a Windows model and got a real completion over mTLS.
2. **Pair 0.1.1 is ALPHA-quality for reliability:** routing snapshots flap (~every 30s the node
   advertisement drops for 2-5s); requests in the gap get instant rejects ("no node advertises").
   With client retry-backoff (what a real client would do) 5/12 got through vs 0/12 before.
   The 89-open-issues question answered empirically: real, but young. PAIR-stops/we-start findings
   confirmed; also PAIR is Ollama-NEW-layout incompatible (wants separate llama-server; we placed
   one at the checked path to unblock).
3. **Latency cost of cross-machine routing is real:** 8-12 tok/s vs 17-81 local (LAN mTLS + engine
   cold-load each request because PAIR tears down engines). For LOCAL-lane work (conversational,
   NOW-timing), single-box wins. For overnight DEFERRED work across machines, reliability > latency
   and the capability gap matters more than tok/s.
4. **Tierllama takeaways** (all four differentiators STILL unmatched by PAIR — re-verified):
   PAIR has no tier/cost policy, no per-machine bench, no visible decision log, no cloud tier.
   PAIR's anti-flap liveness (J12+ T3) is where Tierllama must go FURTHER: our vouching-liveness
   design directly addresses the flapping that ate this benchmark.

## What this proves for Tierllama
- The LAN-fleet lane (J5 discovery + local-fleet) is real and works cross-vendor today.
- The production risk list for Tierllama's scheduler: model cold-load windows must be advertised
  honestly (a job routed during a cold load should say "starting", not silently fail).
- Retry-on-no-node belongs in OUR dispatch budget rules (already supported: dispatch.py retryable
  statuses) - validated as necessary by PAIR's flapping.

## Raw data
- t5_results_mac.json (final) + preserved prior runs: ~/pair-bin/ on the Mac, copied to Drive at
  Hermes-Shared/pair-cluster/. Bench script: bench_t5_mac.py (retry-backoff, serial mode).
- Windows side artifacts: %LOCALAPPDATA%/hermes/projects/pair-dogfood/ (binaries, logs, broker pty).
