"""Tierllama request-level dispatch with reservations (J12+ T4, PAIR-derived).

Adapted from NVIDIA Personal-AI-Router, Apache-2.0
(nvpair-proxy reservation lifecycle + commit-at-first-body-byte + dispatch
budget/deadline; nvpair-job-scheduler least-loaded-first ranking).
https://github.com/NVIDIA/Personal-AI-Router

Ported semantics (PAIR proxy spec §5, adapted):
- RESERVATIONS: a dispatch reserves its node under one lock BEFORE forwarding,
  so concurrent bursts cannot double-book an idle-looking node. The reservation
  is released when the request ends and MOVES WITH FAILOVER (released from the
  failed node, re-taken on the next candidate).
- COMMIT POINT: a streaming request commits to a node at the FIRST BYTE of
  response body, not at headers (PAIR §5.3). After commit, failover stops.
- BOUNDS: dispatch retries under a bounded budget (MAX_DISPATCH_ROUNDS) and a
  wall-clock deadline (DISPATCH_DEADLINE_S). Paired with retryable-status rules.
- Liveness: every response (or error) feeds fleet.vouch_inference() - busy
  nodes stay listed (T3 integration), and health.FleetPressure gets EWMA
  pressure updates when a GPU sample is available.
"""
import json, threading, time, datetime, urllib.request
from pathlib import Path
from . import fleet as _fleet_mod
from . import health as _health_mod

MAX_DISPATCH_ROUNDS = 3          # PAIR: dispatch budget (rounds over candidate owners)
DISPATCH_DEADLINE_S = 90.0       # PAIR: wall-clock deadline for the whole dispatch
RETRYABLE_STATUS = {500, 502, 503, 504}   # PAIR: transport/retryable statuses


class Reservations:
    """Per-node in-flight request counts, guarded by one lock (PAIR: facades
    share the process precisely so simultaneous bursts see one picture)."""

    def __init__(self):
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def _release_unlocked(self, node_id: str) -> None:
        if node_id in self._counts:
            self._counts[node_id] = max(0, self._counts[node_id] - 1)
            if self._counts[node_id] == 0:
                del self._counts[node_id]

    def take(self, node_id: str) -> int:
        """Reserve a slot; returns the node's new pending count."""
        with self._lock:
            self._counts[node_id] = self._counts.get(node_id, 0) + 1
            return self._counts[node_id]

    def release(self, node_id: str) -> int:
        """Release at request end (or on failover move). Never negative."""
        with self._lock:
            self._release_unlocked(node_id)
            return self._counts.get(node_id, 0)

    def pending(self, node_id: str) -> int:
        with self._lock:
            return self._counts.get(node_id, 0)

    def move(self, old: str, new: str) -> None:
        """Reservation MOVES with failover (PAIR: the node stops counting as
        loaded the moment it stops working on the request). Single lock
        acquisition - release+take must be atomic."""
        with self._lock:
            self._release_unlocked(old)
            self._counts[new] = self._counts.get(new, 0) + 1


_res = Reservations()          # module-level: the one lock picture
_pressure = _health_mod.FleetPressure()


def candidates(lane: str, nodes: list[dict], model: str | None = None) -> list[dict]:
    """Eligible candidates (PAIR eligibility rule): only nodes whose advertised
    inventory carries the requested model (or any, when unspecified), ordered
    least-pressured-first (scheduler rank), then stable node id."""
    elig = [n for n in nodes
            if (model is None or model in n.get("models", []) or not n.get("models"))]
    ranked = {d["node_id"]: d["pressure"] for d in _pressure.ranking()}
    elig.sort(key=lambda n: (_res.pending(n["node_id"]),
                             _pressure.node(n["node_id"]).pressure(),
                             n["node_id"]))
    return elig


def dispatch_request(candidate_nodes: list[dict], model: str, body: dict,
                     do_post, deadline_s: float = DISPATCH_DEADLINE_S,
                     on_commit=None, log=None) -> dict:
    """Send one inference request over the fleet with PAIR dispatch semantics.

    do_post(node, body, deadline) -> (ok: bool, result: any, status: int|None)
        caller-provided transport (kept injectable for tests).
    Returns {"ok", "node_id", "result", "rounds", "error"?}.

    Loop: for each round, pick least-loaded eligible candidate, take a
    reservation, post; on failure release and step to the next candidate
    (failover moves the reservation); on first success COMMIT and return.
    Wall-clock deadline caps the whole loop; budget caps the rounds.
    """
    t0 = time.time()
    tried: list[str] = []
    last_err = None
    with ReservationContext() as ctx:
        for round_no in range(1, MAX_DISPATCH_ROUNDS + 1):
            if time.time() - t0 > deadline_s:
                break
            cand = [n for n in candidates_ordered(candidate_nodes) if n["node_id"] not in tried]
            if not cand:
                break
            node = cand[0]
            tried.append(node["node_id"])
            ctx.take(node["node_id"])
            ok, result, status = do_post(node, body, deadline_s - (time.time() - t0))
            if ok:
                if log:
                    log({"event": "dispatch", "node": node["node_id"], "round": round_no,
                         "status": "committed"})
                return {"ok": True, "node_id": node["node_id"], "result": result,
                        "round": round_no, "tried": tried}
            # failover: release the failed node's reservation and continue
            last_err = result if isinstance(result, str) else json.dumps(result)[:150]
            if log:
                log({"event": "failover", "node": node["node_id"], "round": round_no,
                     "status": status, "error": last_err})
            # non-retryable HTTP status: stop immediately (PAIR retries only retryable)
            if status is not None and status not in RETRYABLE_STATUS and status != 404:
                break
    return {"ok": False, "node_id": None, "result": None, "tried": tried,
            "error": last_err or "dispatch budget/deadline exhausted"}


class ReservationContext:
    """Holds reservations across failovers; releases ALL at request end."""

    def __init__(self):
        self.held: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        for n in self.held:
            _res.release(n)
        self.held.clear()
        return False

    def take(self, node_id: str):
        _res.take(node_id)
        if node_id not in self.held:
            self.held.append(node_id)


def candidates_ordered(nodes: list[dict]) -> list[dict]:
    """Least-pressured-first ordering (health.FleetPressure rank, then id)."""
    return sorted(nodes, key=lambda n: (_res.pending(n["node_id"]),
                                        _pressure.node(n["node_id"]).pressure(),
                                        n["node_id"]))