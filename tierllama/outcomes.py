"""J14 task 1: outcome signals — dispatch records task success/failure.

MVP truth sources ONLY (spec; no semantic judging — that's J14 v2/telemetry):
- failure (automatic): HTTP error, empty content, adapter exception
- failure (user): explicit retry-within-session of the same message
- success (automatic): dispatch ok + non-empty content AND no user retry followed
- unknown: anything else (never guessed)

Adapted from NVIDIA Personal-AI-Router, Apache-2.0 (job-scheduler outcome
tracking); the outcome taxonomy is Tierllama's own per the J14 spec.
"""
import json, time, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTCOME_LOG = ROOT / "logs" / "outcomes.jsonl"

# in-session retry tracking: message-key -> count (per process; webapp session)
_retry_counts: dict[str, int] = {}

def message_key(message: str) -> str:
    """Stable key for retry detection (normalized whitespace, lowercase)."""
    return " ".join((message or "").split()).lower()

def _hash_key(key: str) -> str:
    """Privacy (J6 decision-log rule): msg keys are hashed, never stored raw."""
    import hashlib
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

def note_dispatch_result(record: dict, dispatch_res: dict) -> str:
    """Classify + record the outcome of one dispatch. Returns the outcome.
    Mutates `record` by adding record['outcome'] (and appends to outcomes log)."""
    outcome = classify_result(dispatch_res)
    record["outcome"] = outcome
    _append(record, dispatch_res, outcome)
    return outcome

def classify_result(dispatch_res: dict) -> str:
    status = (dispatch_res or {}).get("status")
    if status in ("error", "failed"):
        return "failure"
    result = (dispatch_res or {}).get("result")
    if status == "ok" and isinstance(result, str) and result.strip():
        return "success"
    if status == "queued":   # BOX async: no result yet; not judged
        return "unknown"
    return "failure"

def note_user_retry(message: str) -> str:
    """The user re-sent the same message in-session: failure signal (spec).
    Marks any prior 'success' for this key as failure-reason=user_retry."""
    key = message_key(message)
    _retry_counts[key] = _retry_counts.get(key, 0) + 1
    return key

def is_retried(message: str) -> bool:
    return _retry_counts.get(message_key(message), 0) > 0

def _append(record: dict, dispatch_res: dict, outcome: str):
    try:
        OUTCOME_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "outcome": outcome,
            "lane": record.get("lane"),
            "model": (dispatch_res or {}).get("model"),
            "difficulty": record.get("difficulty"),
            "timing": record.get("timing"),
            "when": record.get("when"),
            "latency_s": (dispatch_res or {}).get("latency_s"),
            "reason": (dispatch_res or {}).get("error") or ("user_retry" if is_retried(record.get("message", "")) else ""),
            "msg_key_hash": _hash_key(message_key(record.get("message", ""))),  # privacy: hashed, never raw content
        }
        with OUTCOME_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # outcome logging must never break routing

def summary(keys: list[str] | None = None) -> dict:
    """Aggregate outcome counts from the log (optionally filtered by msg_key hash)."""
    if not OUTCOME_LOG.exists():
        return {}
    hashed = {_hash_key(message_key(k)) for k in (keys or [])}
    counts: dict[str, int] = {"success": 0, "failure": 0, "unknown": 0}
    with OUTCOME_LOG.open(encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if keys and d.get("msg_key_hash") not in hashed:
                continue
            counts[d["outcome"]] = counts.get(d["outcome"], 0) + 1
    return counts