# Red Hat Guardrail Bench — Full Distillation (2026-10-12)
*Source: extracts/redhat-guardrail-bench.md (primary, verified both tables + appendix prompts) —
for tierllama J27 (per-model prompt profiles) and model-selection defaults. 9 configs, 2 tasks
(prompt-injection, content-safety), class-balanced datasets, NeMo Guardrails harness, latency =
median round-trip. All numbers below are from the paper, not the video.*

## THE CHART (sorted worst→best worst-case accuracy)

```
MODEL                    PARAMS    INFRA          INJECTION        CONTENT-SAFETY
                        (M)       (where it ran)  acc   @med ms    acc   @med ms
─────────────────────────────────────────────────────────────────────────────────────
BART-large-mnli    [2019] 400     M1 CPU          61.5  115        68.7  144
granite-guardian  ─────── 125     M1 CPU           -     -         80.3   33   ◄ safety-only
Nemotron default   ────── 4,000   96GB GPU (US)   69.4  240        84.7  230
Shieldstral        ────── 3,000   96GB GPU (US)   72.0  188        74.8  192
deb inj-v2         ──────   200   M1 CPU          89.0   80  ◄★     -     -
Laya (orig policy) ──────   421   M1 CPU          85.4  119        57.9  118  ◄ injection-only
Nemotron CUSTOM    ────── 4,000   96GB GPU (US)   84.8  240        85.1  242
DiffusionGemma     ────── 2,600   96GB GPU (US)   87.7  562        85.5  499   ◄ slowest
Jev (API)          ────── unknown TypeSafe (US)   86.4  348        86.2  360  ◄ most balanced
Qwen3.6-35B        ────── 35,000  96GB GPU (US)   89.3 ★ 313      85.5  308   ◄ hardest acc
```

## CAPABILITY vs WEIGHT tiers (Gui's chart)

**TIER TANK — lightest to heaviest:**
1. granite-guardian-hap-125m (125M, CPU, 33ms) — safety single-task, lightest
2. deberta-injection-v2 (200M, CPU, 80ms) — injection single-task
3. Laya (421M, CPU, 118ms) — two tasks, one weak
4. BART (400M, CPU) — two tasks, both weak (2019 concept drift)
5. Shieldstral 3B (GPU) — two tasks, both mid
6. DiffusionGemma 2.6B (GPU) — accurate but SLOWEST
7. Nemotron 4B (GPU) — accurate, needs prompt custom work
8. Qwen 35B (GPU cluster) — top accuracy, heavy
9. Jev (unknown, cloud API) — balanced #1 safety, needs US roundtrip

**GENERALIZED RULES (from their data):**
R1. LIGHTWEIGHT RULE: CPU classifiers ~<500M = millisecond class (33-118ms) and can sit
   within 0.3pp of the biggest judge on a well-defined task (DeBERTa).
R2. SCALE RULE on accuracy ceiling: at 35B the ceiling is ~89% injection / ~85.5% safety.
   Nobody broke 90 on either — data quality of the bench, not raw size, sets the wall.
R3. CUSTOM-PROMPT RULE: stock prompts leave 10-15pp on the table for judge models
   (Nemotron default 69→custom 84.8). Prompt work is worth real accuracy points.
R4. TRANSFER-NEGATIVE RULE (the key one): the tuned prompt that gave Laya +17.83pp gave
   Jev -3.67pp. Prompt style is per-model. Never copy prompts between models.
R5. STYLE-MATCH RULE: three prompt archetypes appear:
   - Taxonomy-list style: giant enumerated disallow lists + allow lists (Qwen, Nemotron)
     → works for big judges.
   - Frame-template style: <Instruct>/<Query>/<Document> wrappers (Shieldstral,
     DeBERTa-style) → works for small instructed/embedding models.
   - Per-crime YAML style: independent narrow questions + threshold (Laya) → works for
     decision-models with multiple heads.
R6. DEPLOYMENT RULE: local CPU = 33-240ms; remote = +56ms network floor + cross-country
   RTT. Real deployments budget the network separately from compute latency.
R7. ZERO-SHOT BART RULE: 6-year-old zero-shot = worst on modern tasks (concept drift).
   Zero-shot ≠ zero work; label-stuffing is not prompt engineering.

## GAPS TO TEST OURSELVES (what Red Hat did NOT cover)
G1. OUR MODELS: qwen3:4b/8b, gemma3, ornith etc. never tested — need our own local
   bench to fill. (Their Qwen = Qwen3.6-35B on GPUs, ours = 4B/8B quantized on 16GB.)
G2. OUR TASK: no decision-lane classification (routing decision, when-to-ask, budget
   estimates) was tested — only safety moderation. Transfer of R1-R7 to OUR tasks
   UNVERIFIED. Plan: small golden set per new lane task, then profiles.
G3. PROMPT PROFILES FOR OUR STACK: build prompt_profiles.json + per-swap rebench hook
   (J27 plan). Seed from R5 archetypes mapped to our model families:
   - gemma3 family → per-crime YAML (Laya-style, Gemma backbone!)
   - qwen3 local family → taxonomy-list (Qwen family)
   - classifier heads (qwen3:4b JSON) → frame-template (DeBERTa-style)
G4. LATENCY ON OUR HARDWARE: their CPU numbers = M1; our box differs. 5070 Ti GPU
   lanes + local CPU lanes both need our own ms tables.
G5. THRESHOLD TUNING: Laya used noul > 0.5 default; Red Hat did not tune per-class
   thresholds — that optimization is open (can lift accuracy further without prompts).
