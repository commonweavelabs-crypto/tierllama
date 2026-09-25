"""Tierllama provider-grid health integration (J12+ T1 wiring).

Adapted from NVIDIA Personal-AI-Router, Apache-2.0 (the job-scheduler's
GPU-pressure signal feeding node ranking). https://github.com/NVIDIA/Personal-AI-Router

Behavior-safe by design (J12+ goal constraint: never silent behavior changes):
- health_snapshot() returns per-provider pressure data for the decision log;
  it NEVER changes which provider/model a request routes to in this milestone.
- The tier choice remains exactly as before; pressure is attached as
  *information* on the record. Promotion to a routing input happens when the
  sampler exists (next milestone) and is a separate, tested change.
- Fleet-backed providers (provenance "local-fleet", from tierllama/fleet.py)
  get live pressure from health.FleetPressure; cloud providers get None
  (no GPU) — also neutral, not penalized.
"""
import json, datetime
from pathlib import Path
from . import health as _health

ROOT = Path(__file__).parent.parent
HEALTH_LOG = ROOT / "logs" / "health.jsonl"

# Module-level pressure registry shared by dispatch.py (single source of truth).
_pressure = _health.FleetPressure()
_ever_sampled = False   # set True on the first gpu_sample() in this process


def gpu_sample(node_id: str, util: float, now=None) -> int:
    """Feed a GPU utilization sample (0-1 or 0-100) for a node; returns pressure."""
    global _ever_sampled
    _ever_sampled = True
    return _pressure.feed(node_id, util, now)


def attach_pressure(record: dict, provider_name: str | None = None) -> dict:
    """Attach current pressure info to a routing record (informational).
    provider_name None or unknown -> pressure: None (neutral, not penalized)."""
    node = provider_node(provider_name)
    record["gpu_pressure"] = {
        "provider": provider_name,
        "pressure": _pressure.node(node).pressure() if node else None,
    }
    return record


def provider_node(provider_name: str, providers: list[dict] | None = None) -> str | None:
    """Map a provider name to its pressure-node id: fleet providers track the
    host machine; cloud providers have none. Local default provider (127.0.0.1)
    maps to the literal node id 'localhost'."""
    providers = providers or []
    for p in (providers or []):
        if p.get("name") == provider_name:
            if p.get("provenance") == "local-fleet":
                return "fleet-" + provider_name
    # convention: the built-in LOCAL lane (Ollama on this machine) tracks as 'localhost'
    return "localhost" if provider_name in (None, "local", "LOCAL") else None


def snapshot_line() -> str | None:
    """One JSONL line for the decision-log companion (logs/health.jsonl), or
    None when no node has EVER reported (module-level flag, not time-based:
    staleness is about liveness, not about "is this the first run")."""
    snap = _pressure.snapshot()
    if not _ever_sampled or not any(v["ewma"] is not None for v in snap.values()):
        return None
    line = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "pressure": snap}
    return json.dumps(line, ensure_ascii=False)


def snapshot_write():
    line = snapshot_line()
    if line:
        p = ROOT / "logs" / "health.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(line + "\n")