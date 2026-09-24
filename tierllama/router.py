"""Tierllama router core: message in -> classify -> lane -> dispatch/escalate -> log."""
import json, re, time, datetime
from pathlib import Path
from .classifier import classify
from .config import lane_for
from .adapters import dispatch
from .ladder import escalate

LOG = Path(__file__).parent.parent / "logs" / "decisions.jsonl"


def _resolve_due(phrase):
    """J13: dumb date resolution (NO LLM). Returns ISO due_at or None.
    Regex against current date; ambiguity -> None (caller asks, never guesses)."""
    if not phrase:
        return None
    now = datetime.datetime.now()
    p = (phrase or "").lower().strip()
    m = re.search(r'\b(mon|tues|wednes|thurs|fri|satur|sun)(?:day)?\b', p)
    if m:
        names = {"mon":0,"tues":1,"wednes":2,"thurs":3,"fri":4,"satur":5,"sun":6}
        wd = now.weekday()
        delta = (names[m.group(1)] - wd) % 7 or 7
        hour, minute = 17, 0  # default: 5pm on the named day
        mt = re.search(r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', p)
        if mt and (mt.group(3) or ":" in (mt.group(0) or "")):
            hour = int(mt.group(1)) % 12 + (12 if mt.group(3) == "pm" else 0)
            minute = int(mt.group(2) or 0)
        due = (now + datetime.timedelta(days=delta)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        return due.isoformat(timespec="seconds")
    m = re.search(r'\b(\d{1,2}):(\d{2})\b', p)
    if m and ("am" in p or "pm" in p or ":" in p):
        hh = int(m.group(1)) + (12 if "pm" in p and int(m.group(1)) < 12 else 0)
        return now.replace(hour=min(hh,23), minute=int(m.group(2)), second=0, microsecond=0).isoformat(timespec="seconds")
    if "tonight" in p or "overnight" in p:
        return (now + datetime.timedelta(hours=8)).isoformat(timespec="seconds")
    return None

def _load_tree():
    """routing.json reader - handles both {tiers:{...}} and legacy flat shape."""
    p = Path(__file__).parent.parent / "routing.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("tiers", data) if isinstance(data, dict) else {}
    except Exception:
        return {}

def _tree_lookup(difficulty, timing):
    """J7: user-customizable decision tree from routing.json (hot-reloaded per call)."""
    tiers = _load_tree()
    return tiers.get(f"{difficulty}/{timing}") or tiers.get(f"{difficulty}/NOW")

def route(message, dispatch=True, last_exchanges=None):
    c = classify(message, last_exchanges)
    conf = min(c["difficulty_conf"], c["timing_conf"])
    when = c.get("when", "NOW")
    when_conf = c.get("when_conf", 1.0)
    when_raw = c.get("when_raw", "")
    lane = lane_for(c["difficulty"], c["timing"], conf, when=when, when_conf=when_conf)
    record = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "message": message,
        "difficulty": c["difficulty"], "difficulty_conf": c["difficulty_conf"],
        "timing": c["timing"], "timing_conf": c["timing_conf"],
        "when": when, "when_conf": when_conf, "when_raw": when_raw,
        "confidence": round(conf, 2),
        "lane": lane,
        "dispatched": False,
        "classifier_latency_s": c["latency_s"],
    }
    # J13: scheduler handles DEADLINE/DEFERRED-with-date jobs when beta enabled.
    if lane != "FALLBACK" and dispatch and when in ("DEADLINE",) and when_conf >= 0.85:
        from . import scheduler as _sched
        from .config import SCHEDULER as _S
        if _S.get("enabled"):
            due = _resolve_due(when_raw)
            if due:
                job = _sched.enqueue(message, lane, due, title=message[:40])
                record["scheduled"] = {"job_id": job["id"], "due_at": due}
                LOG.parent.mkdir(exist_ok=True)
                LOG.open("a", encoding="utf-8").write(json.dumps(record, ensure_ascii=False) + "\n")
                return record
            else:
                record["needs_clarification"] = {"field": "when", "raw": when_raw, "reason": "date parse failed"}
        else:
            record["needs_clarification"] = {"field": "when", "raw": when_raw, "reason": "scheduler beta disabled"}
    elif lane != "FALLBACK" and when == "DATE_UNCLEAR" and when_raw:
        record["needs_clarification"] = {"field": "when", "raw": when_raw, "guess": _resolve_due(when_raw)}
    # J7: consult the user-editable decision tree (routing.json) - tier key
    # difficulty/timing maps to (provider, model, thinking). Falls back to LANES.
    target = _tree_lookup(c["difficulty"], c["timing"])
    if dispatch:
        from .adapters import dispatch as _dispatch
        kw = {}
        if target:
            kw["model"] = target["model"]
            kw["thinking"] = target.get("thinking", "normal")
        res = _dispatch(lane, message, **kw)
        record["dispatch"] = res
        record["dispatched"] = res.get("status") in ("ok", "queued")
        if not record["dispatched"] and lane != "FALLBACK":
            res, final_lane = escalate(record, message, lane)
            record["lane"] = final_lane
            record["escalated"] = True
            record["final_dispatch"] = res
            record["dispatched"] = res.get("status") in ("ok", "queued")
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record
