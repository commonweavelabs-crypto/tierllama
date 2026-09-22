"""Seed table (J8): cold-start recommendations from public benchmarks + common-sense
priors. Measured bench data OVERWRITES seed entries per (model, machine).
Cloud models: default-NOW (expert-run hardware - ping only, no speed probes)."""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Ordinal capability prior per family/size (higher = more capable), from public
# benchmark consensus - NOT vendor claims. Updated via seed-refresh (URL) later.
SEED_CAPABILITY = [
    {"pattern": "kimi-k3", "score": 95, "note": "frontier-class"},
    {"pattern": "glm-5.3", "score": 88, "note": "frontier-lite"},
    {"pattern": "minimax-m2.7", "score": 86, "note": "agentic"},
    {"pattern": "deepseek-v4", "score": 80, "note": "strong general"},
    {"pattern": "qwen38-27b", "score": 74, "note": "capable local, slow"},
    {"pattern": "qwen3-vl", "score": 65, "note": "vision-capable"},
    {"pattern": "qwen3:8b", "score": 60, "note": "general local"},
    {"pattern": "gemma3", "score": 55, "note": "small local"},
    {"pattern": "devstral", "score": 58, "note": "code-focused"},
    {"pattern": "qwen2.5-coder", "score": 57, "note": "code-focused"},
    {"pattern": "ornith-1.5:35b", "score": 45, "note": "custom, moderate"},
    {"pattern": "ornith-1.5:9b", "score": 35, "note": "fast but limited"},
    {"pattern": "llama3.2", "score": 30, "note": "legacy small"},
    {"pattern": "qwen3:4b", "score": 40, "note": "tiny local"},
    {"pattern": "qwen3:0.6b", "score": 20, "note": "tiny local"},
    {"pattern": "k2-", "score": 40, "note": "box small"},
]

CLOUD_MARKERS = (":cloud",)

def seed_score(model):
    for e in SEED_CAPABILITY:
        if e["pattern"] in model:
            return e["score"]
    return 50

def is_cloud(model):
    return any(m in model for m in CLOUD_MARKERS)

def recommend(models, bench_results=None):
    """Recommendation matrix: for each tier (difficulty/timing) pick best model.
    measured (>=1 bench record) overrides seed; seed fills gaps."""
    bench = {b["model"]: b for b in (bench_results or []) if "error" not in b}
    cloud = [m for m in models if is_cloud(m)]
    local = [m for m in models if not is_cloud(m)]
    def capability(m):
        if m in bench and bench[m].get("max_fit"):
            return {"EASY": 20, "MEDIUM": 50, "HARD": 80, "UNRELIABLE": 5}.get(bench[m]["max_fit"], 50)
        return seed_score(m)
    matrix = {}
    NEED = {"EASY": 20, "MEDIUM": 50, "HARD": 80, "EXPERT": 85}
    COST = {"local": 0, "cloud_lite": 1, "cloud_frontier": 2}
    def cost_rank(m):
        if is_cloud(m):
            return COST["cloud_frontier"] if seed_score(m) >= 85 else COST["cloud_lite"]
        return COST["local"]
    for diff in ["EASY", "MEDIUM", "HARD", "EXPERT"]:
        for timing in ["NOW", "LATER"]:
            key = f"{diff}/{timing}"
            if timing == "NOW":
                pool = cloud + [m for m in local if bench.get(m, {}).get("timing_fit") == "NOW"]
                if not pool:
                    pool = local or cloud
            else:
                pool = local + cloud
            # cheapest-capable: keep models that MEET the tier's capability bar, pick cheapest
            capable = [m for m in pool if capability(m) >= NEED[diff]]
            if not capable:
                capable = sorted(pool, key=capability, reverse=True)[:1]
            pick = sorted(capable, key=cost_rank)[0]
            src = "measured" if pick in bench and bench[pick].get("max_fit") else "seed"
            matrix[key] = {"provider": "auto", "model": pick,
                           "thinking": "max" if diff in ("HARD", "EXPERT") else "normal",
                           "source": src}
    return matrix
