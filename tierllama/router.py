"""Tierllama router core: message in -> classify -> lane -> dispatch/escalate -> log."""
import json, time, datetime
from pathlib import Path
from .classifier import classify
from .config import lane_for
from .adapters import dispatch
from .ladder import escalate

LOG = Path(__file__).parent.parent / "logs" / "decisions.jsonl"


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
    lane = lane_for(c["difficulty"], c["timing"], conf)
    record = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "message": message,
        "difficulty": c["difficulty"], "difficulty_conf": c["difficulty_conf"],
        "timing": c["timing"], "timing_conf": c["timing_conf"],
        "confidence": round(conf, 2),
        "lane": lane,
        "dispatched": False,
        "classifier_latency_s": c["latency_s"],
    }
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
