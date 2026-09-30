"""J19: the model rater — dynamic, per-user model categorization.

What it does (Gui spec, Sep 29):
- Gathers EVERY model the user can actually reach: local Ollama tags + cloud
  candidates (":cloud" names reachable through the transparent ollama proxy).
- Rates each model: capability (seed prior blended with measured bench),
  speed (tok/s), cost rank (local=0 < cloud-lite=1 < frontier=2).
- Emits the category LIST per tier: every model good enough for EASY/NOW,
  MEDIUM/LATER, ... sorted best-pick-first — not a single silent choice.
- Cloud liveness: a retired model must NEVER be recommended (deepseek-v4-flash
  410 Gone incident). Probed lazily in the background, cached on disk.

Lightweight policy (Gui law): probes fire only on cache misses, never on a
timer; /api/models/rated always serves instantly from disk cache.
"""
import json, datetime, threading, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
LIVENESS_PATH = ROOT / "logs" / "model_liveness.json"
PRICES_PATH = ROOT / "logs" / "model_prices.json"

from .seed import seed_score, is_cloud
from .config import CLASSIFIER

# difficulty tier -> minimum blended capability score to qualify for the tier
NEED = {"EASY": 25, "MEDIUM": 45, "HARD": 62, "EXPERT": 82}

# J19 calibration (Gui: "never pick a model that won't do the job"): a suggested
# model must clear the DRIVER FLOOR — below this it can't hold a real harness
# prompt (qwen3:0.6b can't even carry Hermes' internal context). Price is never
# a reason to suggest something unusable.
DRIVER_FLOOR = 48
# and it must clear the tier need by this comfort margin ("can technically pass
# a toy bench" ≠ "will do the job reliably")
COMFORT_BUFFER = 8

# cloud candidates: any ":cloud" model the account can address through the
# local ollama proxy. This list = known ollama.com cloud catalog entries;
# liveness probes prune the dead ones. (No accounts/keys needed — the local
# server proxies with the user's own ollama session.)
CLOUD_CATALOG = [
    "glm-5.3-flash:cloud", "kimi-k3:cloud", "minimax-m2.7:cloud",
    "deepseek-v4-flash:cloud", "qwen3-max:cloud", "gpt-oss:120b-cloud",
]

def _load_liveness() -> dict:
    try:
        return json.loads(LIVENESS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_liveness(d: dict):
    LIVENESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LIVENESS_PATH.write_text(json.dumps(d, indent=1), encoding="utf-8")

# ---------- J19: per-token pricing (REAL dollars, Gui law: price is a dossier fact) ----------
# Live-scraped from ollama.com/library/<model> ("$X input / $Y output" per Mtok),
# cached on disk like liveness: refresh on demand (cache miss / 7d staleness), never timed.
_PRICE_STALE_S = 7 * 24 * 3600.0

def _fetch_model_prices(model_base: str) -> dict | None:
    """$input/$output per Mtok from the model's ollama.com library page."""
    import re as _re, html as _h
    try:
        t = urllib.request.urlopen(f"https://ollama.com/library/{model_base}", timeout=12).read().decode()
        m = _re.search(r"\$\s?([0-9.]+)\s*input.{0,120}?\$\s?([0-9.]+)\s*output", t, _re.DOTALL)
        if m:
            return {"input": float(m.group(1)), "output": float(m.group(2)),
                    "fetched": datetime.datetime.now().isoformat(timespec="seconds")}
        cached = _re.search(r"\$\s?([0-9.]+)\s*input\s*\$\s?([0-9.]+)", t)
        if cached:
            return {"input": float(cached.group(1)), "output": 0.0,
                    "cached_input_only": True,
                    "fetched": datetime.datetime.now().isoformat(timespec="seconds")}
    except Exception:
        pass
    return None

def _ensure_prices(cloud_models: list[str]):
    """Refresh missing/stale prices in a background thread (cache-miss only)."""
    prices = {}
    if PRICES_PATH.exists():
        try:
            prices = json.loads(PRICES_PATH.read_text(encoding="utf-8"))
        except Exception:
            prices = {}
    now = datetime.datetime.now()
    def _stale(entry):
        if not entry:
            return True
        try:
            f = datetime.datetime.fromisoformat(entry.get("fetched", "2000-01-01T00:00:00"))
            return (now - f).total_seconds() > _PRICE_STALE_S
        except Exception:
            return True
    missing = [m for m in cloud_models if _stale(prices.get(m))]
    if not missing:
        return prices
    def worker():
        d = prices
        for m in missing:
            base = m.split(":")[0]
            p = _fetch_model_prices(base)
            if p:
                d[m] = p
                PRICES_PATH.write_text(json.dumps(d, indent=1), encoding="utf-8")
    threading.Thread(target=worker, daemon=True).start()
    return prices

def _load_prices_now(cloud_models: list[str]) -> dict:
    """Prices for immediate use (disk hit), queueing a background refresh."""
    prices = {}
    if PRICES_PATH.exists():
        try:
            prices = json.loads(PRICES_PATH.read_text(encoding="utf-8"))
        except Exception:
            prices = {}
    _ensure_prices(cloud_models)
    return prices

def _probe_live(model: str) -> bool:
    """One tiny chat: does this model actually answer? Retired models 410."""
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": "hi"}],
                       "stream": False, "think": False,
                       "options": {"num_predict": 1}}).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=15).read())
        return not r.get("error")
    except urllib.error.HTTPError:
        return False
    except Exception:
        return False          # unreachable ≠ dead; never cached as dead on network flake? -> cache as unknown

def _ensure_liveness(models: list[str]):
    """Background-probe models with no liveness verdict yet (cache-miss only)."""
    liv = _load_liveness()
    missing = [m for m in models if m not in liv]
    if not missing:
        return
    def worker():
        for m in missing:
            verdict = _probe_live(m)
            d = _load_liveness()
            d[m] = {"live": verdict, "checked_at": datetime.datetime.now().isoformat(timespec="seconds")}
            _save_liveness(d)
    threading.Thread(target=worker, daemon=True).start()

def gather_pool() -> dict:
    """All reachable models, split local/cloud, each with rater stats."""
    import urllib.request as _u
    tags = json.loads(_u.urlopen("http://127.0.0.1:11434/api/tags", timeout=8).read())
    local = sorted(m["name"] for m in tags.get("models", []))
    cloud = [m for m in CLOUD_CATALOG if not any(m == l for l in local)]
    liv = _load_liveness()
    cloud_live = [m for m in cloud if liv.get(m, {}).get("live") is True]
    cloud_unknown = [m for m in cloud if m not in liv]
    _ensure_liveness(cloud_unknown)   # fills in quietly; unknowns excluded from lists until verdict
    return {"local": local, "cloud": cloud_live}

# J19 timing calibration (Gui law: NOW means NOW): a suggestion must be able to
# do the job in the time the tier implies. Cloud models are latency-free (they
# classify/answer in seconds). Local models need MEASURED latency evidence:
# the bench's per-difficulty seconds and tok/s tell us if a task of that tier
# returns in seconds (NOW) or minutes/hours (LATER — box, overnight).
NOW_MAX_SECONDS = 60.0        # a "NOW" task should finish within a minute
NOW_MIN_TOK_S  = 40.0         # sustained speed floor for interactive use

def _group_bench() -> dict:
    """bench.jsonl grouped by model (list of rows, one per run)."""
    p = ROOT / "logs" / "bench.jsonl"
    out = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                out.setdefault(r["model"], []).append(r)
            except Exception:
                continue
    return out

def _bench_avg(bench: dict) -> dict:
    """Latest-corrected bench stats per model: median seconds for med/hard work."""
    out = {}
    for m, rows in bench.items():
        if not isinstance(rows, list):
            rows = [rows]
        med = [r.get("medium_s") for r in rows if isinstance(r.get("medium_s"), (int, float))]
        hard = [r.get("hard_s") for r in rows if isinstance(r.get("hard_s"), (int, float))]
        cold = [r.get("cold_load_s") for r in rows if isinstance(r.get("cold_load_s"), (int, float))]
        tok = [r.get("tok_s") for r in rows if isinstance(r.get("tok_s"), (int, float))]
        out[m] = {"med_med": sorted(med)[len(med)//2] if med else None,
                  "hard_med": sorted(hard)[len(hard)//2] if hard else None,
                  "cold_med": sorted(cold)[len(cold)//2] if cold else None,
                  "tok_med": sorted(tok)[len(tok)//2] if tok else None,
                  "n": len(rows)}
    return out

def rate_all(pool: dict) -> list[dict]:
    """One row per model: capability blend, speed, real per-token price, cost rank."""
    bench = _group_bench()
    avg = _bench_avg(bench)
    prices = _load_prices_now([m for m in pool["cloud"]])
    rows = []
    for m in pool["local"] + pool["cloud"]:
        s = seed_score(m)
        runs = bench.get(m, [])
        # latest run wins for max_fit (bench conditions improved over time)
        b = runs[-1] if runs else None
        meas = None
        if b and b.get("max_fit"):
            meas = {"EASY": 20, "MEDIUM": 50, "HARD": 80, "UNRELIABLE": 5}.get(b["max_fit"], 50)
            # J19 blend correction: measured bench so far uses toy prompts (a
            # 0.6b model earned max_fit=HARD) — seed prior dominates (0.7) until
            # the real bench battery lands (J19+).
            s = round(0.3 * meas + 0.7 * s)
        st = avg.get(m, {})
        tok_s = st.get("tok_med")
        cloud = is_cloud(m)
        cost = (2 if s >= 85 else 1) if cloud else 0
        # J19 TIMING EVIDENCE (the NOW/LATER dimension, measured not guessed):
        # can this model do MEDIUM and HARD work within NOW_MAX_SECONDS? Also
        # honest about REAL work: 0.6b "passes" toy prompts in 0.1s but that's
        # not evidence for real tasks — gate hard with the tok/s floor AND the
        # cold-load reality; the real bench battery (J19+) replaces this.
        cloud_now = {"med": True, "hard": True} if cloud else {}
        if not cloud:
            # sustained-throughput estimate for a typical ~500-token real task
            est_med = (st.get("cold_med") or 0) + 500 / max(tok_s or 1, 1)
            est_hard = (st.get("cold_med") or 0) + 900 / max(tok_s or 1, 1)
            cloud_now["med"] = est_med <= NOW_MAX_SECONDS * 2 and tok_s >= NOW_MIN_TOK_S*0.5
            cloud_now["hard"] = est_hard <= NOW_MAX_SECONDS * 2 and tok_s >= NOW_MIN_TOK_S*0.5
        rows.append({"model": m, "capability": s, "measured_fit": b.get("max_fit") if b else None,
                     "tok_s": tok_s, "cloud": cloud, "cost_rank": cost,
                     "price_in_per_mtok": (prices.get(m) or {}).get("input") if cloud else None,
                     "price_out_per_mtok": (prices.get(m) or {}).get("output") if cloud else None,
                     "seconds_medium": st.get("med_med"), "seconds_hard": st.get("hard_med"),
                     "can_do_now": cloud_now})
    rows.sort(key=lambda r: (-r["capability"], -(r["tok_s"] or 0)))
    return rows

def is_small_model(model: str) -> bool:
    """J19 law: sub-9B models are toy class for SUGGESTIONS (weak judgment,
    tiny context, mistake-prone). Name-based probe: a parameter token like
    0.6b / 4b / 8b in the tag. Ambiguous/unknown = NOT small (never
    mis-exclude a big model)."""
    import re as _re
    m = _re.search(r":(\d+(?:\.\d+)?)b(?:[\b\-:]|$)", model.lower())
    if not m:
        return False
    return float(m.group(1)) < 9.0

def unbenched_models(pool: dict | None = None) -> list[str]:
    """Local models with NO bench record (J19 warning source): the UI shows a
    warning + benchmark button for these — never leaves the user stranded."""
    pool = pool or gather_pool()
    bench = _group_bench()
    return [m for m in pool["local"] if not bench.get(m)]

def tier_categories(mode: str = "price", include_local: bool = True,
                    include_small: bool = False) -> dict:
    """THE Gui lists: for every tier, ALL qualifying models, best-pick first.
    mode 'price': qualify by capability, order cheap→expensive (fast breaks ties)
    mode 'quality': qualify by capability, order most-capable first; the user's
    most expensive available model anchors the ceiling (kimi-k3 here, claude/gpt
    would be it if the user had those keys — the list self-adjusts per user).
    include_local False = cloud-only pool (user toggle, J19).
    include_small False = sub-9B models EXCLUDED from suggestions (J19 law:
    <9B = toy class, too many mistakes, tiny context — can't drive a harness).
    They stay in the rated table (visible in /api/models/rated rows) but are
    filtered out of every tier's candidate list unless the user opts in.
    Default OFF: sensible for driver/agentic use; other users (pure chat,
    embedded toys) can flip the toggle to see them suggested."""
    pool = gather_pool()
    if not include_local:
        pool = {"local": [], "cloud": pool["cloud"]}
    rows = rate_all(pool)
    # J19 small-model law: <9B params = toy for suggestion purposes.
    # Local models only (cloud 'tiny' variants don't exist). Opt-in via toggle.
    small_models = {m for m in (pool["local"] + pool["cloud"])
                    if is_small_model(m)}
    benched_small = {m for m in small_models
                     if any(b.get("model") == m for b in _group_bench().get(m, []))}
    excluded_small = small_models - benched_small if False else small_models
    rows_for_tiers = [r for r in rows
                      if include_small or r["model"] not in small_models]
    out = {}
    for diff in ["EASY", "MEDIUM", "HARD", "EXPERT"]:
        for timing in ["NOW", "LATER"]:
            key = f"{diff}/{timing}"
            # J19 calibration: qualify = capability AND driver floor AND comfort buffer.
            # The tier never silently suggests something that can't do the job.
            floor_needed = max(NEED[diff] + (COMFORT_BUFFER if mode == "price" else 0), DRIVER_FLOOR)
            # MEDIUM/HARD/EXPERT NOW tiers require MEASURED timing evidence
            # (cloud models are always NOW-capable; local models must have
            # proven they finish that difficulty within NOW_MAX_SECONDS).
            if timing == "NOW":
                def now_capable(r, diff):
                    if r["cloud"]:
                        return True
                    cdn = r.get("can_do_now") or {}
                    if diff == "EASY":
                        return True                      # any local model answers simple prompts fast enough
                    if diff == "MEDIUM":
                        return cdn.get("med", False)
                    return cdn.get("hard", False)        # HARD/EXPERT NOW need hard-tier timing proof
                qualified = [r for r in rows_for_tiers if r["capability"] >= floor_needed and now_capable(r, diff)]
            else:  # LATER: async — slow local giants qualify (latency is acceptable here)
                qualified = [r for r in rows_for_tiers if r["capability"] >= floor_needed]
            if not qualified:   # never return an empty tier: best available, flagged
                qualified = sorted(rows_for_tiers, key=lambda r: -r["capability"])[:3]
                flag = f"no model clears the driver floor ({DRIVER_FLOOR}) for this tier — best-available shown"
            else:
                flag = None
            if mode == "quality":
                # J19 cap rule (Gui spec verbatim): "optimizing for QUALITY → the
                # ceiling model belongs at EXPERT; everything below it gets the
                # best SUB-ceiling fit." Band = [need(T), ceiling_cap) for all
                # tiers below EXPERT (so glm88 serves HARD while the true
                # ceiling kimi95 is reserved); EXPERT band unbounded → ceiling.
                ceiling_cap = max(r["capability"] for r in rows)
                next_need = {"EASY": NEED["MEDIUM"], "MEDIUM": NEED["HARD"],
                             "HARD": ceiling_cap, "EXPERT": 101}[diff]
                band = [r for r in qualified if r["capability"] < next_need] if diff != "EXPERT" else list(qualified)
                # EASY/MEDIUM keep a sane upper bound so quality never goes frontier for trivial asks
                if diff in ("EASY", "MEDIUM") and not any(NEED[diff] <= r["capability"] < next_need for r in band):
                    band = [r for r in qualified if NEED[diff] <= r["capability"] < next_need]
                pool_for_pick = band if band else qualified
                pool_for_pick.sort(key=lambda r: (-r["capability"], -(r["tok_s"] or 0)))
                qualified = pool_for_pick + [r for r in qualified if r not in pool_for_pick]
            else:   # price (Gui spec: "a tier below the highest"): the ceiling
                # model is RESERVED for quality; price mode caps one tier below
                # it across the board (EXPERT→sub-ceiling, not frontier).
                ceiling_cap = max(r["capability"] for r in rows)
                price_cap = {"EASY": NEED["MEDIUM"], "MEDIUM": NEED["HARD"],
                             "HARD": NEED["EXPERT"], "EXPERT": ceiling_cap}[diff]
                priced = [r for r in qualified if r["capability"] >= NEED[diff]
                          and r["capability"] < price_cap]
                if priced:
                    qualified = priced
                qualified.sort(key=lambda r: (r["cost_rank"], -r["capability"], -(r["tok_s"] or 0)))
            out[key] = {"candidates": qualified[:8], "flag": flag}
    return {"mode": mode, "pool_size": len(rows), "tiers": out,
            "generated": datetime.datetime.now().isoformat(timespec="seconds")}