"""Tierllama lane adapters (J3): dispatch a routed message to its lane and return the result.

LOCAL        -> Ollama local models (ornith-1.5:9b / qwen3:4b), sync, sub-second-ish
CLOUD_MEDIUM -> Ollama cloud models (glm-5.3-flash:cloud), sync, ~2s
CLOUD_HARD   -> Ollama cloud (kimi/glm big class) or OpenAI-compatible API (config)
BOX          -> overnight job queue on the mini box (UNC share \\<box-lan-ip>\C$\jobs)

Every dispatch is recorded in the decision log with result + latency. Adapters never
raise: failures return {"status": "error", ...} so the router can escalate (J4)."""
import json, re, re, re, uuid, datetime, urllib.request, urllib.error, time
from pathlib import Path
from .config import LANES, CLASSIFIER

# J20.5-context law (measured Oct 4): Ollama's default context comes from the HOST env
# (OLLAMA_CONTEXT_LENGTH, on this machine 262144 for the ornith-262k chats). A vision
# model at that ctx wants a ~36GB KV cache -> llama.cpp offloads most layers to CPU
# -> 6.6 tok/s. Explicit per-call num_ctx makes BOTH the runtime and the bench
# immune to whatever env the host happens to carry. 8192 covers the rubric +
# a chat-sized prompt with huge headroom; bench parity measured 73 tok/s with it.
DEFAULT_NUM_CTX = 8192

BOX_API = "http://<box-lan-ip>:8080"          # llama-swap (direct inference)
BOX_JOBS = Path(r"\\<box-lan-ip>\C$\jobs")   # job queue (async, overnight)

def _post_chat(endpoint, body, timeout=120):
    req = urllib.request.Request(endpoint, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def _thinking_body(message, model, system, thinking, timeout=120):
    """J7: unified body builder with thinking-level support.
    thinking='max' -> think:true (qwen3-class models; cloud models may reject -> retry without).
    options.num_ctx is set EXPLICITLY (J20.5-context law): the host's OLLAMA_CONTEXT_LENGTH
    (262144 here) makes vision models build a city-sized KV cache and crawl at 6 tok/s."""
    body = {"model": model, "stream": False,
            "options": {"num_ctx": DEFAULT_NUM_CTX},
            "messages": ([{"role": "system", "content": system}] if system else [])
                       + [{"role": "user", "content": message}]}
    if thinking == "max":
        body["think"] = True
    elif thinking == "off":
        body["think"] = False
    return body

def dispatch_local(message, model=None, system=None, thinking=None, timeout=120):
    """LOCAL lane: sync inference on a local Ollama model."""
    model = model or LANES["LOCAL"]["models"][0]
    body = _thinking_body(message, model, system, thinking)
    t0 = time.time()
    try:
        r = _post_chat(CLASSIFIER["endpoint"], body, timeout)
        return {"status": "ok", "lane": "LOCAL", "model": model,
                "result": r["message"]["content"], "latency_s": round(time.time()-t0, 2)}
    except Exception as e:
        return {"status": "error", "lane": "LOCAL", "model": model, "error": str(e)[:200],
                "latency_s": round(time.time()-t0, 2)}

def dispatch_cloud(message, tier="CLOUD_MEDIUM", model=None, system=None, thinking=None, timeout=120):
    """CLOUD lanes: Ollama-served cloud models (glm-5.3-flash:cloud verified) or any
    OpenAI-compatible endpoint via config. model kwarg overrides the lane default
    (J7 decision-tree targets)."""
    lane = LANES[tier]
    model = model or lane["models"][0]
    body = _thinking_body(message, model, system, thinking)
    t0 = time.time()
    try:
        try:
            r = _post_chat(CLASSIFIER["endpoint"], body, timeout)
        except urllib.error.HTTPError as e:
            if e.code == 400 and "think" in body:   # model rejects thinking flag (J6-style fix: adapt, don't fail)
                body.pop("think", None)
                r = _post_chat(CLASSIFIER["endpoint"], body, timeout)
            else:
                raise
        return {"status": "ok", "lane": tier, "model": model,
                "result": r["message"]["content"], "latency_s": round(time.time()-t0, 2)}
    except Exception as e:
        return {"status": "error", "lane": tier, "model": model, "error": str(e)[:200],
                "latency_s": round(time.time()-t0, 2)}

def _safe_title(title):
    return "".join(c for c in re.sub(r"\W+", "-", (title or "job").lower())[:24] if c.isalnum() or c == "-").strip("-") or "job"

def dispatch_box(message, title="tierllama-box-job", model="qwen38-27b-iq3s", system=None, thinking=None, timeout=30):
    """BOX lane: enqueue an overnight job on the mini box. The box worker consumes
    C:/jobs/pending/*.json files shaped {id, model, system, prompt} and POSTs them to
    local llama-swap; the response lands in done/<id>.response.json. Async by design."""
    job_id = f"job-{datetime.datetime.now().strftime('%Y%m%d')}t-{uuid.uuid4().hex[:6]}-{_safe_title(title)}"
    job_path = BOX_JOBS / "pending" / f"{job_id}.json"
    payload = {"id": job_id, "model": model,
               "system": system or "You are a careful assistant. Answer completely.",
               "prompt": message}
    t0 = time.time()
    try:
        job_path.write_text(json.dumps(payload), encoding="utf-8")
        return {"status": "queued", "lane": "BOX", "job_id": job_id,
                "path": str(job_path), "latency_s": round(time.time()-t0, 2),
                "note": "async - result at \\<box-lan-ip>\C$\jobs\done\<id>.response.json"}
    except Exception as e:
        return {"status": "error", "lane": "BOX", "error": str(e)[:200],
                "latency_s": round(time.time()-t0, 2)}

def dispatch(lane, message, **kw):
    if lane == "LOCAL": return dispatch_local(message, **kw)
    if lane == "CLOUD_MEDIUM": return dispatch_cloud(message, "CLOUD_MEDIUM", **kw)
    if lane == "CLOUD_HARD": return dispatch_cloud(message, "CLOUD_HARD", **kw)
    if lane == "BOX": return dispatch_box(message, **kw)
    if lane == "FALLBACK": return dispatch_cloud(message, "CLOUD_MEDIUM", **kw)
    return {"status": "error", "error": f"unknown lane {lane}"}
