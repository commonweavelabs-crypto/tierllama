# J8 findings - model capability oracle / auto-tune

## Verified (all live on this machine)
1. bench.py: combined sweep per local model - unload -> cold-load timing ->
   EASY/MEDIUM/HARD probes (timed AND graded) -> {max_fit, timing_fit} per model
2. All 7 local models benched incl. ornith-1.5:35b (cold 163.2s, 37.6 tok/s -> LATER)
3. seed.py: capability priors + cheapest-capable recommender (NEED bars per tier,
   cost rank local < cloud-lite < frontier); measured (>=1 record) overrides seed
4. /api/optimize + /api/optimize/status (threaded sweep + progress polling)
5. Consent gate: local-storage consent REQUIRED (refuses without); telemetry
   opt-in recorded separately; PRIVACY.md updated
6. UI: Optimize card with disclaimer ("~40s per model") + progress bar +
   consent checkbox; decision tree moved under Advanced settings (hidden default)
7. E2E: optimize-filled tree -> proxy routed live message to the recommended
   model (EASY -> qwen3:0.6b, 0.11s, status ok)
8. Fresh clone: clone -> probe_model passes (logs mkdir fixed)

## Bugs found during J8
- B1: SEED_CAPACITY typo (SEED_CAPACITY vs SEED_CAPABILITY) - NameError on import
- B2: recommender picked pure-max-capability (all tiers -> frontier cloud);
  redesigned to cheapest-capable per tier (the actual product goal)
- B3: probe grading brittle: 4b writes reasoning first (2500-token budget needed,
  code in thinking field); exec-based grading now extracts from fenced blocks,
  then def-patterns, across content+thinking
- B4: fresh clone crashed on missing logs/ dir - mkdir added
- B5: qwen3:8b palindrome genuinely buggy (case bug) - grading correctly caught it

## Measured matrix (this machine, 9/22)
- qwen3:0.6b: 1.3s cold, 219 tok/s, MEDIUM fit, NOW
- qwen3:4b: 11.4s cold, 192 tok/s, HARD fit, NOW
- qwen3:8b: 22.2s cold, 40 tok/s, EASY fit, LATER (palindrome bug)
- gemma3:12b: 42.5s cold, 57.7 tok/s, MEDIUM, LATER
- ornith-1.5:9b: 35.5s cold, 62.5 tok/s, HARD, LATER
- qwen3-vl:8b: 40.2s cold, 128.9 tok/s, HARD, LATER
- ornith-1.5:35b: 163.2s cold, 37.6 tok/s, HARD, LATER


## J8 REVISION (Gui pushback, 9/22): "these picks are wrong"
Gui correctly flagged: qwen3:0.6b at HARD, ornith-1.5:9b at HARD/LATER, weak EXPERT.

### Root causes (3 stacked flaws)
- F1: HARD probe luckable (single-number check) - 0.6b 'passed' HARD
- F2: n=1 measurement instantly overrode seed consensus (noisy probe > benchmarks)
- F3: recommender ranked pure capability, not cheapest-capable

### Fixes
- HARD probe = multi-step workers/wall problem (can't luck; answer 3.30h)
- Capability = 0.6*seed + 0.4*measured (benchmarks anchor; measurements refine)
- NEED bars raised: EASY 25, MEDIUM 45, HARD 62, EXPERT 82
- Thinking dropdown UX: explicit labels ("Thinking: MAX (deep reasoning, slower)")
  + amber badge for max; wiring verified end-to-end (think:true in dispatch body)

### New tree (verified live)
EASY/NOW qwen3:0.6b | MEDIUM/NOW deepseek-v4-flash | HARD/NOW deepseek-v4-flash max
HARD/LATER qwen3-vl:8b max | LATER locals ornith-1.5:9b | EXPERT glm-5.3-flash max


## Follow-up (Gui, 9/22): box visibility, blend permanence, ornith reasoning
- BOX: discovered + visible in fleet (4 models in dropdowns). NOT benched: it runs
  llama-swap (OpenAI protocol, no cold-load API). By design = async LATER lane
  (queued batches). No Tierllama install needed on the box. Providers-v2 gives it
  proper adapter treatment.
- 60/40 blend: PERMANENT feature. Seed = aggregate of many benchmark runs; a
  machine measurement = 1 sample of noisy reality. As usage accumulates, n rises
  and the measured share grows naturally - improves without changing the rule.
- Ornith LATER verdict was partly a rule bug: my cold<15s test conflated
  first-message cost with conversation speed. keep_alive keeps models warm, so
  the rule is now: tok/s >= 40 earns NOW even with slow warmup. Ornith (55.7
  tok/s) -> MEDIUM/NOW + EASY/NOW local - matches Gui's own description
  ("conversational, knows tools, not for hard"). Box 27B correctly stays LATER
  (33.7 tok/s + 111s cold).
