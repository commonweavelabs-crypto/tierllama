"""Tierllama router core: message in -> classify -> lane -> decision log."""
import json, time, datetime
from pathlib import Path
from .classifier import classify
from .config import lane_for

LOG = Path(__file__).parent.parent / "logs" / "decisions.jsonl"

def route(message, dispatch=False, last_exchanges=None):
    c = classify(message, last_exchanges)
    conf = min(c["role_conf"], c["difficulty_conf"], c["timing_conf"])
    lane = lane_for(c["difficulty"], c["timing"], conf)
    record = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "message": message,
        "role": c["role"], "role_conf": c["role_conf"],
        "difficulty": c["difficulty"], "difficulty_conf": c["difficulty_conf"],
        "timing": c["timing"], "timing_conf": c["timing_conf"],
        "confidence": round(conf, 2),
        "lane": lane,
        "dispatched": False,
        "classifier_latency_s": c["latency_s"],
    }
    # dispatch adapters (J3): LOCAL/CLOUD_MEDIUM/CLOUD_HARD/BOX. MVP: log-only.
    record["dispatched"] = lane in ("LOCAL",)
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record
