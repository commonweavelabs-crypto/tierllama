# J11 findings - dashboard v2: tabs, Providers UI, visual polish

## Shipped
1. Tab navigation (Overview/Routing/Providers/Activity) - single served page,
   zero JS routing libs; existing cards reorganized into panes
2. Providers tab: logo cards (inline SVG-style badges, no binary assets),
   enabled toggle, key-status dot (green/amber), key input -> .tierllama_keys.env
   (gitignored); key saved also set os.environ for the live session
3. /api/providers/all (incl. disabled providers + key_ready), /toggle,
   /key endpoints
4. providers.py: _load_keys/save_key/set_enabled; dispatch falls back to the
   keys file when env var absent
5. Dark GitHub-style palette, gradient KPI text, tier-row grid, amber styling
   for max-thinking dropdowns

## Bugs found during J11
- B1: set_enabled() ate the newline before the next [[provider]] header ->
  "expert = "o1"[[provider]]" = invalid TOML -> /api/providers/all 500 on any
  toggled clone. Fixed: preserve trailing newline; verified toggle round-trip.
- B2: webapp.py missing `import os` (providers_all used os.environ) - 500.
  Lesson: py_compile passes but NameErrors only appear at runtime.

## Verified (fresh clone :8862)
dashboard/providers-all/fleet/savings/log all 200; tabs present; providers
exposed as openai(off)/xai(off)/ollama-cloud(on)
