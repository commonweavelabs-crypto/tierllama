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
import json, time, datetime
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

@app.get("/")
def index():
    return FileResponse(ROOT / "webapp" / "index.html")

@app.get("/app.js")
def app_js():
    return FileResponse(ROOT / "webapp" / "app.js")
