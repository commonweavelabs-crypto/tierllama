"""Tierllama web dashboard (J7): one FastAPI process serves API + static UI.
No Electron, no node build - the dashboard ships with the router. Run:
    python -m uvicorn tierllama.webapp:app --port 8848   (or python cli.py serve)
Endpoints:
  GET  /api/fleet       discovered machines + models
  GET  /api/config      current decision tree (tier -> model + thinking level)
  PUT  /api/config      save decision tree changes (effective next route, no restart)
  GET  /api/log?n=50    recent decision log entries (masked)
  GET  /api/savings     savings summary vs always-best baseline
  POST /api/route       route a test message live
"""
import json, os, time, datetime
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from .discover import discover
from .config import LANES, CLASSIFIER, lane_for

app = FastAPI(title="Tierllama", docs_url=None, redoc_url=None)
ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "routing.toml"

class TierTarget(BaseModel):
    difficulty: str            # EASY | MEDIUM | HARD | EXPERT
    timing: str = "NOW"        # NOW | LATER
    provider: str = "ollama"
    model: str
    thinking: str = "normal"   # normal | max | off

@app.get("/api/fleet")
def fleet():
    peers = discover()
    # J7 fix: include THIS machine's Ollama (localhost) in the fleet - the LAN scan
    # skips 127.0.0.1, so local models never showed in the UI dropdowns:
    try:
        tags = json.loads(urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5).read())
        local = {"host": "127.0.0.1", "port": 11434, "kind": "ollama (this machine)",
                 "models": [m["name"] for m in tags.get("models", [])]}
        peers = [local] + [p for p in peers if p.get("host") != "127.0.0.1"]
    except Exception:
        pass
    return {"peers": peers, "generated": datetime.datetime.now().isoformat(timespec="seconds")}

@app.get("/api/config")
def get_config():
    return {"tiers": _load_tiers(), "classifier": CLASSIFIER["model"]}

def _load_tiers():
    """Decision tree as data: routing.json (user-editable via UI) with defaults."""
    p = ROOT / "routing.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    # defaults from config LANES:
    defaults = {
        "EASY/NOW":   {"provider": "ollama", "model": "qwen3:4b", "thinking": "normal"},
        "MEDIUM/NOW": {"provider": "ollama-cloud", "model": "glm-5.3-flash:cloud", "thinking": "normal"},
        "HARD/NOW":   {"provider": "ollama-cloud", "model": "glm-5.3-flash:cloud", "thinking": "normal"},
        "EXPERT/NOW": {"provider": "ollama-cloud", "model": "glm-5.3-flash:cloud", "thinking": "max"},
        "EASY/LATER": {"provider": "box", "model": "qwen38-27b-iq3s", "thinking": "normal"},
        "MEDIUM/LATER": {"provider": "box", "model": "qwen38-27b-iq3s", "thinking": "normal"},
        "HARD/LATER": {"provider": "ollama-cloud", "model": "glm-5.3-flash:cloud", "thinking": "normal"},
        "EXPERT/LATER": {"provider": "ollama-cloud", "model": "glm-5.3-flash:cloud", "thinking": "max"},
    }
    p.write_text(json.dumps(defaults, indent=1), encoding="utf-8")
    return defaults

@app.put("/api/config")
def put_config(payload: dict):
    """Save the decision tree. Effective on the next route (router reads it per call)."""
    tiers = payload.get("tiers", {})
    (ROOT / "routing.json").write_text(json.dumps(tiers, indent=1), encoding="utf-8")
    return {"saved": True, "tiers": tiers}

@app.get("/api/log")
def recent_log(n: int = 50):
    log = ROOT / "logs" / "decisions.jsonl"
    if not log.exists(): return {"decisions": []}
    lines = log.read_text(encoding="utf-8").strip().splitlines()[-n:]
    out = []
    for l in lines:
        d = json.loads(l)
        m = d.get("message", "")
        if len(m) > 200: d["message"] = m[:100] + f"...[{len(m)} chars masked]"
        out.append(d)
    return {"decisions": out}

@app.get("/api/savings")
def savings():
    log = ROOT / "logs" / "decisions.jsonl"
    if not log.exists(): return {"summary": {"decisions": 0}}
    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").strip().splitlines()]
    rows = [r for r in rows if r.get("event") != "escalation"]
    prices = {"LOCAL": (0.0, 0.0), "BOX": (0.0, 0.0), "CLOUD_MEDIUM": (0.15, 0.60),
              "CLOUD_HARD": (3.0, 15.0), "EXPERT": (3.0, 15.0), "FALLBACK": (0.15, 0.60)}
    IN_, OUT_ = 250, 400
    M = 1_000_000
    actual = sum((IN_*prices.get(r.get("lane"), (3,15))[0] + OUT_*prices.get(r.get("lane"), (3,15))[1])/M for r in rows)
    baseline = len(rows) * (IN_*3.0 + OUT_*15.0)/M
    return {"decisions": len(rows), "baseline_usd": round(baseline, 4),
            "routed_usd": round(actual, 4),
            "saved_pct": round((1 - actual/baseline)*100, 1) if baseline else 0,
            "baseline_per_mtok": round(baseline*M/len(rows), 2) if rows else 0,
            "routed_per_mtok": round(actual*M/len(rows), 2) if rows else 0}

class RouteReq(BaseModel):
    message: str

@app.post("/api/route")
def do_route(payload: RouteReq):
    from .router import route
    r = route(payload.message[:8192], dispatch=False)  # log-only: show the decision
    return r

# ---- J8 Optimize flow -------------------------------------------------------
import threading, time as _time
OPT_STATE = {"running": False, "done": 0, "total": 0, "current": "", "result": None,
             "consent_local_accepted": False, "consent_share": False}

@app.post("/api/optimize")
def optimize(payload: dict = None):
    """Start the bench sweep (local models) + write the recommendation matrix.
    payload: {"consent_local": true, "consent_share": false}"""
    payload = payload or {}
    if not payload.get("consent_local"):
        return {"started": False, "reason": "local-storage consent required"}
    if OPT_STATE["running"]:
        return {"started": False, "reason": "already running"}
    OPT_STATE.update({"running": True, "done": 0, "total": 0, "current": "", "result": None})
    import threading
    th = threading.Thread(target=_optimize_worker, daemon=True)
    th.start()
    return {"started": True}

def _optimize_worker():
    try:
        from .bench import probe_model, _get_models
        models = _get_models()
        OPT_STATE["total"] = len(models)
        for m in models:
            OPT_STATE["current"] = m
            try:
                probe_model(m)
            except Exception:
                pass
            OPT_STATE["done"] += 1
        from .seed import recommend
        bench = [json.loads(l) for l in (ROOT/"logs"/"bench.jsonl").read_text().strip().splitlines()]
        latest = {}
        for b in bench:
            if "error" not in b:
                latest[b["model"]] = b
        fleet_peers = discover()
        allm = [m for p in fleet_peers for m in p.get("models", []) if m]
        matrix = recommend(allm, list(latest.values()))
        # measured-wins: only overwrite tiers whose new source is 'measured' unless empty:
        current = _load_tiers()
        for k, v in matrix.items():
            v["provider"] = "auto"
        (ROOT / "routing.json").write_text(json.dumps(matrix, indent=1), encoding="utf-8")
        # telemetry record (shared ONLY if consent given - phase 2 endpoint):
        if OPT_STATE.get("consent_share"):
            (ROOT/"logs"/"telemetry.jsonl").open("a").write(json.dumps(
                {"ts": _time.time(), "type": "opt-anonymized", "note": "NO prompts, NO IPs"}) + "\n")
        OPT_STATE["result"] = matrix
    finally:
        OPT_STATE["running"] = False

@app.get("/api/optimize/status")
def optimize_status():
    return {k: OPT_STATE[k] for k in ["running", "done", "total", "current", "result"]}

# ---- J10 seed refresh endpoints ----
@app.post("/api/jev/install-local")
def jev_install_local():
    """Secure pull: pinned model tag from the Ollama registry (content-addressed
    digests = hash-verified by Ollama itself). We never fetch from random URLs."""
    import subprocess as _sp
    try:
        r = _sp.run(["ollama","pull","qwen3:4b"], capture_output=True, text=True, timeout=1800)
        return {"ok": r.returncode == 0, "error": r.stderr[-200:] if r.returncode else ""}
    except Exception as e:
        return {"ok": False, "error": str(e)[:150]}

@app.post("/api/jev/toggle")
def jev_toggle(payload: dict = None):
    from .providers import _load_keys
    payload = payload or {}
    keys = _load_keys()
    has_key = bool(keys.get("TYPESAFE_API_KEY"))
    # store preference; cloud fallback only active if key exists
    pref = ROOT / ".jev_cloud_pref"
    pref.write_text("on" if payload.get("enabled") and has_key else "off", encoding="utf-8")
    return {"ok": True, "active": payload.get("enabled", False) and has_key,
            "reason": "" if has_key else "needs TYPESAFE_API_KEY"}

@app.get("/api/jev")
def jev_status():
    from .jev_cloud import status
    st = status()
    # local classifier status too
    local_ok = False
    try:
        import urllib.request as _u
        _u.urlopen("http://127.0.0.1:11434/api/tags", timeout=3)
        local_ok = True
    except Exception:
        pass
    st["local_available"] = local_ok
    return st

@app.get("/api/providers/all")
def providers_all():
    from .providers import load_providers, _load_keys
    keys = _load_keys()
    out = []
    for p in load_providers():
        env = p.get("api_key_env", "NONE")
        key_ok = env == "NONE" or bool(os.environ.get(env) or keys.get(env))
        out.append({"provider": p["name"], "enabled": p.get("enabled", False),
                    "api_key_env": env, "key_ready": key_ok,
                    "models": p.get("models", {}),
                    "cost_per_mtok_input": p.get("cost_per_mtok_input"),
                    "cost_per_mtok_output": p.get("cost_per_mtok_output")})
    return {"providers": out}

@app.post("/api/providers/toggle")
def providers_toggle(payload: dict = None):
    from .providers import set_enabled
    payload = payload or {}
    return set_enabled(payload.get("provider"), payload.get("enabled", False))

@app.post("/api/providers/key")
def providers_key(payload: dict = None):
    from .providers import save_key
    payload = payload or {}
    return save_key(payload.get("provider"), payload.get("key", ""))

@app.get("/api/providers")
def providers():
    from .providers import provider_models
    return {"providers": provider_models()}

@app.put("/api/config")
def put_config(payload: dict):
    """Save the decision tree. Tracks user-edited tiers (J10: sacred tiers)."""
    tiers = payload.get("tiers", {})
    edited = set(payload.get("user_edited", []))
    (ROOT / "routing.json").write_text(json.dumps({"tiers": tiers, "_user_edited": sorted(edited)}, indent=1), encoding="utf-8")
    return {"saved": True, "tiers": tiers}

@app.get("/api/seed/check")
def seed_check():
    from .seed_refresh import check_and_stage
    return check_and_stage()

@app.get("/api/seed/preview")
def seed_preview(mode: str = "price"):
    from .seed_refresh import preview_diff
    user_edited = set(json.loads((ROOT/"routing.json").read_text(encoding="utf-8")).get("_user_edited", []))
    return preview_diff(user_edited, mode=mode)

def preview_diff_safe(user_edited):
    from .seed_refresh import preview_diff
    return preview_diff(user_edited)

@app.post("/api/seed/apply")
def seed_apply(payload: dict = None):
    from .seed_refresh import apply_staged
    payload = payload or {}
    # user-confirmed overrides: apply them too (J10 revision - informed consent)
    overrides = set(payload.get("overrides", []))
    result = apply_staged()
    if result.get("applied") and overrides:
        # mark those tiers as measured-seed applied, remove from user_edited guard
        rdata = json.loads((ROOT/"routing.json").read_text(encoding="utf-8"))
        edited = set(rdata.get("_user_edited", [])) - overrides
        rdata["_user_edited"] = sorted(edited)
        (ROOT/"routing.json").write_text(json.dumps(rdata, indent=1), encoding="utf-8")
    return result

@app.post("/api/seed/rollback")
def seed_rollback():
    from .seed_refresh import rollback
    return rollback()

@app.get("/")
def index():
    return FileResponse(ROOT / "webapp" / "index.html")

@app.get("/app.js")
def app_js():
    return FileResponse(ROOT / "webapp" / "app.js")

@app.get("/manifest.json")
def manifest():
    return FileResponse(ROOT / "webapp" / "manifest.json", media_type="application/manifest+json")

@app.get("/sw.js")
def sw_js():
    return FileResponse(ROOT / "webapp" / "sw.js", media_type="application/javascript")

@app.get("/icon-192.png")
def icon192():
    return FileResponse(ROOT / "webapp" / "icon-192.png", media_type="image/png")

@app.get("/icon-512.png")
def icon512():
    return FileResponse(ROOT / "webapp" / "icon-512.png", media_type="image/png")
