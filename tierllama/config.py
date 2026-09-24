"""Tierllama config: lanes, models, machines. Edit here; no YAML yet (MVP)."""
LANES = {
    "LOCAL":  {"models": ["qwen3:4b", "ornith-1.5:9b"], "cost_per_mtok": 0.0},
    "CLOUD_MEDIUM": {"models": ["glm-5.3-flash:cloud"], "cost_in": 0.15, "cost_out": 0.60},
    "CLOUD_HARD":   {"models": ["kimi-k3"], "cost_in": 3.00, "cost_out": 15.00},
    "BOX":    {"models": ["qwen38-27b-iq3s"], "cost_per_mtok": 0.0, "note": "overnight async"},
}

CLASSIFIER = {
    "model": "qwen3:4b",
    "endpoint": "http://127.0.0.1:11434/api/chat",
    "v1_endpoint": "http://127.0.0.1:11434/v1/chat/completions",
    "temperature": 0,
    "confidence_threshold": 0.75,   # below -> FALLBACK lane (main LLM decides)
}

DIFFICULTY_TO_LANE = {
    "EASY": "LOCAL", "MEDIUM": "CLOUD_MEDIUM", "HARD": "CLOUD_HARD", "LATER": "BOX",
}

# --- J13 scheduler (BETA: off by default; user must knowingly opt in) ---
WHEN_VALUES = ["NOW", "DEADLINE", "DEFERRED", "DATE_UNCLEAR"]

SCHEDULER = {
    "enabled": False,      # BETA feature gate - never enable silently (Gui policy)
    "beta": True,
    "when_conf_threshold": 0.85,   # below -> needs_clarification (never guess a date)
    "queue_path": None,            # default: ROOT/logs/schedule.json (set by scheduler.py)
    "due_loop_s": 30,
    "max_tries": 3,
    "long_horizon_min": 90,        # > this many minutes -> long-job clarify gate
    "shove_cap_week": 3,
    "night_window": {"start": "00:00", "end": "08:00"},  # user-adjustable
}

def lane_for(difficulty, timing, confidence, threshold=None, when=None, when_conf=None):
    """Route a classified message to a lane. Ambiguous/low-confidence -> FALLBACK.
    J13: when=None reproduces the pre-J13 behavior exactly (golden set safe).
    when=DEADLINE -> same lane as timing picks, but caller enters the job in the
    scheduler with a due_at instead of dispatching immediately (router handles)."""
    threshold = threshold if threshold is not None else CLASSIFIER["confidence_threshold"]
    if confidence < threshold:
        return "FALLBACK"
    if when == "DEADLINE" and when_conf is not None and when_conf < SCHEDULER["when_conf_threshold"]:
        return "FALLBACK"
    if timing == "LATER" and difficulty != "HARD":
        return "BOX"
    return DIFFICULTY_TO_LANE.get(difficulty, "CLOUD_MEDIUM")
