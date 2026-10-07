"""Tierllama OpenAI-compatible proxy (J7 dogfood): Hermes (or any OpenAI client)
points at this endpoint; every request is classified and routed to the lane the
decision tree picks. One provider in config = all lanes behind it.

Run:  python cli.py serve-proxy      (default :8846, /v1/chat/completions)
"""
import json, time, datetime, urllib.request, urllib.error
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .router import route
from .adapters import dispatch, DEFAULT_NUM_CTX
from . import dispatch as _dispatch
from . import fleet as _fleet_mod

app = FastAPI(title="Tierllama proxy", docs_url=None, redoc_url=None)
ROOT = Path(__file__).parent.parent
PROXY_LOG = ROOT / "logs" / "proxy.jsonl"
SELF_NODE_ID = "local"           # this machine in the fleet picture
SELF_HOST, SELF_PORT = "127.0.0.1", 11434

class Msg(BaseModel):
    role: str
    content: str

class ChatReq(BaseModel):
    model: str = "tierllama-auto"
    messages: list[Msg]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None

def _upstream(lane_model: str, messages, stream, temperature, max_tokens, thinking="normal", timeout=180):
    """Forward to local Ollama (which transparently proxies ':cloud' models to
    ollama.com cloud — verified live). Native /api/chat. J18 thinking fix: the
    tree's thinking level controls the think flag now — max turns it ON with
    /think, normal/off suppress it (J7 dogfood: qwen3-class thinking ate the
    token budget; /no_think system prompt is the reliable soft-switch)."""
    body = {"model": lane_model, "messages": messages, "stream": False,
            "options": {"num_ctx": DEFAULT_NUM_CTX}}
    if thinking == "max":
        body["think"] = True
        body["messages"] = [{"role": "system", "content": "/think"}] + messages
    else:
        body["think"] = False
        body["messages"] = [{"role": "system", "content": "/no_think"}] + messages
    if temperature is not None or max_tokens:
        if temperature is not None: body["options"]["temperature"] = temperature
        if max_tokens: body["options"]["num_predict"] = max_tokens
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

def _post_node(node: dict, body: dict, deadline: float):
    """Dispatch transport: one Ollama native /api/chat call against a fleet node.
    Returns (ok, result, status) per dispatch_request's contract; urllib errors
    become (False, message, None) so CONN-REFUSED/COULDNT-CONNECT failover works."""
    url = f"http://{node['host']}:{node['port']}/api/chat"
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        r = json.loads(urllib.request.urlopen(req, timeout=max(3, int(deadline))).read())
        msg = r.get("message", {})
        text = msg.get("content", "")
        # J26 Finding-3 guard: qwen3-vl-class models can burn the WHOLE budget in
        # the 'thinking' field despite think:false (measured: eval=300, content='').
        # Empty content is a FAILED generation, not a success - let dispatch
        # failover to the next node/candidate instead of serving blank text.
        if not text.strip():
            rc = r.get("eval_count", 0)
            return False, f"empty content (thinking burned {rc} tokens)", 502
        return True, {"text": text,
                      "prompt_tokens": r.get("prompt_eval_count", 0),
                      "completion_tokens": r.get("eval_count", 0)}, 200
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode(errors="replace")).get("error", "")[:150]
        except Exception:
            msg = f"HTTP {e.code}"
        return False, msg, e.code
    except Exception as e:          # URLError/timeout: transport-level failure
        return False, str(e)[:150], None


def _fleet_nodes_for(local_models: list[str]) -> list[dict]:
    """Fleet picture for THIS request: self (always) + live LAN nodes whose
    advertised models include the target model (disaptch.candidates' rule)."""
    self_node = {"node_id": SELF_NODE_ID, "host": SELF_HOST, "port": SELF_PORT,
                 "models": local_models}
    try:
        fleet = _fleet_mod.Fleet()
        lan = [n for n in fleet.list()
               if n.get("node_id") != SELF_NODE_ID and n.get("host")]
        return [self_node] + lan
    except Exception:
        return [self_node]


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
    thinking = (target.get("thinking") if target else None) or "normal"
    tree_num_predict = target.get("num_predict") if isinstance(target, dict) else None
    # J7 dogfood guardrail, J18 revision: LOCAL lanes must be models present on
    # this machine; ":cloud" models go to Ollama's CLOUD endpoint instead of
    # being silently rewritten to a random local fallback (everything-same-model bug).
    tags = json.loads(urllib.request.urlopen(
        "http://127.0.0.1:11434/api/tags", timeout=5).read())["models"]
    local_models = [m["name"] for m in tags]
    model_set = set(local_models)
    if not model:
        model = "glm-5.3-flash:cloud" if "glm-5.3-flash:cloud" in model_set else sorted(model_set)[0]
        lane = "LOCAL-FALLBACK"
    elif model.endswith(":cloud"):
        lane = "CLOUD"   # host = ollama.com cloud inference
    elif not any(model == m or m.startswith(model) for m in local_models):
        model = "glm-5.3-flash:cloud" if "glm-5.3-flash:cloud" in model_set else sorted(model_set)[0]
        lane = "LOCAL-FALLBACK"
    rec = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
           "role": decision.get("role", "UNKNOWN"),
           "difficulty": decision["difficulty"],
           "timing": decision["timing"], "lane": lane, "model": model,
           "confidence": decision["confidence"],
           "classifier_latency_s": decision["classifier_latency_s"],
           "messages_n": len(req.messages)}
    t0 = time.time()
    out = None
    if lane == "CLOUD" or model.endswith(":cloud"):
        # cloud models keep the original direct path (ollama.com via local relay)
        out = _upstream(model, [m.model_dump() for m in req.messages], req.stream,
                        req.temperature, req.max_tokens, thinking=thinking)
        rec["status"] = "ok"; rec["latency_s"] = round(time.time()-t0, 2)
        rec["node_id"] = SELF_NODE_ID
    else:
        # T4 integration (J26 consolidation): LOCAL lanes dispatch over the fleet
        # with reservations + failover (self always eligible; LAN nodes advertise).
        msgs = [m.model_dump() for m in req.messages]
        if thinking == "max":
            body = {"think": True, "messages": [{"role": "system", "content": "/think"}] + msgs}
        else:
            body = {"think": False, "messages": [{"role": "system", "content": "/no_think"}] + msgs}
        body["model"] = model
        body["stream"] = False
        body["options"] = {"num_ctx": DEFAULT_NUM_CTX}
        if req.temperature is not None: body["options"]["temperature"] = req.temperature
        # tree num_predict (J26 HARD fix): thinking models need headroom; caller's
        # explicit max_tokens wins when larger, tree floor applies otherwise
        np_opts = [n for n in (req.max_tokens, tree_num_predict) if n]
        if np_opts:
            body["options"]["num_predict"] = max(np_opts)
        nodes = _fleet_nodes_for(local_models)
        res = _dispatch.dispatch_request(nodes, model, body, _post_node,
                                         log=lambda e: rec.setdefault("dispatch_events", []).append(e))
        rec["node_id"] = res.get("node_id")
        rec["dispatch_tried"] = res.get("tried", [])
        if res["ok"]:
            r = res["result"]
            out = {"id": "tierllama", "object": "chat.completion", "model": model,
                   "choices": [{"index": 0, "finish_reason": "stop",
                                "message": {"role": "assistant", "content": r["text"]}}],
                   "usage": {"prompt_tokens": r["prompt_tokens"],
                             "completion_tokens": r["completion_tokens"]}}
            rec["status"] = "ok"; rec["latency_s"] = round(time.time()-t0, 2)
            _fleet_mod.Fleet().vouch_inference(res["node_id"])
        else:
            rec["status"] = "error"; rec["error"] = (res.get("error") or "")[:150]
            rec["latency_s"] = round(time.time()-t0, 2)
            out = {"error": rec["error"]}
    with PROXY_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    # J17 cold start: every real routed outcome feeds the capability ledger so
    # the bump rule accumulates evidence from live traffic (gate still decides
    # whether bumps APPLY — recording happens always, per the dry-run spec).
    try:
        from .capability import Ledger, class_key
        led = Ledger()
        led.record({"bench_key": f"{model}@127.0.0.1",
                    "difficulty": decision["difficulty"], "timing": decision["timing"],
                    "when": "NOW" if decision["timing"] == "NOW" else "LATER",
                    "outcome": ("success" if rec["status"] == "ok" else "failure"),
                    "latency_s": rec.get("latency_s"),
                    "ts": rec["ts"]})
    except Exception:
        pass  # ledger telemetry must never break routing
    if rec["status"] == "error":
        return JSONResponse(out, status_code=502)
    return JSONResponse(out)

@app.get("/v1/models")
def models():
    r = json.loads(urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5).read())
    return {"object": "list", "data": [{"id": m["name"], "object": "model"} for m in r["models"]]}
