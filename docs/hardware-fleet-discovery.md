# Fleet Discovery & The "Download and Connect" Onboarding (design)

**Date:** 2026-09-22 | **Question (Gui):** How does the app make all the user's hardware
available? Scan like Tailscale? "Download Tierllama on each machine, log in, everything
shows up"? MVP or add-on?

## Live fleet status measured right now (proof the concept works)

| Machine | Tailscale IP | Reachable NOW | Blocker |
|---|---|---|---|
| Windows (this machine, classifier host) | 100.119.226.51 | ✅ | — |
| Box DESKTOP-0GIFKM1 | 100.73.6.74 | ✅ llama-swap :8080 OPEN | CPU-only (24.6s floor), execution lane only |
| MacBook Air | 100.98.166.109 | ❌ **asleep (Online: False)** | Mac is powered down/lid closed |
| Cloud (Ollama `:cloud`) | — | ✅ 0.7–1.0s | none — works today |

The Mac HAS Ollama installed (Gui confirms) + SSH + Hermes agent + Tailscale — it shows
in `tailscale status` but `Online: False`, last seen 16:30Z today. It is not unreachable;
it is asleep. Nothing for us to fix: when the Mac wakes, it reappears on the tailnet and
the same health-check that finds it will classify through it.

## The design Gui described = the Tailscale model, and we should copy it exactly

**User experience:** download Tierllama on each machine → log into the (same) account →
the machine appears in the fleet on every other machine's app. Cloud counts as an
always-available third "machine" (rented). That's exactly how Tailscale onboarding feels.

**How to build it (simplest + safest path):**
1. **Don't reinvent the mesh — use Tailscale's** (or any WireGuard mesh) as the optional
   transport. It's free for personal use (≤100 devices), battle-tested, and gives us
   identity + encryption + NAT traversal without writing a line of networking code.
2. **Each Tierllama install runs a tiny local agent** (localhost HTTP service) that:
   - registers with the account (login = signed token, stored locally)
   - exposes `GET /health` → {ollama_version, models[], free_vram, busy?}
   - accepts classify/dispatch jobs from the user's own machines only (tailnet ACLs).
3. **The app discovers peers via Tailscale's MagicDNS** (no IP entry by the user) +
   health-checks each peer for the classifier endpoint. Offline machines show as
   "sleeping" (Tailscale's own state), not errors.
4. **Waking sleeping Macs** is possible later (Tailscale supports Wake-on-LAN on some
   setups) — phase 3, not MVP.

## MVP or add-on? (Gui asked)

**Split it:** the MVP ships with (a) local GPU classifier + (b) key-free cloud lane —
both work on first run with ZERO onboarding — plus config-file listed peers
(`[peers]` = hostname + URL) for power users. That covers "use your hardware + cloud"
without any account system.
**Phase 2 (the real fleet feature):** the download-and-connect experience above with
accounts, because it needs a backend (identity, peer registry, auth). Estimated build:
the agent is small; the backend is the real work. Ship MVP first, fleet second —
consistent with our spec (hardware auto-discovery = phase 2, locked 2026-09-21).

## What's actually hard (honest assessment)
- Identity/account backend (sign-up, tokens, revocation) = the big chunk.
- NAT/firewall variance across users' networks = solved by riding Tailscale.
- Health checks + cold-start UX ("model is waking up") = small, fun work.

## Measured facts backing this plan
- Cloud classifier fallback: 0.73–0.99s (live).
- Box interactive routing: 24.6s tiny-prompt (rejected for interactive use; stays async).
- Mac: asleep at test time — will re-measure when Gui wakes it (expect ~0.1s RTT + load).
