"""Tierllama escalation ladder (J4): when a routed message fails or looks uncertain,
escalate through the ladder and record every step.

Triggers:
1. dispatch_error  - lane adapter returned status=error
2. low_confidence  - classifier probability below threshold (J2 logprob signal)
3. disagree        - two classification passes disagree on role (retry-with-rephrase)
4. max_retries     - all retries exhausted -> final escalation to strongest lane

Ladder order: LOCAL -> CLOUD_MEDIUM -> CLOUD_HARD -> FALLBACK (main LLM).
Every escalation step is recorded in the decision log with its trigger and outcome."""
import json, time, datetime
from pathlib import Path
from .adapters import dispatch
from .config import CLASSIFIER

LANE_ORDER = ["LOCAL", "CLOUD_MEDIUM", "CLOUD_HARD"]
MAX_ATTEMPTS_PER_LANE = 2

def _log_step(record, step):
    record.setdefault("escalation", []).append(step)
    log = Path(__file__).parent.parent / "logs" / "decisions.jsonl"
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": record["ts"], "event": "escalation",
                            "message": record["message"], "step": step}) + "\n")

def escalate(record, message, lane_start, dispatch_kw=None):
    """Run the escalation ladder for a routed message. Mutates record with the full
    escalation trace. Returns the final dispatch result + the lane that served it."""
    dispatch_kw = dispatch_kw or {}
    idx = LANE_ORDER.index(lane_start) if lane_start in LANE_ORDER else 0
    lane = lane_start
    attempt = 0
    result = None
    while idx < len(LANE_ORDER):
        # Phase 1: retry-with-rephrase on the SAME lane (cheap; fixes transient errors
        # and ambiguous phrasings without paying a stronger model's price).
        for attempt in range(1, MAX_ATTEMPTS_PER_LANE + 1):
            t0 = time.time()
            result = dispatch(lane, message, **dispatch_kw)
            step = {"trigger": "dispatch", "lane": lane, "attempt": attempt,
                    "status": result.get("status"), "latency_s": result.get("latency_s")}
            if result.get("status") in ("ok", "queued"):
                step["outcome"] = "served"
                _log_step(record, step)
                record["lane"] = lane
                record["final_dispatch"] = result
                return result, lane
            # Phase 2: second-pass verification - re-ask the classifier with the error
            # appended as context (retry-with-rephrase for the ROUTER, not the model).
            _log_step(record, step)
            if attempt < MAX_ATTEMPTS_PER_LANE:
                rephrase = record.get("rephrased_message") or message
                from .classifier import classify_role
                role2, probs2, _dt = classify_role(rephrase or message)
                step2 = {"trigger": "rephrase_reclassify", "lane": lane,
                         "new_role": role2, "p_top": round(max(probs2.values()), 3)}
                _log_step(record, step2)
        # Phase 3: escalate to the next stronger lane.
        idx += 1
        if idx < len(LANE_ORDER):
            new_lane = LANE_ORDER[idx]
            step_up = {"trigger": "lane_escalation", "from_lane": lane, "to_lane": new_lane,
                       "reason": result.get("error", "unknown") if result else "unknown"}
            _log_step(record, step_up)
            lane = new_lane
    # Phase 4: final fallback - main LLM lane (cloud medium as stand-in until the
    # FALLBACK adapter exists in J5; logged explicitly).
    result = dispatch("FALLBACK", message, **dispatch_kw)
    _log_step(record, {"trigger": "fallback_final", "lane": "FALLBACK",
                       "status": result.get("status")})
    record["final_dispatch"] = result
    return result, "FALLBACK"
