"""Tierllama fleet discovery (J12+ T3, PAIR-derived).

Adapted from NVIDIA Personal-AI-Router, Apache-2.0
(nvpair-node-scanner: consolidated discovery, activity-vouching liveness,
anti-flap eviction, "a scan losing all known nodes is our own fault"
suppression). https://github.com/NVIDIA/Personal-AI-Router

Design (modular doctrine - own module, stdlib + zeroconf only):
- _ollama_ollama._tcp browse: any Ollama on the LAN advertising itself via
  zeroconf joins the fleet; J5's TCP sweep (discover.py) remains the fallback
  path for engines that don't advertise.
- Liveness (PAIR anti-flap rules, ported):
  * A node is EVICTED only after EVICT_AFTER_SCANS consecutive failed scans
    (PAIR: ~1 minute / ~10 failures), NOT on a single miss.
  * Two signals VOUCH for a busy node without probing (PAIR: "the only
    liveness evidence that gets stronger the busier a node is"):
      - a fresh successful fetch within VOUCH_ENRICH_SECONDS, or
      - fresh inference response bytes within VOUCH_BYTES_SECONDS.
  * A scan that loses ALL known nodes at once is treated as OUR fault: the
    scan is suppressed for SUPPRESS_SCANS (PAIR: up to 6 scans / ~30s) and
    nothing is penalized - one saturated machine must not drop the directory.
- Every node registered into the provider grid carries provenance
  "local-fleet" (per the seed/measured/user provenance model).
"""
from __future__ import annotations  # Py3.13 evaluates annotations eagerly; the
# `list` METHOD in class Fleet shadows the builtin for later `list[dict]`
# annotations in the same class body (def as_providers 3.13 crash) - deferred
# evaluation keeps annotations symbolic.
import json, socket, threading, time, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
FLEET_PATH = ROOT / "logs" / "fleet.json"

SERVICE_TYPE = "_ollama._tcp.local."   # what Ollama actually advertises on the LAN

VOUCH_ENRICH_SECONDS = 10.0    # PAIR: node-info enrichment in the last 10s vouches
VOUCH_INFER_SECONDS = 60.0     # PAIR: inference bytes in the last 60s vouch
MISS_THRESHOLD = 12            # scans a node may be absent before eviction (PAIR ~1 min)
SCAN_INTERVAL_S = 5.0          # PAIR: 5s scans
SUPPRESS_SCANS = 6             # PAIR: all-nodes-lost suppression window (~30s)


class FleetNode:
    def __init__(self, node_id, host, port, kind="ollama"):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.kind = kind
        self.models: list = []
        self.miss_streak = 0            # consecutive scans without any answer
        self.last_enrich_ts = 0.0       # fresh metadata fetch (vouch signal 1)
        self.last_infer_ts = 0.0        # inference bytes seen (vouch signal 2)
        self.probe_streak = 0           # consecutive failed TCP probes (~15s+)

    def to_dict(self):
        return {"node_id": self.node_id, "host": self.host, "port": self.port,
                "kind": self.kind, "models": self.models}


class Fleet:
    """LAN fleet registry with PAIR anti-flap liveness. Thread-safe, file-backed."""

    def __init__(self, store_path: Path | None = None):
        self.path = store_path or FLEET_PATH
        self._nodes: dict[str, FleetNode] = {}
        self._lock = threading.Lock()
        self._global_miss_streak = 0    # consecutive scans where EVERY known node missed
        self._load()

    # ---------- persistence ----------
    def _load(self):
        if not self.path.exists():
            return
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            for n in d.get("nodes", []):
                fn = FleetNode(n["node_id"], n["host"], n["port"], n.get("kind", "unknown"))
                fn.models = n.get("models", [])
                self._nodes[fn.node_id] = fn
        except Exception:
            pass  # corrupt store -> empty fleet, never crash the proxy

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        d = {"updated": datetime.datetime.now().isoformat(timespec="seconds"),
             "nodes": [n.to_dict() for n in self._nodes.values()]}
        self.path.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")

    # ---------- membership ----------
    def upsert(self, node_id, host, port, kind="ollama", models=None) -> dict:
        with self._lock:
            n = self._nodes.get(node_id)
            if n is None:
                n = FleetNode(node_id, host, port, kind)
                self._nodes[node_id] = n
            else:
                n.host, n.port, n.kind = host, port, kind
            if models is not None:
                n.models = models
            n.miss_streak = 0          # any contact resets eviction (PAIR anti-flap)
            n.probe_streak = 0
            self._save()
            return n.to_dict()

    def remove(self, node_id):
        with self._lock:
            self._nodes.pop(node_id, None)
            self._save()

    def list(self) -> list[dict]:
        return [n.to_dict() for n in self._nodes.values()]

    # ---------- liveness (PAIR anti-flap + activity vouching) ----------
    def vouch_inference(self, node_id):
        """A dispatch just got response bytes from this node - strongest liveness
        signal. Resets both the probe streak and the scan miss streak."""
        with self._lock:
            n = self._nodes.get(node_id)
            if n:
                n.last_infer_ts = time.time()
                n.probe_streak = 0
                n.miss_streak = 0
                self._save()

    def record_probe(self, node_id, alive: bool):
        """Called by scan/enrich cycles. A node must miss MISS_THRESHOLD scans
        AND have no vouch signals within their windows before eviction."""
        with self._lock:
            n = self._nodes.get(node_id)
            if n is None:
                return
            now = time.time()
            if not alive:
                n.probe_streak += 1
                n.miss_streak += 1
                # PAIR activity vouch: fresh enrichment or inference bytes reset
                if (now - n.last_infer_ts) < VOUCH_INFER_SECONDS or \
                   (now - n.last_enrich_ts) < VOUCH_ENRICH_SECONDS:
                    n.miss_streak = 0
                    n.probe_streak = 0
                    return
                if n.miss_streak >= MISS_THRESHOLD:
                    del self._nodes[node_id]
            else:
                n.probe_streak = 0
                n.miss_streak = 0
                n.last_enrich_ts = now
            self._save()

    def record_all_lost(self):
        """A scan where EVERY known node missed = our own fault (multicast starved
        by local inference load). Suppress penalization for SUPPRESS_SCANS scans
        (PAIR rule: independent machines don't vanish in the same 5s window)."""
        with self._lock:
            self._global_miss_streak += 1
            if self._global_miss_streak <= SUPPRESS_SCANS:
                for n in self._nodes.values():
                    n.miss_streak = 0
                    n.probe_streak = 0
            self._save()

    def reset_global_miss(self):
        with self._lock:
            self._global_miss_streak = 0
            self._save()

    # ---------- integration ----------
    def as_providers(self) -> list[dict]:
        """Fleet nodes in provider-grid shape with provenance 'local-fleet'."""
        return [{"name": f"fleet-{n.node_id}", "kind": n.kind, "host": n.host,
                 "port": n.port, "models": n.models, "provenance": "local-fleet",
                 "lane": "LOCAL", "enabled": True}
                for n in self._nodes.values()]


# ---------- zeroconf browse (optional at import; graceful without the dep) ----------
def browse_once(seconds=3.0, fleet=None, logger=None):
    """Browse SERVICE_TYPE for `seconds`, upsert each found Ollama into `fleet`.
    Returns the fleet list. zeroconf is an optional dependency; without it the
    J5 TCP sweep (discover.py) remains the discovery path."""
    try:
        from zeroconf import Zeroconf, ServiceBrowser
    except ImportError:
        return {"ok": False, "reason": "zeroconf not installed (pip install zeroconf) - falling back to TCP sweep"}
    fleet = fleet or Fleet()
    found = []

    class _L:
        def add_service(self, zc, type_, name):
            try:
                info = zc.get_service_info(type_, name, timeout=2500)
                if info and info.parsed_addresses():
                    host = info.parsed_addresses()[0]
                    port = info.port or 11434
                    props = {k.decode(): v.decode() for k, v in (info.properties or {}).items()}
                    found.append({"node_id": props.get("uuid") or name,
                                  "host": host, "port": port,
                                  "kind": props.get("kind", "ollama"),
                                  "models": []})
            except Exception:
                pass

        def update_service(self, zc, type_, name):
            pass

        def remove_service(self, zc, type_, name):
            pass

    zc = Zeroconf()
    try:
        ServiceBrowser(zc, SERVICE_TYPE, _L())
        time.sleep(seconds)
    finally:
        zc.close()
    for f in found:
        fleet.upsert(f["node_id"], f["host"], f["port"], f["kind"], f["models"])
    return {"ok": True, "found": found}