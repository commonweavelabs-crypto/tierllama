"""J19: Jev as the model-suggestion brain (Gui's idea, Sep 29-30).

Instead of hand-tuned thresholds deciding which model drives which tier, the
classifier brain (Jev — local qwen3:4b, free; fallback: heuristic rater) reads
a compact DOSSIER per candidate model — capability, measured speed, real-dollar
cost, specialties, timing verdicts, user-stance notes — and scores each model
0-100 per tier for "can this model do THIS tier's job".

Heuristics (rater.py) are demoted to GUARDRAILS:
- dead models: never suggested (liveness)
- below the DRIVER_FLOOR: never suggested (can't hold a harness prompt)
- LATER-only models: never suggested for NOW tiers (measured timing)
- ceiling model: reserved for EXPERT... no — Jev decides that too; the
  guardrail only enforces the three hard lines above.

Ratings cached in logs/jev_ratings.json, keyed by a dossier hash so any bench
/ liveness / pool change invalidates them. Zero timers (Gui law): ratings
recompute on demand when the cache misses.
"""
import json, hashlib, datetime, urllib.request
import re as _re

def _norm(s: str) -> str:
    """lenient model-name compare: lowercase, drop non-alnum."""
    return _re.sub(r"[^a-z0-9]", "", s.lower())
from pathlib import Path

ROOT = Path(__file__).parent.parent
JEV_RATINGS_PATH = ROOT / "logs" / "jev_ratings.json"

TIER_JOBS = {
    "EASY": "short replies, simple Q&A, quick lookups; a wrong-but-plausible answer is recoverable",
    "MEDIUM": "summarization, rewriting, multi-paragraph drafting, routine tool-calls; must follow instructions reliably",
    "HARD": "code generation, technical analysis, structured reasoning; subtle errors are costly",
    "EXPERT": "long-form technical writing, multi-step reasoning, agentic harness driving with big internal prompts",
    "NOW": "the user is waiting — must return within ~a minute, sustained",
    "LATER": "async/overnight — minutes or hours of latency are acceptable",
}

def _dossier_hash(rows: list, tiers: list) -> str:
    payload = json.dumps([[{k: r.get(k) for k in ("model", "capability", "tok_s", "cost_rank",
                                                  "seconds_medium", "seconds_hard", "can_do_now")}
                           for r in rows], tiers], sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]

def _load() -> dict:
    try:
        return json.loads(JEV_RATINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save(d: dict):
    JEV_RATINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    JEV_RATINGS_PATH.write_text(json.dumps(d, indent=1), encoding="utf-8")

def _dossier_block(rows: list, user_stances: list[str]) -> str:
    lines = []
    for r in rows:
        facts = [f"{r['model']}",
                 f"capability {r['capability']}/100"]
        if r["cloud"]:
            facts.append("cloud, seconds latency")
            pi, po = r.get("price_in_per_mtok"), r.get("price_out_per_mtok")
            if pi is not None:
                facts.append(f"cost ${pi}/${
                    po if po is not None else '?'} per Mtok (input/output) — REAL dollar cost, weigh it")
        else:
            facts.append(f"local, {r['tok_s'] or '?'} tok/s, $0 cost")
            if r.get("seconds_medium") is not None:
                facts.append(f"medium-task measured ~{r['seconds_medium']}s")
        cdn = r.get("can_do_now") or {}
        if not r["cloud"]:
            facts.append("timing verdict: medium NOW-capable" if cdn.get("med")
                         else "timing verdict: LATER-only for medium work (too slow to use interactively)")
            facts.append("hard NOW-capable" if cdn.get("hard")
                         else "LATER-only for hard work")
        lines.append(" - ".join(facts))
    if user_stances:
        lines.append("Operator stance notes: " + "; ".join(user_stances))
    return "\n".join(lines)

def _jev_ask(system: str, user: str, timeout: int = 45, num_predict: int = 900,
             model: str | None = None) -> str | None:
    """One LLM completion via ollama /api/chat. None on failure.
    Default brain = CLASSIFIER model; the rater call pins gemma3:12b (the 4b
    loops endlessly on scoring tasks — probed). No think flag here: gemma3
    has none, and a 'think' kwarg errors on non-qwen3 models."""
    from .config import CLASSIFIER
    brain = model or CLASSIFIER["model"]
    payload = {"model": brain, "stream": False,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}],
               "options": {"temperature": 0, "num_predict": num_predict,
                           "num_ctx": 4096}}
    if brain.startswith("qwen3"):
        payload["think"] = False     # ollama forces thinking on qwen3 otherwise
    body = json.dumps(payload).encode()
    req = urllib.request.Request(CLASSIFIER["endpoint"], data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        msg = r.get("message", {}) or {}
        txt = (msg.get("content") or "").strip()
        if not txt and msg.get("thinking"):
            # this brain sometimes spends the whole budget thinking and returns
            # empty content; the thinking trail still contains score lines
            txt = str(msg.get("thinking")).strip()
        return txt or None
    except Exception:
        return None

import re as _re
def _parse_scores(text: str, valid_models: list[str]) -> dict | None:
    """Extract {model: score} even when Jev buries the JSON in chatty prose.
    Tolerant: fences, trailing prose, partial outputs, quoted keys."""
    if not text or not isinstance(text, str):
        return None
    out: dict[str, float] = {}
    for m in valid_models:
        # match "model-name": 78  /  model-name: 78  /  'model-name' — 78 anywhere in the text
        pat = _re.escape(m) + r"\"?'\]?\s*[:=]\s*([0-9]+(?:\.[0-9])?)"
        hit = None
        for mm in _re.finditer(pat, text, _re.IGNORECASE):
            hit = mm                      # last mention wins (final answer, not scratchpad)
        if hit:
            out[m] = max(0.0, min(100.0, float(hit.group(1))))
    return out or None

def rate_tiers(rows: list, tiers: list[tuple[str, str]],
               user_stances: list[str] | None = None) -> dict:
    """Jev rates the WHOLE matrix in ONE call (gemma3:12b brain — the 4b
    classifier loops endlessly on this task at any budget, probed live).
    Returns {tier_key: {"scores": {model: 0-100}, "ok": bool}}; ok=False →
    caller falls back to heuristic order."""
    dossier = _dossier_block(rows, user_stances or [])
    h = _dossier_hash(rows, [f"{d}/{t}" for d, t in tiers])
    cache = _load()
    if cache.get("dossier_hash") == h:
        return cache.get("ratings", {})
    model_names = [r["model"] for r in rows]
    tier_lines = [f"{d}/{t} — {TIER_JOBS[d]}" for d, t in tiers]
    system = ("You are Tierllama's model rater. One routing tier gets one score "
              "per candidate model (0-100) for how well it does that tier's job. "
              "Weigh: capability, real dollar cost, latency needs (NOW = user "
              "waiting; LATER = async/overnight, skill over speed), model "
              "specialty vs job mismatch, and operator stance notes. "
              "OUTPUT FORMAT: exactly one line per pair, like 'EASY/NOW|model-name: 75'. "
              "Every tier crossed with every candidate. NOTHING else.")
    user = (f"CANDIDATES:\n{dossier}\n\nTIERS:\n" + "\n".join(tier_lines) +
            f"\n\nOutput {len(tiers) * len(model_names)} lines: 'TIER|model: score'.")
    txt = _jev_ask(system, user, timeout=240, num_predict=1600, model="gemma3:12b")
    out = {}
    for d, t in tiers:
        out[f"{d}/{t}"] = {"scores": {}, "ok": False}
    if txt:
        for line in txt.splitlines():
            m = _re.match(r"[^A-Za-z0-9]*([A-Z]+)/([A-Z]+)[^A-Za-z0-9]*(.+?)\s*(?:[:=\-])\s*([0-9]+(?:\.[0-9])?)\s*$", line.strip())
            if not m:
                continue
            key = f"{m.group(1)}/{m.group(2)}"
            if key not in out:
                continue
            model = m.group(3).strip().strip("\"'").lstrip("-• ").strip()
            for vm in model_names:
                if vm == model or _norm(vm) == _norm(model) or \
                   _norm(vm).rstrip("cloud") == _norm(model).rstrip("cloud"):
                    s = max(0.0, min(100.0, float(m.group(4))))
                    out[key]["scores"][vm] = s
                    break
    for key, v in out.items():
        covered = {m for m in model_names if m in v["scores"]}
        v["ok"] = len(covered) >= max(2, len(model_names) // 2)
        if v["ok"]:
            # fill any missing candidates with a neutral 50 so downstream always scores
            for m in model_names:
                v["scores"].setdefault(m, 50.0)
    _save({"dossier_hash": h, "ratings": out,
           "generated": datetime.datetime.now().isoformat(timespec="seconds")})
    return out


def apply_stance_guardrails(ratings: dict, rows: list) -> dict:
    """Operator stances as HARD post-guardrails (not prompt hints — the brain
    ignores hints when raw capability dominates, observed live):
    - the CEILING model (highest capability row) is reserved for EXPERT: its
      score takes a flat demotion on every other tier. Only when no other
      candidate remains (cloud-only pool) is it left standing."""
    if not rows:
        return ratings
    ceiling = max(rows, key=lambda r: r["capability"])
    ceil_name = ceiling["model"]
    for key, v in ratings.items():
        if not v.get("ok") or key.split("/")[0] == "EXPERT":
            continue
        others = [s for m, s in v["scores"].items() if m != ceil_name]
        if others and ceil_name in v["scores"]:
            v["scores"][ceil_name] = max(0.0, v["scores"][ceil_name] - 30.0)
    return ratings