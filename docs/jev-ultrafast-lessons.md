# Borrowable patterns from browser-use/jev-ultrafast (entry 272)

**Why it matters:** a real product (17.7K★ in a week) built on EXACTLY our mechanism —
TypeSafe Jev making typed decisions over an indexed option table, one round trip.
Our router = the same architecture with roles/difficulty/timing instead of CLICK/TYPE.
This is third-party validation, and it shipped 2026-09-16.

## Pattern 1 — Speculative target fan-out (adopt in J2/J4)
Their trick: ONE network round trip returns (operation, target) because only targets
compatible with the chosen operation are offered. Our analog: when difficulty=EASY is
likely (short/simple message), only LOCAL-lane fields need full scoring — and HARD
messages can downweight NOW-timing. Concretely: offer timing_conf only when the
difficulty head is uncertain. Potential saving: fewer output tokens per decision.
Status: design note now; measure after J4 lands (don't re-plumb mid-milestone).

## Pattern 2 — Narrow blast radius (already ours, now validated at scale)
Jev Ultrafast: model output NEVER becomes selectors/coordinates/shell/JS; targets
resolve from observed DOM nodes only. Tierllama equivalent: classifier picks from a
FIXED enum; dispatch adapters validate inputs; lane adapters never pass model text into
commands. We built this instinctively in J1-J3; entry 272 proves it works at product
scale. Keep it as a hard rule in the enterprise tier.

## Pattern 3 — Structured state > vision/screenshots (cost symmetry)
They dropped screenshots entirely: Jev consumes the indexed table. Our analog is
already in spec (hooks inject ~200 tokens of hardware state). Reinforces: cheap
structured signals beat expensive generative ones — same lesson as BM25 entry 255.

## Pattern 4 — Radical honesty in perf docs (product trust)
Their perf doc volunteers scope exclusions AND "three pairs too few for a strong
statistical claim (p=0.25)". Adopt for our docs: every measured claim carries (n,
scope, exclusions). We already do this in bench docs — keep it contractual.

## What we do NOT copy
- Paid TypeSafe dependency: our wedge is key-free local+Ollama-cloud routing
  (measured 0.03s/0.8s). TypeSafe integration stays an enterprise-tier OPTION,
  never a requirement — Gui's lock, and this repo proves the "TypeSafe key required"
  onboarding cost is real friction for users.
- Browser automation as a lane: out of Tierllama scope (Jev-classifier ≠ agent).

## Naming signal
Repo uses "jev-" prefix openly; ecosystem convention supports our "powered by Jev"
repo subtitle (Gui's call, 2026-09-22). Tierllama stays the product name.
