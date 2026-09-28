"""J16 Gap B: machine profiles — the machine dimension becomes first-class.

Adapted from NVIDIA Personal-AI-Router, Apache-2.0 (node inventory +
node-settings), but Tierllama's version is USER-DECLARED machine roles:
the spec's hard rule is that a machine's CLASS is always user-confirmed —
we never guess a workhorse. Discovery (J5) finds machines; bench (J8)
measures model@machine pairs (Gap A); this module gives each machine an
identity + role so J13's scheduler can route night work to night machines.

Shape (spec "Best-practice shape"):
  machine_profile = {host, name (user-given), class (user-confirmed),
                     windows, pairs: [{model, timing_fit, max_fit, tok_s,
                     cold_load_s}]}

One JSON per machine in logs/fleet/<host>.json. Three modules, three files,
one direction of data flow: discover → bench → machines. No new daemons.

Classes (J16 spec):
  workhorse       — the user's daily machine (user-confirmed)
  always_on       — runs any time (user-confirmed)
  night_only      — night-window machine, e.g. the mini box (user-confirmed)
  cloud_scheduled — cloud providers (never local; represented, not profiled)
"""
import json
from pathlib import Path
from .config import SCHEDULER

ROOT = Path(__file__).parent.parent
FLEET_DIR = ROOT / "logs" / "fleet"

CLASSES = ("workhorse", "always_on", "night_only", "cloud_scheduled")

def profile_path(host: str) -> Path:
    return FLEET_DIR / f"{host}.json"

def load_profile(host: str) -> dict | None:
    p = profile_path(host)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def load_all() -> dict:
    """All machine profiles keyed by host."""
    if not FLEET_DIR.exists():
        return {}
    out = {}
    for p in FLEET_DIR.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            out[d.get("host", p.stem)] = d
        except Exception:
            continue
    return out

def upsert_profile(host: str, name: str | None = None, machine_class: str | None = None,
                   windows: dict | None = None, pairs: list | None = None) -> dict:
    """Create or update a machine profile. CLASS CHANGES REQUIRE user=True —
    this function is the CONSENT BOUNDARY: webapp passes the user's explicit
    answer; there is no inferred/automatic class anywhere in this module."""
    FLEET_DIR.mkdir(parents=True, exist_ok=True)
    existing = load_profile(host) or {"host": host, "created_at": _now(), "pairs": []}
    if name is not None:
        existing["name"] = name
    if machine_class is not None:
        if machine_class not in CLASSES:
            raise ValueError(f"machine class '{machine_class}' not in {CLASSES}")
        existing["class"] = machine_class
        existing["class_confirmed_by"] = "user"          # spec: never guess
        existing["class_confirmed_at"] = _now()
    if windows is not None:
        existing["windows"] = windows
    if pairs is not None:
        existing["pairs"] = pairs
    existing["updated_at"] = _now()
    profile_path(host).write_text(json.dumps(existing, indent=1, ensure_ascii=False), encoding="utf-8")
    return existing

def delete_profile(host: str) -> bool:
    p = profile_path(host)
    if p.exists():
        p.unlink()
        return True
    return False

def attach_pairs_from_bench(host: str, bench_by_key: dict) -> dict | None:
    """Gap C helper: fill a machine's pairs from the (Gap A) bench keys
    belonging to this host. Only measured pairs are attached (source truth)."""
    prof = load_profile(host)
    if prof is None:
        return None
    pairs = []
    for key, rec in bench_by_key.items():
        if not key.endswith(f"@{host}"):
            continue
        pairs.append({"model": rec["model"],
                      "timing_fit": rec.get("timing_fit"),
                      "max_fit": rec.get("max_fit"),
                      "tok_s": rec.get("tok_s"),
                      "cold_load_s": rec.get("cold_load_s")})
    existing_pairs = {p["model"]: p for p in (prof.get("pairs") or [])}
    for p in pairs:
        existing_pairs[p["model"]] = p   # bench overrides; user data (name/class) untouched
    prof["pairs"] = list(existing_pairs.values())
    profile_path(host).write_text(json.dumps(prof, indent=1, ensure_ascii=False), encoding="utf-8")
    return prof

def worker_class_for(host: str, lane: str, now=None) -> str:
    """J13 hookup: worker class from machine_profile (replaces the provisional
    lane mapping when a profile exists). Falls back to the provisional
    mapping for un-profiled machines (documented fallback)."""
    prof = load_profile(host)
    if prof and prof.get("class"):
        return prof["class"]
    from .worker_classes import class_for_lane
    return class_for_lane(lane)

def _now():
    import datetime
    return datetime.datetime.now().isoformat(timespec="seconds")