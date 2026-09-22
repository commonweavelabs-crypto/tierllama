# Privacy (J6/S4)
- `logs/decisions.jsonl` stays LOCAL. It stores the message text + routing decision so
  the router can improve; it never leaves the machine unless the user shares it.
- `tierllama tail` masks messages longer than 256 chars by default.
- Support rule: if you share a decision log, run the mask first or trim to the fields
  you need (role/difficulty/timing/lane/confidence - not the message).
- Nothing in Tierllama phones home. Discovery scans only run when invoked.
