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
import json, re, os, re, platform, socket, subprocess, threading, time, datetime
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

_discovery_cache: dict = {"ts": 0.0, "peers": None}   # raw scan result cache
_DISCOVERY_TTL_S = 60.0        # serve cached scan for 1 min; refresh in background
_discovery_lock = threading.Lock()

def _discover_cached() -> list:
    """LAN scan with instant serve + background refresh (J17 T4 policy: the
    response NEVER waits on the network; a background thread keeps it fresh)."""
    import time as _t
    now = _t.time()
    with _discovery_lock:
        fresh = now - _discovery_cache["ts"] < _DISCOVERY_TTL_S
        cached = _discovery_cache["peers"]
    if cached is not None and fresh:
        return cached
    if cached is not None:            # stale: serve it, refresh behind the lock
        def worker():
            try:
                result = discover()
                with _discovery_lock:
                    _discovery_cache["ts"] = _t.time()
                    _discovery_cache["peers"] = result
            except Exception:
                pass
        if not any(getattr(t, 'daemon', False) and t.name == 'fleet-refresh' for t in threading.enumerate()):
            threading.Thread(target=worker, daemon=True, name='fleet-refresh').start()
        return cached
    # cold: scan inline once (server just booted), then always serve cached
    result = discover()
    with _discovery_lock:
        _discovery_cache["ts"] = now
        _discovery_cache["peers"] = result
    return result

@app.get("/api/fleet")
def fleet():
    peers = _discover_cached()
    # J7 fix: include THIS machine's Ollama (localhost) in the fleet - the LAN scan
    # skips 127.0.0.1, so local models never showed in the UI dropdowns:
    mine = _this_machine_hosts()
    # J17: fold any discovered peer that IS this machine (its own LAN IP, e.g.
    # seen as host.docker.internal) into the localhost entry — one row, models
    # reused from the scan (no second /api/tags fetch that can timeout under load).
    self_models: list | None = None
    kept = []
    for p in peers:
        if p.get("host") in mine:
            if p.get("models"):
                self_models = p["models"]
        else:
            kept.append(p)
    peers = kept
    # this machine's own Ollama (localhost) first — independent of the LAN scan:
    try:
        tags = json.loads(urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=8).read())
        peers.insert(0, {"host": "127.0.0.1", "port": 11434, "kind": "ollama (this machine)",
                         "models": [m["name"] for m in tags.get("models", [])]})
    except Exception:
        if self_models:  # scan already saw this machine's models — use them
            peers.insert(0, {"host": "127.0.0.1", "port": 11434, "kind": "ollama (this machine)",
                             "models": self_models})
    # J17 T4: enrich NEW machines in the background (slow probes never block
    # this response); this request serves instantly from the enrichment cache.
    _ensure_enriched([p.get("host", "") for p in peers if p.get("host") not in ("127.0.0.1", "localhost")])
    peers = [_with_fleet_name(p) for p in peers]
    return {"peers": peers, "generated": datetime.datetime.now().isoformat(timespec="seconds")}


# ---------- J17 T1: fleet naming ----------
# Names live in their own sidecar so the discovery scan (which rewrites peers
# every call) never clobbers a user's rename. Key = "host:port" because the
# discover path has no stable node_id (unlike Fleet's zeroconf uuid).
FLEET_NAMES_PATH = ROOT / "logs" / "fleet_names.json"
# J17 T4: enrichment cache — name/OS lookups are SLOW (nbtstat ~6s, ping ~5s),
# so they run ONCE per new machine in a background thread and persist here.
# /api/fleet serves from this cache instantly; it never blocks on probes.
FLEET_ENRICH_PATH = ROOT / "logs" / "fleet_enrich.json"

# Auto-name chain (informed initial naming, J17 spec — user can always override):
# 1. reverse DNS / mDNS hostname  (Mac: "MacBookAir.lan" -> "MacBookAir")
# 2. NetBIOS name broadcast       (Windows/Mac answer: e.g. "DESKTOP-SHN3HMJ")
# 3. OS fingerprint via ping TTL  (128=Windows, 64=Mac/Linux) -> "Windows machine (ip)"
# 4. raw IP
_DNS_ALIAS_JUNK = {"host.docker.internal", "docker.internal", "localhost",
                   "ip6-localhost", "ip6-allnodes", "ip6-allrouters"}
_name_cache: dict[str, str] = {}          # ip -> netbios/os name (slow lookups only)
def _fleet_names() -> dict:
    if not FLEET_NAMES_PATH.exists():
        return {}
    try:
        return json.loads(FLEET_NAMES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _load_enrich() -> dict:
    try:
        return json.loads(FLEET_ENRICH_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_enrich(d: dict):
    FLEET_ENRICH_PATH.parent.mkdir(parents=True, exist_ok=True)
    FLEET_ENRICH_PATH.write_text(json.dumps(d, indent=1), encoding="utf-8")

def _enrich_host(ip: str) -> dict:
    """One slow enrichment pass: name chain + OS fingerprint. Called only from
    the background enricher (never inside a request)."""
    name = _reverse_dns_name(ip) or _netbios_name(ip) or _os_fallback_name(ip) or ip
    os_guess = ""
    try:
        ttl = _ping_ttl(ip)
        if ttl >= 127:
            os_guess = "Windows"
        elif 56 <= ttl <= 64:
            os_guess = "Mac/Linux"
    except Exception:
        pass
    return {"name": name, "os": os_guess, "enriched_at": datetime.datetime.now().isoformat(timespec="seconds")}

def _ping_ttl(ip: str) -> int:
    import re as _re
    r = subprocess.run(["ping", "-n", "1", "-w", "1500", ip],
                       capture_output=True, text=True, timeout=5)
    m = _re.search(r"TTL[=:]\s*(\d+)", r.stdout or "")
    return int(m.group(1)) if m else -1

def _ensure_enriched(ips: list[str]):
    """Kick a background thread to enrich any cache-miss IPs (fire-and-forget).
    This is the J17 T4 lightweight policy: probe ONLY new machines, never poll."""
    enr = _load_enrich()
    missing = [ip for ip in ips if ip not in enr]
    if not missing:
        return
    def worker():
        for ip in missing:
            try:
                result = _enrich_host(ip)
                d = _load_enrich()
                d[ip] = result
                _save_enrich(d)
            except Exception:
                continue
    threading.Thread(target=worker, daemon=True).start()

def _fleet_names() -> dict:
    if not FLEET_NAMES_PATH.exists():
        return {}
    try:
        return json.loads(FLEET_NAMES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _reverse_dns_name(ip: str) -> str:
    """mDNS/DNS reverse lookup, sanitized. Empty on junk aliases or failure."""
    try:
        full = socket.gethostbyaddr(ip)[0].strip()
    except Exception:
        return ""
    # Docker Desktop maps the HOST's own LAN IP to host.docker.internal — a
    # self-alias, never a real peer name. Reject before taking the first label.
    if "docker" in full.lower() or full.lower() in _DNS_ALIAS_JUNK:
        return ""
    host = full.split(".")[0]
    if not host or host.replace(".", "").isdigit():
        return ""
    return host

def _netbios_name(ip: str) -> str:
    """Windows broadcasts its machine name via NetBIOS (works cross-OS: a Mac
    also answers). Slow (~4s on misses) - cached per process."""
    import re as _re
    if ip in _name_cache:
        return _name_cache[ip]
    out = ""
    try:
        res = _run_nbtstat(ip)
        m = _re.search(r"([A-Za-z0-9\-_]{2,15})\s+<00>\s+UNIQUE", res, _re.IGNORECASE)
        if m:
            out = m.group(1).strip()
    except Exception:
        pass
    _name_cache[ip] = out
    return out

def _run_nbtstat(ip: str) -> str:
    import subprocess
    r = subprocess.run(["nbtstat", "-A", ip], capture_output=True, text=True, timeout=6)
    return r.stdout or ""

def _os_fallback_name(ip: str) -> str:
    """Ping-TTL OS fingerprint: Windows default TTL 128, Unix-family 64."""
    import subprocess
    if ip in _name_cache:
        return _name_cache[ip]
    out = ""
    try:
        r = subprocess.run(["ping", "-n", "1", "-w", "1500", ip],
                           capture_output=True, text=True, timeout=5)
        import re as _re
        m = _re.search(r"TTL[=:]\s*(\d+)", r.stdout or "")
        if m:
            ttl = int(m.group(1))
            if ttl >= 127:
                out = f"Windows machine ({ip})"
            elif 56 <= ttl <= 64:
                out = f"Mac/Linux machine ({ip})"
    except Exception:
        pass
    if not out:
        out = ip
    _name_cache[ip] = out
    return out

def _this_machine_hosts() -> set:
    """All host labels this machine answers to (loopback + its LAN IP), so the
    fleet list doesn't show the same PC twice (localhost + LAN IP)."""
    mine = {"127.0.0.1", "localhost"}
    try:
        hn = socket.gethostname()
        mine.add(hn.lower())
        # resolve hostname to ALL its interface addresses (Tailscale 100.x,
        # LAN 192.168.x, ...) so a peer entry for any of them is recognized
        # as this machine and hidden (J17 dedupe).
        import getpass
        mine.add(getpass.getuser().lower() + "-pc")  # legacy naming hint, harmless
        for info in socket.getaddrinfo(hn, None, socket.AF_INET):
            mine.add(info[4][0].lower())
    except Exception:
        pass
    # Docker's self-alias maps the host LAN IP to host.docker.internal —
    # treat the LAN IP itself as "mine" by asking the OS which interfaces exist.
    try:
        import ipaddress
        raw = subprocess_run_ipconfig()
        for ip in __import__("re").findall(r"IPv4[^\n]*?:\s*([0-9.]+)", raw):
            mine.add(ip.strip())
    except Exception:
        pass
    return mine

def subprocess_run_ipconfig() -> str:
    r = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=6)
    return r.stdout or ""

def _default_fleet_name(peer: dict) -> str:
    host = peer.get("host", "")
    if host.lower() in ("127.0.0.1", "localhost"):
        return socket.gethostname()
    enriched = _load_enrich().get(host, {})
    return enriched.get("name", "") or peer.get("host", "")

def _with_fleet_name(peer: dict) -> dict:
    key = f"{peer.get('host')}:{peer.get('port')}"
    name = _fleet_names().get(key, "")
    peer = dict(peer)
    is_self = peer.get("host", "").lower() in ("127.0.0.1", "localhost")
    if is_self:
        # this machine: name it plainly and read the OS straight from the OS
        peer.setdefault("name", socket.gethostname())
        peer["name"] = peer["name"] if not name else name
        peer.setdefault("kind", "ollama (this machine)")
        peer["os"] = f"{platform.system()} {platform.release()}" if platform.system() else "this machine"
    else:
        peer["name"] = name or _default_fleet_name(peer) or peer.get("host", "")
        enr = _load_enrich().get(peer.get("host", ""), {})
        if enr.get("os"):
            peer["os"] = enr["os"]
    peer["name_user_set"] = bool(name)
    return peer

@app.post("/api/fleet/name")
def api_fleet_name(payload: dict = None):
    payload = payload or {}
    host, name = str(payload.get("host", "")), str(payload.get("name", "")).strip()
    port = int(payload.get("port", 0))
    if not host:
        return {"ok": False, "error": "host required"}
    names = _fleet_names()
    if name:
        names[f"{host}:{port}"] = name[:64]
    else:
        names.pop(f"{host}:{port}", None)   # empty name = back to the hostname default
    FLEET_NAMES_PATH.write_text(json.dumps(names, indent=1), encoding="utf-8")
    return {"ok": True, "name": name}

@app.get("/api/config")
def get_config():
    try:
        rdata = json.loads((ROOT / "routing.json").read_text(encoding="utf-8"))
        user_edited = rdata.get("_user_edited", [])
    except Exception:
        user_edited = []
    return {"tiers": _load_tiers(), "classifier": CLASSIFIER["model"], "user_edited": user_edited}

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
    digests = hash-verified by Ollama itself). We never fetch from random URLs.
    J19.5: pulls the ACTUAL configured Jev brain (qwen3:8b since the swap) — tag
    derived from config, never hardcoded, so a future brain bump updates itself."""
    import subprocess as _sp
    from .config import CLASSIFIER as C
    tag = C["model"]
    try:
        r = _sp.run(["ollama", "pull", tag], capture_output=True, text=True, timeout=3600)
        return {"ok": r.returncode == 0, "error": r.stderr[-200:] if r.returncode else "", "model": tag}
    except Exception as e:
        return {"ok": False, "error": str(e)[:150], "model": tag}

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

# ---------- J19.5: model-suggestions hardware gate ----------
# The model-suggestions feature (Brain 2 + Rescan) uses the Jev brain for its
# matrix read — on constrained hardware that's unaffordable to keep resident.
# Gate design (docs/JEV-BRAIN-DECISION.md §Hardware tiers): state is reported,
# never assumed; "usable" requires the brain present AND enough free VRAM.
JEV_VRAM_NEED_MB = 6000   # 8b Q4_K_M ≈ 5.2GB weights + headroom for KV ctx

def _vram_mb() -> dict:
    """Total/free VRAM in MB via nvidia-smi. None on no-GPU machines (the gate
    treats 'no discrete GPU' as constrained — CPU-only 8b = ~66s/decision)."""
    import subprocess as _sp
    try:
        r = _sp.run(["nvidia-smi", "--query-gpu=memory.total,memory.used",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=10)
        if r.returncode != 0 or not r.stdout.strip():
            return {"total": None, "free": None}
        t, u = [int(x) for x in r.stdout.strip().splitlines()[0].split(",")]
        return {"total": t, "free": t - u}
    except Exception:
        return {"total": None, "free": None}

@app.get("/api/jev/hardware")
def jev_hardware():
    """Gate state for the model-suggestions toggle. installed = brain digest on
    disk; usable = installed AND (GPU with free VRAM >= need)."""
    import urllib.request as _u
    from .config import CLASSIFIER as C
    tag = C["model"]
    installed = False
    digest = None
    size_mb = None
    try:
        tags = json.loads(_u.urlopen("http://127.0.0.1:11434/api/tags", timeout=5).read())
        for m in tags.get("models", []):
            if m.get("name") == tag:
                installed = True
                digest = (m.get("digest") or "")[:12]
                size_mb = round((m.get("size") or 0) / 1e6)
                break
    except Exception:
        pass
    v = _vram_mb()
    gpu = v["total"] is not None
    vram_ok = gpu and v["free"] is not None and v["free"] >= JEV_VRAM_NEED_MB
    usable = bool(installed and vram_ok)
    reason = ("ok" if usable else
              (f"brain '{tag}' not downloaded yet" if not installed else
               f"free VRAM {v['free']}MB < need {JEV_VRAM_NEED_MB}MB — close big apps (ComfyUI, games) or run on the GPU box"))
    return {"model": tag, "installed": installed, "digest": digest, "size_mb": size_mb,
            "gpu": gpu, "vram_total_mb": v["total"], "vram_free_mb": v["free"],
            "vram_need_mb": JEV_VRAM_NEED_MB, "usable": usable, "reason": reason}

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


# ---------- J19 model rater (dynamic categorization) ----------
def user_stance_notes() -> list[str]:
    """Gui's standing model-trust stances (Sep 29-30 session, recorded in the
    tierllama-debug-sessions skill) — fed to Jev as operator preferences."""
    return [
        "qwen3 small variants (0.6b/4b) are NOT trusted for interactive driving",
        "ornith-1.5:35b is acceptable for EASY-NOW or async work at most",
        "box model qwen38-27b-iq3s is the trusted overnight/LATER workhorse",
        "kimi-k3:cloud is premium — reserve for EXPERT when optimizing for price",
    ]

@app.get("/api/models/rated")
def api_models_rated(mode: str = "price", include_local: bool = True,
                     include_small: bool = False, source: str = "used"):
    """THE per-tier candidate lists (Gui spec): every reachable model, rated,
    grouped by tier, best-pick first. Serves instantly; probes run background.
    include_small: sub-9B models are toy class — out of suggestions by default.
    source: 'used' (base vetted catalog) | 'catalog' (full provider catalog
    via the J20 oracle — models the user never used, live-validated)."""
    from .rater import tier_categories, unbenched_models
    cats = tier_categories(mode, include_local=include_local, include_small=include_small,
                           source=source)
    cats["unbenched"] = unbenched_models()
    return cats

@app.post("/api/bench/run")
def api_bench_run(payload: dict = None):
    """J19: benchmark specific unbenched models on request (from the UI warning
    button). Background thread; polled via GET on the same path."""
    payload = payload or {}
    models = payload.get("models") or []
    if not models:
        return {"started": False, "reason": "no models given"}
    if getattr(api_bench_run, "_running", False):
        return {"running": True, "current": getattr(api_bench_run, "_current", "?")}
    api_bench_run._running = True
    def worker():
        from .bench import probe_model
        done = []
        try:
            for m in models:
                api_bench_run._current = m
                try:
                    probe_model(m)
                    done.append(m)
                except Exception:
                    continue
        finally:
            api_bench_run._running = False
            api_bench_run._last = len(done)
            api_bench_run._current = ""
    import threading as _th
    _th.Thread(target=worker, daemon=True).start()
    return {"started": True, "total": len(models)}

@app.get("/api/bench/run")
def api_bench_status():
    return {"running": getattr(api_bench_run, "_running", False),
            "current": getattr(api_bench_run, "_current", ""),
            "last_result": getattr(api_bench_run, "_last", None)}

@app.get("/api/suggestions")
def api_suggestions(mode: str = "price", include_local: bool = True,
                    include_small: bool = False, source: str = "used"):
    """Single picks for the decision tree. J19 v2: JEV brains the pick — every
    guardrailed candidate gets a dossier; Jev scores 0-100 per tier with user
    stance notes weighed; the top score wins. The heuristic rater (bands,
    ceiling caps, cost sort) demoted to FALLBACK when Jev is unreachable.
    J20: source='catalog' widens the pool to the full live-validated provider
    catalog (Jev discovers models the user never used)."""
    from .rater import tier_categories
    cats = tier_categories(mode, include_local=include_local, include_small=include_small,
                           source=source)
    # gather guardrail-legal candidates per tier (the three hard lines):
    guardrailed = {}
    for key, info in cats["tiers"].items():
        diff, timing = key.split("/")
        # rebuild the same qualification tier_categories used: ask the rater
        # for its full row set so we can re-derive with timings included
        guardrailed[key] = info
    picks, jev_meta = {}, {}
    try:
        from .jev_rater import rate_tiers, TIER_JOBS
        from .rater import rate_all, gather_pool
        pool = gather_pool(source=source)
        if not include_local:
            pool = {"local": [], "cloud": pool["cloud"]}
        rows = rate_all(pool)
        tiers = [(k.split("/")[0], k.split("/")[1]) for k in cats["tiers"]]
        ratings = rate_tiers(rows, tiers, user_stance_notes())
        from .jev_rater import apply_stance_guardrails
        ratings = apply_stance_guardrails(ratings, rows)
        for key, info in cats["tiers"].items():
            cands = info.get("candidates") or []
            if not cands:
                continue
            diff, timing = key.split("/")
            legal = {r["model"]: r for r in rows
                     if r["model"] in {c["model"] for c in cands}}
            jr = ratings.get(key, {})
            if jr.get("ok") and jr.get("scores"):
                # Jev's pick among guardrailed candidates ONLY:
                scored = [(s, m) for m, s in jr["scores"].items() if m in legal]
                if scored:
                    scored.sort(reverse=True)
                    m = scored[0][1]
                    picks[key] = {"provider": "auto", "model": m,
                                  "thinking": "max" if diff in ("HARD", "EXPERT") else "normal",
                                  "source": "jev"}
                    jev_meta[key] = {"scores": jr["scores"], "jev": True}
                    continue
            # fallback: heuristic first candidate
            pick = cands[0]
            picks[key] = {"provider": "auto", "model": pick["model"],
                          "thinking": "max" if diff in ("HARD", "EXPERT") else "normal",
                          "source": f"rated-{mode}"}
            jev_meta[key] = {"scores": jr.get("scores") or {}, "jev": False}
        return {"tiers": picks, "mode": mode, "pool_size": cats["pool_size"],
                "tiers_flagged": {k: v["flag"] for k, v in cats["tiers"].items() if v.get("flag")},
                "jev": {"used": any(v.get("jev") for v in jev_meta.values()), "tiers": jev_meta}}
    except Exception as e:
        # hard fallback: heuristic-only (never break suggestions)
        picks = {}
        for key, info in cats["tiers"].items():
            diff = key.split("/")[0]
            cands = info.get("candidates") or []
            if cands:
                picks[key] = {"provider": "auto", "model": cands[0]["model"],
                              "thinking": "max" if diff in ("HARD", "EXPERT") else "normal",
                              "source": f"rated-{mode}"}
        return {"tiers": picks, "mode": mode, "pool_size": cats["pool_size"],
                "tiers_flagged": {k: v["flag"] for k, v in cats["tiers"].items() if v.get("flag")},
                "jev": {"used": False, "error": str(e)[:120]}}

# ---------- J20 catalog oracle (admin endpoints) ----------
@app.get("/api/catalog")
def api_catalog_refresh(source: str = "cloud", max_pages: int = 1, include_detail: bool = False):
    """Refresh the catalog (no timers — refresh happens ONLY when this is hit
    or when the UI toggle first enables catalog mode). Fast mode: listings
    only; detail mode adds ctx/params/price per family (slower, ~1 req each)."""
    from . import catalog as C
    if source == "library":
        st = C.scrape_library(max_pages=max_pages, include_detail=include_detail)
    else:
        st = C.scrape_cloud(include_detail=include_detail)
    st["live_rows"] = len(C.catalog_rows())
    return st

@app.post("/api/catalog/validate")
def api_catalog_validate(payload: dict = None):
    """Liveness re-validation for catalog entries (rot guard). No payload =
    re-check all cloud entries. The deepseek-v4-flash 410 lesson, runnable."""
    from . import catalog as C
    names = (payload or {}).get("names")
    return C.validate_liveness(names)

@app.get("/api/catalog/pool")
def api_catalog_pool():
    """What the catalog adds vs the base vetted catalog (UI disclosure)."""
    from . import catalog as C
    from .rater import _catalog_extended_catalog, CLOUD_CATALOG
    ext = _catalog_extended_catalog()
    new = [m for m in ext if m not in CLOUD_CATALOG]
    rows = {r["model"]: r for r in C.catalog_rows()}
    return {"base": CLOUD_CATALOG, "extended": ext,
            "new_from_catalog": new,
            "new_details": [{"model": m, "ctx": rows.get(m.split(':')[0], {}).get("context_length"),
                             "price_in": rows.get(m.split(':')[0], {}).get("price_in_per_mtok"),
                             "price_out": rows.get(m.split(':')[0], {}).get("price_out_per_mtok")}
                            for m in new if rows.get(m.split(':')[0])],
            "live_rows": len(C.catalog_rows())}

# ---------- J14 capability loop (BETA) ----------
@app.get("/api/capability")
def api_capability():
    from .capability import Ledger, load_recent_bumps, evaluate_bump, seed_from_bench
    from .outcomes import summary as outcome_summary
    # J17 T2: idempotent backfill from bench history — first call populates the
    # ledger so the panel shows evidence instead of an empty beta scaffold.
    seed = seed_from_bench()
    led = Ledger()
    led.load()
    keys = sorted(led.events.keys())
    rows = [{"key": k, **led.stats(k)} for k in keys]
    rows.sort(key=lambda r: -(r["samples"]))
    # J17 T3 dry-run visibility: for every class with evidence, show what the
    # bump rule WOULD decide right now (independent of the gate).
    would = []
    for r in rows[:50]:
        parts = r["key"].split("|")
        d = evaluate_bump(led, None, bench_key=parts[0], difficulty=parts[1],
                          timing=parts[2], when=parts[3] if len(parts) > 3 else "NOW",
                          current_tier=parts[1])
        if d.get("would_bump"):
            would.append({"key": d["key"], "from": d["from_tier"], "to": d["to_tier"],
                          "reason": d["reason"]})
    from .config import CAPABILITY
    # bump events recorded in state (they exist even when gate OFF - dry-run transparency)
    bumps = load_recent_bumps()
    return {"enabled": CAPABILITY["enabled"], "beta": CAPABILITY["beta"],
            "params": {k: CAPABILITY[k] for k in
                       ("bump_after_failures", "cooldown_h", "max_moves_per_day",
                        "min_samples", "canary_pct", "canary_successes")},
            "outcomes": outcome_summary(),
            "classes": rows[:50],
            "bumps": bumps,
            "would_bump": would,
            "seeded": seed}

@app.post("/api/capability/toggle")
def api_capability_toggle(payload: dict = None):
    # same consent pattern as the scheduler gate: user knowingly opts in/out.
    # The CAPABILITY gate line carries the same comment text as SCHEDULER's, so
    # this must disambiguate - rewrite INSIDE the CAPABILITY block only.
    payload = payload or {}
    want = bool(payload.get("enabled"))
    cfg_path = Path(__file__).parent.parent / "tierllama" / "config.py"
    src = cfg_path.read_text(encoding="utf-8")
    i = src.find("CAPABILITY = {")
    j = src.find("SCHEDULER = {")
    if i < 0 or j < 0 or j < i:
        return {"ok": False, "error": "CAPABILITY block not found in config.py"}
    block = src[i:j]
    new_block = re.sub(r'("enabled": )(True|False)(,      # BETA feature gate)',
                       lambda m: f"{m.group(1)}{want}{m.group(3)}", block, count=1)
    if new_block == block:
        return {"ok": False, "error": "gate line not found inside CAPABILITY block"}
    cfg_path.write_text(src[:i] + new_block + src[j:], encoding="utf-8")
    from . import config as _cfg
    _cfg.CAPABILITY["enabled"] = want
    return {"ok": True, "enabled": want}


# ---------- J16 machines (hardware census) ----------
@app.get("/api/machines")
def api_machines():
    from .machines import load_all
    from .bench_keys import load_bench_by_key
    from .pair_labels import label_pairs
    bench = load_bench_by_key()
    out = []
    for host, prof in sorted(load_all().items()):
        labeled = label_pairs(host) or prof   # refresh measured pairs on read
        out.append({"host": host, "name": labeled.get("name") or host,
                    "class": labeled.get("class"),
                    "class_confirmed_by": labeled.get("class_confirmed_by"),
                    "windows": labeled.get("windows"),
                    "pairs": labeled.get("pairs") or []})
    # un-profiled hosts found by discovery but never given a profile:
    profiled = {m["host"] for m in out}
    try:
        from .discover import discover
        for h in discover():
            if h["host"] not in profiled:
                out.append({"host": h["host"], "name": h["host"], "class": None,
                            "windows": None, "pairs": [], "models": h.get("models") or []})
    except Exception:
        pass  # discovery offline - profiles alone still render
    return {"machines": out}

@app.post("/api/machines/class")
def api_machine_class(payload: dict = None):
    # THE consent boundary: this endpoint is the only path that sets a class,
    # and it requires the user's explicit answer from the UI.
    from .machines import upsert_profile
    payload = payload or {}
    host = payload.get("host")
    machine_class = payload.get("class")
    name = payload.get("name")
    if not host or not machine_class:
        return {"ok": False, "error": "host and class required"}
    try:
        prof = upsert_profile(host, name=name, machine_class=machine_class,
                              windows=payload.get("windows"))
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "profile": prof}


# ---------- J13 scheduler (BETA) ----------
@app.get("/api/schedule")
def api_schedule():
    from .config import SCHEDULER as _S
    out = {"enabled": _S.get("enabled"), "beta": _S.get("beta")}
    if not _S.get("enabled"):
        return out
    from . import scheduler as _sched
    jobs = _sched.list_jobs()
    out["clarify"] = [j for j in jobs if j["status"] == "clarify"] + [j for j in jobs if j.get("needs_clarification")]
    out["upcoming"] = [j for j in jobs if j["status"] in ("pending", "due")]
    out["recent"] = [j for j in jobs if j["status"] in ("dispatched", "done", "failed", "cancelled")][:10]
    return out

@app.post("/api/schedule/resolve")
def api_schedule_resolve(payload: dict = None):
    payload = payload or {}
    from .config import SCHEDULER as _S
    if not _S.get("enabled"):
        return {"ok": False, "reason": "scheduler beta disabled"}
    from . import scheduler as _sched
    try:
        j = _sched.resolve(payload.get("id"), due_at=payload.get("due_at"),
                           lane=payload.get("lane"), action=payload.get("action", "schedule"))
        return {"ok": True, "job": j}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

@app.post("/api/schedule/toggle")
def api_schedule_toggle(payload: dict = None):
    """User knowingly opts in/out of the BETA scheduler (writes config flag)."""
    payload = payload or {}
    want = bool(payload.get("enabled"))
    cfg_path = Path(__file__).parent.parent / "tierllama" / "config.py"
    src = cfg_path.read_text(encoding="utf-8")
    # match either True or False on the gate line (regex bug 2026-09-25: OFF toggle
    # was a silent no-op whenever the file already said True)
    new = re.sub(r'("enabled": )(True|False)(,\s*# BETA feature gate)',
                 lambda m: f"{m.group(1)}{want}{m.group(3)}", src, count=1)
    if new == src:
        return {"ok": False, "error": "gate line not found in config.py - not written"}
    cfg_path.write_text(new, encoding="utf-8")
    # flip the live module state too (server needs no restart)
    from . import config as _cfg
    _cfg.SCHEDULER["enabled"] = want
    return {"ok": True, "enabled": want}

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

@app.get("/icons/svg/{name}.svg")
def icon_svg(name: str):
    """Vendored SVG icons (Simple Icons CC0 / Lucide MIT). Path-segment only:
    name is restricted to safe chars, no traversal possible."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        return JSONResponse({"error": "bad icon name"}, status_code=400)
    p = ROOT / "webapp" / "icons" / "svg" / f"{name}.svg"
    if not p.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(p, media_type="image/svg+xml")

@app.get("/icons/{name}.{ext}")
def brand_mark(name: str, ext: str):
    """Brand/own marks (Tierllama logo etc). Single safe segment, svg/png only."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name) or ext not in ("svg", "png"):
        return JSONResponse({"error": "bad icon name"}, status_code=400)
    p = ROOT / "webapp" / "icons" / f"{name}.{ext}"
    if not p.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    mt = "image/svg+xml" if ext == "svg" else "image/png"
    return FileResponse(p, media_type=mt)

@app.get("/favicon.ico")
def favicon():
    return FileResponse(ROOT / "webapp" / "icons" / "tierllama.ico", media_type="image/x-icon")
