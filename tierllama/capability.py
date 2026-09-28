"""J14 task 2+3: capability ledger + gradual bump rule.

Ledger: per (model@host, difficulty, timing, when) = model@host x prompt-class
rolling stats — failure_rate, avg_latency_s, sample_count. Prompt-class is
keyed by CLASSIFIER DIMENSIONS ONLY (spec: no embeddings, stdlib tuple;
J14 v2 may cluster). Events: logs/capability.jsonl; rolling window per key.

Bump rule (J15 collision guards honored — spec):
- bump_after_failures consecutive failures on the class -> tier += 1
  FOR THAT CLASS ONLY (never global)
- cooldown_h between class moves; max_moves_per_day per class
- min_samples before any move; gate OFF = dry-run (computes, never routes)
- Bump events are recorded regardless of gate so the UI can show what
  WOULD have happened (transparency) — routing change only when enabled.

Feeds bench.py (read side). Attribution: ledger concept is Tierllama's own;
failure-handling prior art: NVIDIA Personal-AI-Router, Apache-2.0.
"""
import json, datetime
from pathlib import Path
from . import config

CAP = lambda: config.CAPABILITY

ROOT = Path(__file__).parent.parent
CAP_LOG = ROOT / "logs" / "capability.jsonl"

# difficulty tier ladder for bumping (J14 spec: gradual, 1 step at a time)
DIFFICULTY_ORDER = ["EASY", "MEDIUM", "HARD", "EXPERT"]

def class_key(model_host: str, difficulty: str, timing: str, when: str | None) -> str:
    """Ledger key: model@host x classifier dimensions (prompt-class)."""
    return f"{model_host}|{difficulty}|{timing}|{when or 'NOW'}"

def _class_from_key(key: str) -> tuple:
    parts = key.split("|")
    return parts[0], parts[1], parts[2], parts[3]

class Ledger:
    """In-memory rolling window over the JSONL event log."""

    def __init__(self, path: Path | None = None):
        self.path = path or CAP_LOG
        self.events: dict[str, list] = {}   # key -> [event, ...] (oldest first)

    def load(self):
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                continue
            try:
                self.record(json.loads(line), persist=False)
            except Exception:
                continue

    def record(self, event: dict, persist: bool = True):
        """Add an outcome event: {bench_key, difficulty, timing, when,
        outcome, latency_s, ts}. outcome in {success, failure, unknown}."""
        key = self.key_for(event)
        window = CAP()["window_n"]
        lst = self.events.setdefault(key, [])
        lst.append(event)
        if len(lst) > window:
            del lst[:len(lst) - window]
        if persist:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def key_for(self, event: dict) -> str:
        return class_key(event.get("bench_key", ""), event.get("difficulty", ""),
                         event.get("timing", ""), event.get("when"))

    def stats(self, key: str) -> dict:
        evs = self.events.get(key, [])
        n = len(evs)
        failures = sum(1 for e in evs if e.get("outcome") == "failure")
        lats = [e.get("latency_s") for e in evs if isinstance(e.get("latency_s"), (int, float))]
        return {"samples": n, "failures": failures,
                "failure_rate": round(failures / n, 3) if n else 0.0,
                "avg_latency_s": round(sum(lats) / len(lats), 3) if lats else None}

    def consecutive_failures(self, key: str) -> int:
        n = 0
        for e in reversed(self.events.get(key, [])):
            if e.get("outcome") == "failure":
                n += 1
            elif e.get("outcome") == "success":
                break        # streak broken by success
            # unknown events don't break the streak but don't extend it
        return n

class BumpState:
    """Tracks class tier moves (the +1/+2 ladder position per class). Persisted
    so cooldowns survive restarts. Stored in logs/capability_state.json."""

    def __init__(self, path: Path | None = None):
        self.path = path or (ROOT := Path(__file__).parent.parent) / "logs" / "capability_state.json"
        self.state: dict = {}
        if self.path.exists():
            try:
                self.state = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.state = {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=1), encoding="utf-8")

    def bump_level(self, key: str) -> int:
        return self.state.get(key, {}).get("bump_level", 0)

    def last_move(self, key: str) -> dict | None:
        return self.state.get(key, {}).get("last_move")

    def moves_today(self, key: str, now) -> int:
        mv = self.last_move(key)
        if not mv:
            return 0
        return 1 if mv.get("at", "").startswith(now.strftime("%Y-%m-%d")) else 0

    def apply_bump(self, key: str, from_tier: str, to_tier: str, reason: str, now) -> dict:
        lvl = self.bump_level(key)
        self.state[key] = {"bump_level": lvl + 1, "from_tier": from_tier, "to_tier": to_tier,
                           "last_move": {"at": now.isoformat(timespec="seconds"),
                                         "from": from_tier, "to": to_tier, "reason": reason}}
        self._save()
        return self.state[key]

    def can_move(self, key: str, now) -> tuple[bool, str]:
        c = CAP()
        if self.moves_today(key, now) >= c["max_moves_per_day"]:
            return False, "rate limit: max 1 tier move per class per day (J15 guard)"
        mv = self.last_move(key)
        if mv:
            import datetime as dt
            last = datetime.datetime.fromisoformat(mv["at"])
            if (now - last) < datetime.timedelta(hours=c["cooldown_h"]):
                return False, f"cooldown: last move {mv['at']} < {c['cooldown_h']}h ago (J15 guard)"
        return True, "ok"

def bump_tier(tier: str, bump_level: int) -> str:
    """Move a difficulty tier up by bump_level steps, capped at EXPERT."""
    if tier not in DIFFICULTY_ORDER:
        return tier
    i = min(DIFFICULTY_ORDER.index(tier) + max(0, bump_level), len(DIFFICULTY_ORDER) - 1)
    return DIFFICULTY_ORDER[i]


def load_recent_bumps(limit: int = 20) -> list:
    """Recent class tier moves from BumpState files - for the UI report.
    Transparency: moves exist in state only after apply_bump (performed by the
    caller only when the gate is ON)."""
    state_path = Path(__file__).parent.parent / "logs" / "capability_state.json"
    if not state_path.exists():
        return []
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = []
    for key, st in state.items():
        mv = st.get("last_move")
        if mv:
            rows.append({"class": key, "at": mv.get("at"), "from": mv.get("from"),
                         "to": mv.get("to"), "reason": mv.get("reason"),
                         "bump_level": st.get("bump_level", 0)})
    rows.sort(key=lambda r: r.get("at") or "", reverse=True)
    return rows[:limit]

def evaluate_bump(ledger: "Ledger" = None, state: "BumpState" = None, bench_key: str = "",
                  difficulty: str = "", timing: str = "", when: str = "",
                  current_tier: str | None = None, now=None) -> dict:
    """The gradual bump rule (dry-run safe: returns a DECISION; the caller
    applies it to routing ONLY if CAPABILITY.enabled — gate checked by caller,
    never here, so the math is testable while OFF)."""
    import datetime as dt
    L = ledger or Ledger()
    S = state or BumpState()
    now = now or dt.datetime.now()
    key = class_key(bench_key, difficulty, timing, when)
    st = L.stats(key)
    decision = {"key": key, "would_bump": False, "reason": "", "from_tier": current_tier,
                "to_tier": current_tier, "stats": st}
    c = CAP()
    if st["samples"] < c["min_samples"]:
        decision["reason"] = f"min_samples: {st['samples']} < {c['min_samples']}"
        return decision
    streak = L.consecutive_failures(key)
    if streak < c["bump_after_failures"]:
        decision["reason"] = f"streak {streak} < {c['bump_after_failures']}"
        return decision
    ok, guard = S.can_move(key, now)
    if not ok:
        decision["reason"] = guard
        return decision
    base = current_tier or difficulty
    decision["would_bump"] = True
    decision["from_tier"] = base
    decision["to_tier"] = bump_tier(base, 1)
    decision["reason"] = f"{streak} consecutive failures on class (rate {st['failure_rate']})"
    return decision