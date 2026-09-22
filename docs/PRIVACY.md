# Privacy (J6/S4)
- `logs/decisions.jsonl` stays LOCAL. It stores the message text + routing decision so
  the router can improve; it never leaves the machine unless the user shares it.
- `tierllama tail` masks messages longer than 256 chars by default.
- Support rule: if you share a decision log, run the mask first or trim to the fields
  you need (role/difficulty/timing/lane/confidence - not the message).
- Nothing in Tierllama phones home. Discovery scans only run when invoked.

## J8 additions: bench + telemetry
- `logs/bench.jsonl` stays LOCAL: per-model speed + capability results on your
  hardware. Used to fill your decision tree. Never sent anywhere by default.
- Optimize flow asks before the first scan: results stay on this machine.
- Shared telemetry is OPT-IN (checkbox at scan, never pre-checked): only model
  name/quant, hardware class, latency + capability scores. NEVER prompts, message
  text, or IPs. Dashboard shows last-shared. One-click revoke.
- Already-sent telemetry is aggregated/compacted and cannot be recalled (stated
  plainly at consent).
