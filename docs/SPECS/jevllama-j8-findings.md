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
