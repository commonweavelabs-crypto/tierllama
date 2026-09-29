# J24-SEC — Secure Fleet (secure exposure + pairing) — SPEC SKELETON
#project/tierllama #spec-skeleton #security #j24-sec

> Status: SKELETON spec, drafted 2026-09-29 (Gui approved planning during brainstorm).
> NOT built yet. Ships after the debug session + polish backlog. Must pass a security
> review checklist before any exposure milestone merges.

## Product promise (Gui, verbatim intent)
One toggle: "Secure Fleet: ON". "The user should just plug in — find their endpoints,
providers, models, hardware — like a snap. That's what Tierllama is." Never a VPN config;
never a terminal; no Tailscale required (but supported when the user already has it).

## Threat model (researched 2026-09-29, sources in roadmap side-notes)
IN scope (what this feature defends):
- Discovery spoofing: a compromised LAN device answering the fleet shout
  (mDNS/LLMNR poisoning — documented, unauthenticated protocol layer)
- Prompt/data interception between fleet machines (traffic rides LAN plaintext by default)
- Compute theft / model exfiltration if exposure ever crosses LAN boundaries
OUT of scope (by design decision, Gui):
- Public-internet exposure (never default; explicit, separate, review-gated)
- Off-network access (Tailscale is the answer; we support, don't rebuild)

## Design (3 pieces, zero-crypto-math custom)
1. **Node identity (zero-touch):** the tierllama engine process generates a keypair at
   first install. User involvement: none. Identity = node-uuid + cert; fingerprint
   shown in the dashboard (like PAIR does).
2. **Pairing handshake (the one user moment):** new device shows a 6-character visual
   code; user types/confirm it on the main machine; mutual cert pinning completes.
   Revoke = delete the pin row in the dashboard. Expire = long-lived certs (years),
   rotation prompt in dashboard. Pattern proven live 2026-09-29 (PAIR cluster pins
   exchanged + verified on both our machines).
3. **Secure transport (default hard):** all fleet traffic rides mTLS with pinned leaf
   certs, LAN-bound; no plaintext accepted from non-loopback (PAIR's rule, good one);
   broadcast discovery carries NO secrets — only fingerprints to match.

## Toggle semantics (consent pattern copy)
- OFF (default): node discovers others (read-only, safe) but does NOT advertise
  itself and rejects everything non-local. Copy: "Your machine stays invisible."
- ON: advertises + accepts pinned-pair traffic only. Copy: "Visible to machines
  you've paired. Encrypted. Never public."

## MVP cut of the security feature (what v1 ships)
- Keypair + fingerprint display
- Pairing code handshake (1 machine + this machine)
- mTLS transport for tierllama-to-tierllama traffic only
- Pin management UI (list/revoke) + the toggle
- Security review checklist passed: (a) no secrets in discovery, (b) no plaintext
  accept from non-loopback when ON, (c) pin revocation effective < 60s, (d) no
  public binding without explicit second toggle, (e) threat model doc reviewed

## Later (post-v1)
- Heterogeneous engine adapters (LM Studio / llama-swap consumption — side-note)
- Third-party exposure mode for non-Ollama engines (the unclaimed niche)
- Cross-user/multi-home federation (J15/telemetry territory)

## Monetization mapping (from the same brainstorm, Gui)
- Free forever: core router, local models, 1:1 routing (acquisition engine)
- Household tier (~$10/mo est.): secure fleet + multi-device routing + scheduler pro
  + dashboard polish (the management layer; never charge for your own hardware's work)
- Enterprise: oracle API, team dashboards, support (J8/J10 tier already spec'd)
- Cloud routing: referral/margin via Compute Fund (the visible meter; OpenRouter's
  $140M ARR proves the meter exists on cloud — ours routes BOTH and keeps local free)

## Market sizing (sanity arithmetic, honest labels)
- Verified: tens of millions of RTX-class GPUs shipped; homelab/self-hosting ~+40% YoY.
- Estimated: ~1M households run a local LLM today (order-of-magnitude, unverified).
- Capture model: 1-3% year one = 10-30k active users; at ~$10/mo household tier =
  $1-3M ARR potential consumer-only; enterprise on top (J8 research: enterprise pays most).
- ALL figures estimated/derived — not a business plan; revisit with the telemetry
  flywheel's opt-in data.

## Why-not-Tailscale (positioning, for support/docs)
Tailscale = network tool ($45.2M ARR, $1.5B valuation — the category is real and paid).
It doesn't know what a model is: no difficulty/cost routing, no bench, no scheduler,
no visible reasoning. Free up to 3 users then paid tiers for household features.
Tierllama rides it off-network; replaces it for the AI-fleet use case on-LAN.
We're not rebuilding the VPN; we're building the car around the wheel.