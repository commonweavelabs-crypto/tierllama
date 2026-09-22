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
KEYS_FILE = ROOT / ".tierllama_keys.env"  # local, gitignored - keys never in repo

def _load_keys():
    keys = {}
    if KEYS_FILE.exists():
        for line in KEYS_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                keys[k.strip()] = v.strip()
    return keys

def save_key(provider_name, key):
    """Store a provider key locally (gitignored file). Returns env var name."""
    for p in load_providers():
        if p["name"] == provider_name:
            env = p.get("api_key_env", "NONE")
            if env == "NONE":
                return {"ok": False, "reason": "provider needs no key"}
            keys = _load_keys(); keys[env] = key
            KEYS_FILE.write_text("\n".join(f"{k}={v}" for k, v in keys.items()) + "\n", encoding="utf-8")
            os.environ[env] = key  # live for this session too
            return {"ok": True, "env": env}
    return {"ok": False, "reason": "unknown provider"}

def set_enabled(provider_name, enabled):
    """Flip enabled flag in providers.toml (tomlkit-free: regex rewrite)."""
    txt = PROVIDERS_TOML.read_text(encoding="utf-8")
    import re as _re
    # find the [[provider]] block for this name and flip its enabled line
    blocks = txt.split("[[provider]]")
    for i, b in enumerate(blocks):
        if f'name = "{provider_name}"' in b:
            lines = b.splitlines()
            for j, ln in enumerate(lines):
                if ln.strip().startswith("enabled"):
                    lines[j] = f"enabled = {str(bool(enabled)).lower()}"
            blocks[i] = "\n".join(lines) + "\n"
    PROVIDERS_TOML.write_text("[[provider]]".join(blocks), encoding="utf-8")
    return {"ok": True}

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
        keys = _load_keys()
        has_key = key_env == "NONE" or bool(os.environ.get(key_env) or keys.get(key_env))
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
