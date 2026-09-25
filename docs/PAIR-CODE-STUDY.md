# PAIR code study — feature extraction (2026-09-25)

_Repo cloned to `~/AppData/Local/hermes/projects/pair-study` (Apache-2.0, NVIDIA
official). This is a READ study: patterns ported to Tierllama's Python/TS stack, no
code imported. Companion to `PAIR-CASE-STUDY.md`. Archive: ig-ddc44crwjl2x._

## Architecture in one paragraph

12 Go binaries under a supervising broker (`nvpair-ui-broker`), talking
newline-delimited JSON-RPC 2.0 over stdio / named pipes. Key workers:
`nvpair-node-scanner` (mDNS discovery, one consolidated `_nvpair-node._tcp` record
per node, hardware + model enrichment), `nvpair-proxy` (one process, one facade per
engine — Ollama-native + OpenAI-compatible endpoints), `nvpair-job-scheduler`
(least-loaded-first ranking), `nvpair-engine-manager` (manifest-driven engine
lifecycle), `nvpair-workload-manager` (cluster-wide job relay). Browser client = the
Electron desktop app; TUI available.

## The 8 patterns worth porting (ranked for Tierllama)

**1. EWMA-smoothed GPU pressure with hysteresis (job-scheduler).** The scheduler's
ranking signal: pending workload + GPU pressure where pressure = EWMA (α=0.35) of
GPU utilization banded 0–3 (0 <40%, 1 40–69%, 2 70–84%, 3 ≥85%), with *asymmetric
downward thresholds* (35/65/80) to prevent rank thrash, stale samples (>10s) →
neutral pressure 1. **Port directly**: this is exactly the health signal our
provider grid's `measured` tier lacks — today we probe cold-load/steady tok/s
occasionally, not continuously. An EWMA GPU-pressure input to our tier choice is
~50 lines and improves local-node selection immediately.

**2. Reservations under one lock (proxy).** Between scheduler snapshots, facades
take short-lived "reservations" for dispatched work, held in-process under one lock,
so concurrent bursts can't double-book an idle-looking node. Reservation is released
when the request ends and MOVES with failover. **Port**: our multi-node dispatch
(T4) needs exactly this — pending-count drift between reconcile ticks is the classic
bug; their answer (reserve at dispatch, release at request end, reservations move
with failover) is the right shape.

**3. Commit-at-first-body-byte + dispatch budget + wall-clock deadline (proxy spec §5).**
Inference requests "commit to a node at the first byte of response body rather than
at its headers," retry under a bounded dispatch budget and deadline. **Port to T4**:
defines when a request is considered "placed" — the correct semantics for streaming
LLM responses and cheap to copy as a rule.

**4. Anti-flap liveness with activity vouching (node-scanner).** A node is evicted
only after ~1 minute absent + ~10 consecutive failed TCP probes; and two signals
VOUCH without probing: a fresh node-info fetch (<10s) and inference response bytes
(<60s) — "the only liveness evidence that gets stronger the busier a node is."
Also: a scan losing ALL known nodes is treated as OUR fault (suppression window) so
one saturated machine can't drop the whole directory. **Port**: brilliant for fleet
discovery (T3) — a busy GPU node starves its own control plane; activity-vouching
keeps it listed while it serves.

**5. Manifest-driven engines (engine-manager).** Adding an engine = a JSON manifest
(detect/install/start/stop/health/actions), not code; `pull_model` streams progress.
**Port idea to our provider grid**: cloud providers today are TOML-configured; a
manifest schema would let users drop in new local engine types (llama.cpp variants,
Kobold, vLLM) without code changes. Low priority but cheap.

**6. One consolidated mDNS record per node (scanner).** All services behind a single
`_nvpair-node._tcp` record with TXT keys; model inventory fetched over HTTP from the
engine-manager (because TXT records are too small). **Port**: when we do discovery,
one-record-per-node + out-of-band enrichment avoids mDNS bloat and the 255-byte
limits. Also adopt their "last-good cache" so a transient fetch miss doesn't blank
a node's card.

**7. CORS pass-through honesty (proxy).** Browser preflight queries all routable
targets with concurrency 8 / 10s deadline; grants only the INTERSECTION of
permissions; a denial is never replaced by a successful OPTIONS; errors carry real
status codes. Also documents the Chromium Local-Network-Access gate for public
origins → loopback. **Port to our webapp if it proxies local inference from a
browser UI** — this exact problem is coming for us in comfyui-video-ui too (document
the Chromium `targetAddressSpace` annotation early).

**8. JSON-RPC-over-stdio supervisor pattern (broker/workers).** Parent supervises
optional workers; a missing binary degrades capability but the broker keeps running;
crashes reported as one notification. Their per-service README discipline (each
spec.md normative, README yields) is also a good docs pattern for our services.

## What they DON'T have (our differentiation, confirmed in code)

- **No cost/price/tier anywhere.** Grep for price/cost/tier across all READMEs: only
  incidental English. PAIR never asks "what is this request worth?" — zero pricing
  policy, zero QUALITY-vs-PRICE intent, no cloud. This is precisely our layer.
- **No measured-per-machine model bench.** Their health signal is GPU utilization
  + pending count. No cold-load/steady tok/s probing, no quality scoring. Our 5-probe
  bench has no PAIR counterpart.
- **No decision transparency for users.** Ranking happens and is pushed; there's no
  visible per-request decision tree like our log. (Their failover emits events, but
  there is no "why this node" surface.)
- **No cloud tier at all.** LAN-only by design.
- **No conversation-level routing** (our Jev-class classifier lane) — it routes
  requests, not decisions.

## Direct lifts (rules/specs to adapt nearly verbatim into our design docs)

- EWMA α=0.35 + asymmetric hysteresis bands + stale-sample neutral default
  (job-scheduler) → into the T4 dispatch design.
- Reservation lifecycle: dispatch → reserve → release-on-end → move-on-failover
  (proxy) → into T4 design.
- Commit-point rule (first body byte) + budget/deadline bounds → into T4 spec.
- Activity-vouching liveness + all-lost-is-our-fault suppression → into T3 spec.
- Manifest-driven engine addition → into our provider-grid config design.

## Not worth taking

- Their mDNS service-key scheme (`ni/ol/lm/er/...`) — fine for Go/mDNS, we'll use
  zeroconf with our own schema.
- Cluster mTLS pin/trust machinery — heavy for a personal fleet; revisit only if we
  ship multi-user fleets (Compute Fund context could need it later; note and move on).
- The Electron desktop app — our dashboard already covers this.

## License compliance note

Apache-2.0 throughout (SPDX headers verified). If we ever copy Go code (we are NOT),
we'd need to preserve notices. Pattern-ports into Python are clean; keep NVIDIA
attribution in PAIR-CASE-STUDY.md (already present).