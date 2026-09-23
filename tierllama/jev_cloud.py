"""Jev Cloud adapter (TypeSafe AI): native /v1/systemone protocol.
The cloud fallback for the ROUTER ITSELF - for users without hardware to run
the local qwen3:4b classifier. Output tokens are free; input $0.042/Mtok
(~$0.00002/decision at ~400 input tokens). This is a tribute provider: Jev
(Diogo Almeida, ex-OpenAI) is the model family our router is named after.
Protocol: POST /v1/systemone {model, state, questions:{...}} ->
  {answer: {choice|noul|score, probabilities, confidence}}
NOT OpenAI-compatible - dedicated adapter, like the box lane.
"""
import json, os, time, urllib.request, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
KEYS_FILE = ROOT / ".tierllama_keys.env"
COST_LOG = ROOT / "logs" / "costs.jsonl"
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"

def _key():
    env = "TYPESAFE_API_KEY"
    if os.environ.get(env):
        return os.environ[env]
    if KEYS_FILE.exists():
        for line in KEYS_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith(env + "="):
                return line.partition("=")[2].strip()
    return None

def classify_cloud(message: str, rubric_hint: str = ""):
    """Route decision via Jev Cloud. Returns the same shape as our local
    classifier: {role, difficulty, timing, confidence, lane_source:'jev-cloud'}.
    Falls back to None if no key configured (caller keeps local classifier)."""
    key = _key()
    if not key:
        return None
    body = {
        "model": MODEL,
        "state": message[:4000],
        "questions": {
            "difficulty": {"type": "choice",
                            "instructions": "How hard is this for an AI to do well?",
                            "criteria": {"EASY": "trivial lookup or single-step action",
                                          "MEDIUM": "routine multi-step work",
                                          "HARD": "deep reasoning or complex creation",
                                          "EXPERT": "frontier-level reasoning"}},
            "timing": {"type": "choice",
                        "instructions": "Does this need an answer NOW or can it wait?",
                        "criteria": {"NOW": "user is waiting for this",
                                      "LATER": "batch/overnight work acceptable"}},
        },
    }
    t0 = time.time()
    try:
        req = urllib.request.Request(ENDPOINT,
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        r = json.loads(urllib.request.urlopen(req, timeout=15).read())
        diff = r.get("difficulty", {}).get("choice", "MEDIUM")
        timing = r.get("timing", {}).get("choice", "NOW")
        conf = r.get("difficulty", {}).get("confidence", 0.0)
        in_tok = r.get("usage", {}).get("input_tokens", 400)
        cost = in_tok * 0.042 / 1e6  # output tokens are free
        COST_LOG.parent.mkdir(exist_ok=True)
        COST_LOG.open("a", encoding="utf-8").write(json.dumps({
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "provider": "jev", "model": MODEL, "in_tokens": in_tok,
            "out_tokens": 0, "cost_usd": round(cost, 8)}) + "\n")
        return {"difficulty": diff, "timing": timing,
                "confidence": conf, "latency_s": round(time.time() - t0, 3),
                "source": "jev-cloud"}
    except Exception as e:
        return {"error": str(e)[:150]}

def status():
    """For the featured Providers card: is Jev Cloud configured?"""
    k = _key()
    return {"configured": bool(k), "endpoint": ENDPOINT, "model": MODEL,
            "price": "$0.042/Mtok input, output free (~$0.00002/decision)"}
