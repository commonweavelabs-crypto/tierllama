"""Providers v2 (J10): TOML descriptors for OpenAI-compatible providers.
Keys in env vars. Dispatch + per-provider cost accounting."""
import json, os, time, urllib.request, datetime
from pathlib import Path
try:
    import tomllib
except ImportError:
    tomllib = None

ROOT = Path(__file__).parent.parent
PROVIDERS_TOML = ROOT / "providers.toml"
COST_LOG = ROOT / "logs" / "costs.jsonl"

def load_providers():
    if not PROVIDERS_TOML.exists() or tomllib is None:
        return []
    with open(PROVIDERS_TOML, "rb") as f:
        data = tomllib.load(f)
    return data.get("provider", [])

def provider_models():
    """All models from enabled providers: [{model, provider, cost_in, cost_out}]"""
    out = []
    for p in load_providers():
        if not p.get("enabled", False):
            continue
        key_env = p.get("api_key_env", "NONE")
        has_key = key_env == "NONE" or bool(os.environ.get(key_env))
        for tier, model in p.get("models", {}).items():
            out.append({"model": model, "provider": p["name"],
                        "key_ready": key_env == "NONE" or bool(os.environ.get(key_env)),
                        "cost_in": p.get("cost_per_mtok_input"), "cost_out": p.get("cost_per_mtok_output")})
    return out

def dispatch_provider(provider_name, model, message, system=None, timeout=120):
    """Send to any OpenAI-compatible provider endpoint. Logs cost per call."""
    provs = {p["name"]: p for p in load_providers()}
    p = provs.get(provider_name)
    if not p:
        return {"status": "error", "error": f"unknown provider {provider_name}"}
    key_env = p.get("api_key_env", "NONE")
    headers = {"Content-Type": "application/json"}
    if key_env != "NONE":
        key = os.environ.get(key_env)
        if not key:
            return {"status": "error", "error": f"{key_env} not set in environment"}
        headers["Authorization"] = f"Bearer {key}"
    body = {"model": model, "stream": False,
            "messages": ([{"role": "system", "content": system}] if system else [])
                       + [{"role": "user", "content": message}]}
    t0 = time.time()
    try:
        req = urllib.request.Request(p["base_url"] + "/chat/completions",
            data=json.dumps(body).encode(), headers=headers)
        r = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        usage = r.get("usage", {})
        in_tok = usage.get("prompt_tokens", 0); out_tok = usage.get("completion_tokens", 0)
        cost = (in_tok * p.get("cost_per_mtok_input", 0) + out_tok * p.get("cost_per_mtok_output", 0)) / 1e6
        COST_LOG.parent.mkdir(exist_ok=True)
        COST_LOG.open("a", encoding="utf-8").write(json.dumps({
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "provider": provider_name, "model": model,
            "in_tokens": in_tok, "out_tokens": out_tok,
            "cost_usd": round(cost, 6)}) + "\n")
        return {"status": "ok", "provider": provider_name, "model": model,
                "result": r["choices"][0]["message"]["content"],
                "cost_usd": round(cost, 6),
                "latency_s": round(time.time()-t0, 2)}
    except Exception as e:
        return {"status": "error", "error": str(e)[:150], "provider": provider_name}
