# Real Savings — Measured, Not Claimed

*How we computed the savings on this page, with every assumption in the open.*

## The measured result (2026-09-22, live on this repo's own router)

| Scenario | Cost per 1M workload tokens | Saved vs always-best |
|---|---|---|
| Always the best model (kimi-k3 for everything) | **$1,246.15** | — |
| **Tierllama routing (measured)** | **$276.27** | **77.8%** |
| Ideal routing (theoretical ceiling) | $275.84 | 77.9% |

**The measured router lands within 0.1% of the theoretical ideal.** That's the whole
point of the architecture: cheap mistakes (J1 finding) + escalation (J4) mean the
errors that survive cost almost nothing.

## How this test was run (reproduce it)
1. Workload: 120 real user messages (the repo's golden set - roles from DIRECTOR to
   NAVIGATOR, including 20 designed ambiguity traps). Total ~150K tokens at typical
   chat shape (250 in / 400 out per message).
2. Route each through the actual classifier in this repo (qwen3:4b, logprob path).
3. Price each lane at live verified rates: local $0; glm-5.3-flash:cloud $0.15/$0.60
   per M in/out tokens; kimi-k3 $3.00/$15.00; box queue $0 (own hardware).
4. Compare against the always-best baseline: every message to kimi-k3.

## What this does NOT claim (honesty section)
- Savings apply to WORKLOADS WITH TIERABLE REQUESTS. If every message you send is
  genuinely HARD, routing can't help you (you'd pay the strong-model price anyway;
  you'd only save the ~0.1s classifier check).
- Costs are model-API prices only. The local lane costs electricity (~negligible:
  4B model on a gaming GPU is a rounding error next to a GPU rendering job).
- Your mix matters: our 120-msg set has 40% easy/local traffic. Heavy-bug-report
  workloads will route more to cloud. The router logs every decision - run
  `tierllama tail` on YOUR workload to see YOUR numbers.
- Latency trade-off: EASY messages go to local models that are cheaper but can be
  less capable. That's the deal - you chose the trade with the confidence threshold.

## Minimum system requirements (local routing)
- **GPU:** any card with ~4GB free VRAM for the classifier (measured on RTX 5070 Ti;
  model qwen3:4b quantized). CPU-only works but adds ~20-25s per decision (rejected
  for interactive use; fine for overnight lanes).
- **RAM:** ~4GB free beyond your normal workload while the classifier is loaded;
  it unloads automatically after 5 min idle.
- **OS:** Windows/macOS/Linux wherever Ollama runs.
- **Software:** Python 3.11+, Ollama (free) with qwen3:4b pulled. No accounts, no API
  keys for the local+Ollama-cloud lanes.
- **Optional:** second machine with Ollama for extra lanes (discovered automatically
  on the LAN, no setup); cloud keys only if you bring non-Ollama providers.

## Where the numbers come from
- Classifier accuracy: 94.2% on the 120-message golden set (docs/jevllama-bench-01.md,
  j2-findings.md - with n, scope, and p-values published).
- Prices: provider pages checked 2026-09-21 (docs/SPECS/tierllama-decisions.md).
- Every decision logged locally: `logs/decisions.jsonl` - audit us.
