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

def lane_for(difficulty, timing, confidence, threshold=None):
    """Route a classified message to a lane. Ambiguous/low-confidence -> FALLBACK."""
    threshold = threshold if threshold is not None else CLASSIFIER["confidence_threshold"]
    if confidence < threshold:
        return "FALLBACK"
    if timing == "LATER" and difficulty != "HARD":
        return "BOX"
    return DIFFICULTY_TO_LANE.get(difficulty, "CLOUD_MEDIUM")
