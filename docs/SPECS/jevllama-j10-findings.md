# J10 findings - providers v2 + seed-refresh pipeline

## Verified (live)
1. providers.py + providers.toml: OpenAI-compatible TOML descriptors, keys in
   env (api_key_env), /api/providers endpoint (4 models, ollama-cloud enabled;
   openai/xai disabled-by-default pending keys)
2. dispatch_provider(): any provider + cost logging to logs/costs.jsonl
3. seed_refresh.py: check_and_stage (sha256 verify vs manifest, version compare),
   preview_diff (user_edited tiers skipped), apply_staged (backup + apply),
   rollback (verified: apply#2 -> rolled_back=True)
4. /api/seed/{check,preview,apply,rollback} + /api/providers endpoints
5. UI: Re-scan models button (check -> preview diff -> confirm -> apply ->
   rollback available); user_edited tracking in routing.json ({tiers,_user_edited})
6. Fresh clone: dashboard/providers/seed-check/fleet all 200

## Bugs found during J10
- B1: TOML table-header rule - cost keys after [provider.models] became part of
  it (0.15 appeared as a "model"). Costs moved above the table header.
- B2: _load_tree helper spliced INSIDE proxy.chat() (replace mid-function) -
  proxy returned null; surgically repaired, compiles + serves
- B3: seed URL used main; repo default branch is master - 404 on check
- B4: preview diff read routing.json root instead of nested tiers (from=null)

## Open-core mapping
- Free: static signed seed refresh + own providers via TOML
- Opt-in: community-refined seeds (same channel, phase-2 telemetry)
- Enterprise: live oracle API (not built - future tier)
