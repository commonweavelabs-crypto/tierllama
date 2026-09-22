"""Tierllama OpenAI-compatible proxy (J7 dogfood): Hermes (or any OpenAI client)
points at this endpoint; every request is classified and routed to the lane the
decision tree picks. One provider in config = all lanes behind it.

Run:  python cli.py serve-proxy      (default :8846, /v1/chat/completions)
"""
import json, time, datetime, urllib.request
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from .router import route
from .adapters import dispatch

app = FastAPI(title="Tierllama proxy", docs_url=None, redoc_url=None)
ROOT = Path(__file__).parent.parent
PROXY_LOG = ROOT / "logs" / "proxy.jsonl"

class Msg(BaseModel):
    role: str
    content: str

class ChatReq(BaseModel):
    model: str = "tierllama-auto"
    messages: list[Msg]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None

def _upstream(lane_model: str, messages, stream, temperature, max_tokens, timeout=180):
    """Forward to local Ollama. Native /api/chat with think:False (J7 dogfood fix:
    qwen3-class thinking mode eats the whole token budget -> empty content).
    Wraps the Ollama response in OpenAI-compatible shape for the caller."""
    body = {"model": lane_model, "messages": messages, "stream": False, "think": False}
    # qwen3-class models ignore the think flag over /api/chat; /no_think system
    # prompt is the soft-switch that works (J7 dogfood finding):
    body["messages"] = [{"role": "system", "content": "/no_think"}] + messages
    if temperature is not None or max_tokens:
        opts = {}
        if temperature is not None: opts["temperature"] = temperature
        if max_tokens: opts["num_predict"] = max_tokens
        body["options"] = opts
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    text = r.get("message", {}).get("content", "")
    return {"id": "tierllama", "object": "chat.completion", "model": lane_model,
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": text}}],
            "usage": {"prompt_tokens": r.get("prompt_eval_count", 0),
                      "completion_tokens": r.get("eval_count", 0)}}

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

@app.post("/v1/chat/completions")
def chat(req: ChatReq):
    # Classify the LAST user message (the prompt):
    prompt = next((m.content for m in reversed(req.messages) if m.role == "user"), "")[:4096]
    decision = route(prompt, dispatch=False)
    tier_key = f"{decision['difficulty']}/{decision['timing']}"
    tree = _load_tree()
    target = tree.get(tier_key) or tree.get(f"{decision['difficulty']}/NOW") or {}
    lane = decision["lane"]
    model = target.get("model") if target else None
    # v1 dogfood guardrail: LOCAL lanes only (models present on this machine):
    tags = json.loads(urllib.request.urlopen(
        "http://127.0.0.1:11434/api/tags", timeout=5).read())["models"]
    local_models = {m["name"] for m in tags}
    if not model or not any(model == m or m.startswith(model) for m in local_models):
        model = "glm-5.3-flash:cloud" if "glm-5.3-flash:cloud" in local_models else sorted(local_models)[0]
        lane = "LOCAL-FALLBACK"
    rec = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
           "role": decision["role"], "difficulty": decision["difficulty"],
           "timing": decision["timing"], "lane": lane, "model": model,
           "confidence": decision["confidence"],
           "classifier_latency_s": decision["classifier_latency_s"],
           "messages_n": len(req.messages)}
    t0 = time.time()
    try:
        out = _upstream(model, [m.model_dump() for m in req.messages], req.stream,
                        req.temperature, req.max_tokens)
        rec["status"] = "ok"; rec["latency_s"] = round(time.time()-t0, 2)
    except Exception as e:
        rec["status"] = "error"; rec["error"] = str(e)[:150]
        rec["latency_s"] = round(time.time()-t0, 2)
        out = {"error": rec["error"]}
    with PROXY_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    if rec["status"] == "error":
        return JSONResponse(out, status_code=502)
    return JSONResponse(out)

@app.get("/v1/models")
def models():
    r = json.loads(urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5).read())
    return {"object": "list", "data": [{"id": m["name"], "object": "model"} for m in r["models"]]}
