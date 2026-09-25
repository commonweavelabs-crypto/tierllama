"""Tierllama GPU-pressure health signal (J12+ T1).

Adapted from NVIDIA Personal-AI-Router, Apache-2.0 (nvpair-job-scheduler ranking
signal): EWMA-smoothed GPU utilization banded 0-3, with asymmetric downward
thresholds to prevent rank thrash, and stale samples -> neutral pressure.
https://github.com/NVIDIA/Personal-AI-Router

Tierllama port: pure stdlib, no GPU dependency in this module (callers feed
utilization samples from any source - nvidia-smi, Ollama ps, provider polling).

Bands (PAIR-identical):
    EWMA < 40%          -> pressure 0
    40-69%              -> 1
    70-84%              -> 2
    >= 85%              -> 3
Downward transitions use the LOWER thresholds (35/65/80) - hysteresis so a
signal hovering on a boundary does not thrash the node ranking.
Stale samples (> STALE_SECONDS since last update) contribute neutral pressure 1,
matching PAIR's "invalid, missing, or older-than-10-second telemetry" rule.
"""
import threading, time

ALPHA = 0.35                 # PAIR's EWMA coefficient
STALE_SECONDS = 10.0         # PAIR: >10s old -> neutral
BAND_UP = (0.40, 0.70, 0.85)     # upward thresholds: util -> pressure
BAND_DOWN = (0.35, 0.65, 0.80)   # downward hysteresis: pressure releases earlier
NEUTRAL_PRESSURE = 1


def _band(ewma: float) -> int:
    """Plain upward mapping (PAIR pressureBand)."""
    if ewma < BAND_UP[0]:
        return 0
    if ewma < BAND_UP[1]:
        return 1
    if ewma < BAND_UP[2]:
        return 2
    return 3


def _pressure_with_hysteresis(ewma: float, previous: int) -> int:
    """PAIR pressureWithHysteresis: downward transitions need the util to fall
    past the lower band edge before pressure releases."""
    if previous <= 0:
        return _band(ewma)
    lo = (BAND_DOWN[0], BAND_DOWN[1], BAND_DOWN[2])
    if previous >= 3 and ewma < lo[2]:
        return _band(ewma)
    if previous == 2 and ewma < lo[1]:
        return _band(ewma)
    if previous == 1 and ewma < lo[0]:
        return 0
    return previous


class NodePressure:
    """Per-node GPU-pressure tracker. One instance per machine/provider."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._ewma: float | None = None   # None = no valid sample yet
        self._pressure: int = 0
        self._last_ts: float = 0.0        # time.monotonic of last valid sample

    def update(self, gpu_util: float, now: float | None = None) -> int:
        """Feed a raw GPU utilization sample (0.0-1.0 or 0-100 scale), return current pressure."""
        now = time.time() if now is None else now
        if gpu_util is None:
            return self.pressure(now)
        if gpu_util > 1.5:            # accept 0-100 style inputs
            gpu_util = gpu_util / 100.0
        gpu_util = max(0.0, min(1.0, gpu_util))
        if self._ewma is None:
            self._ewma = gpu_util     # first sample anchors the EWMA (PAIR behavior)
        else:
            self._ewma = ALPHA * gpu_util + (1 - ALPHA) * self._ewma
        self._pressure = _pressure_with_hysteresis(self._ewma, self._pressure)
        self._last_ts = now
        return self._pressure

    def pressure(self, now: float | None = None) -> int:
        """Current pressure with staleness: >10s since last sample -> neutral 1.
        Never-sample-yet nodes are also neutral (PAIR: missing data contributes 1)."""
        now = time.time() if now is None else now
        if self._ewma is None:
            return NEUTRAL_PRESSURE
        if (now - self._last_ts) > STALE_SECONDS:
            return NEUTRAL_PRESSURE
        return self._pressure


class FleetPressure:
    """All tracked nodes; ranking = sort by (pressure,) then node_id (stable)."""

    def __init__(self):
        self._nodes: dict[str, NodePressure] = {}

    def node(self, node_id: str) -> NodePressure:
        if node_id not in self._nodes:
            self._nodes[node_id] = NodePressure(node_id)
        return self._nodes[node_id]

    def feed(self, node_id: str, util: float, now: float | None = None) -> int:
        return self.node(node_id).update(util, now)

    def ranking(self, now: float | None = None) -> list[dict]:
        """Nodes sorted least-pressured-first (PAIR rank order, without pending
        counts which live in the proxy layer)."""
        now = time.time() if now is None else now
        out = [{"node_id": nid, "pressure": p.pressure(now)}
               for nid, p in self._nodes.items()]
        out.sort(key=lambda d: (d["pressure"], d["node_id"]))
        for i, d in enumerate(out):
            d["rank"] = i
        return out

    def snapshot(self, now: float | None = None) -> dict:
        """Persisted state for the decision log: {"node": {"ewma","pressure","age_s"}}."""
        now = time.time() if now is None else now
        out = {}
        for nid, p in self._nodes.items():
            stale = p._ewma is None or (now - p._last_ts) > STALE_SECONDS
            out[nid] = {"ewma": None if p._ewma is None else round(p._ewma, 4),
                        "pressure": p.pressure(now),
                        "stale": stale,
                        "age_s": None if p._last_ts == 0 else round(now - p._last_ts, 1)}
        return out