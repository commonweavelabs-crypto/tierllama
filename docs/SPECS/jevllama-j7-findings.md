# J7 findings - web dashboard with customizable routing

## Architecture decision
FastAPI single process = API + static UI (served at :8848). No Electron, no node
build. Rationale: ships with the backend, zero extra installs, the router process
is the only stateful component (decision log + routing.json both local files).
UI: Pico CSS + vanilla JS in one page - Ollama-style clean/dark/functional.

## Verified (all live)
1. Fleet view: discovered machines + models render (GET /api/fleet -> 200)
2. Decision-tree editor: 8 tiers (4 difficulties x 2 timings), dropdown per tier =
   model + thinking level; PUT /api/config saves routing.json
3. Hot reload: router._tree_lookup() reads routing.json per route call - change is
   effective next message, no restart (verified: HARD/LATER override -> qwen3:8b
   served in 14.06s, status ok)
4. Thinking levels: thinking=max -> think:true (qwen3-class); models that reject
   the flag (glm cloud) get an automatic 400-retry without it (24s, status ok)
5. Savings summary + masked decision log render in browser
6. Fresh clone: dashboard/config/fleet 200 OK; PUT config saved + read back

## Bugs found and fixed during J7
- B1: duplicate `const TIERS` declaration in app.js (UI would not load) - consolidated
- B2: adapters ignored model kwarg (CLOUD_HARD branch forced lane default) - kwarg
  precedence fixed; verified override flows through
- B3: _thinking_body had swapped args (message/model) - every cloud call 400'd;
  caught by e2e test, fixed
- B4: missing `import re` broke _safe_title (S3 regression guard) - restored
- B5: test-harness confusion (HARD classified timing=LATER) - NOT a bug: tree maps
  difficulty+timing correctly; documented because it's the exact mental-model trap

## Boundaries kept
classifier unchanged (qwen3:4b); comfyui-video-ui untouched; changes confined to
tierllama/ + docs/.
