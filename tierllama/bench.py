"""Tierllama bench (J8): one combined sweep per local model = cold-load capture +
timed + graded competence probes. Writes the recommendation matrix with source tags.

Run:  python cli.py bench          (all machines + models)
      python cli.py bench --model qwen3:8b

Protocol per LOCAL model (cloud models: ping only, default-NOW):
  1. unload (keep_alive=0)            -> model fully out of RAM
  2. EASY probe   (timed from zero)   -> cold_load_s + easy_pass
  3. MEDIUM probe (timed)             -> steady tok/s + med_pass
  4. HARD probe   (timed)             -> hard_pass + reasoning-latency
Results land in bench_results.json {model@machine: {...}, source: "measured"}.
The Optimize flow (webapp /api/optimize) consumes this to prefill routing.json.
"""
import json, time, urllib.request, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
BENCH_LOG = ROOT / "logs" / "bench.jsonl"
OLLAMA = "http://127.0.0.1:11434"

PROBES = [
    ("EASY", "What is 17 * 23? Answer with just the number.",
     lambda r: "391" in r),
    ("MEDIUM", "Write a Python function is_palindrome(s) that returns True if string s is a palindrome (case-insensitive). Reply with code only, no explanation.",
     None),  # graded by EXEC below
    ("HARD", "Solve step by step: A shop sells notebooks for $4 and pens for $1.5. Ana buys x notebooks and 6 pens for $35. How many notebooks did she buy? End your reply with 'ANSWER: <number>'.",
     lambda r: "ANSWER: 6" in r or "ANSWER: 6." in r),
]


def _post(path, body, timeout=300):
    req = urllib.request.Request(OLLAMA + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def unload(model):
    try:
        _post("/api/chat", {"model": model, "messages": [], "keep_alive": 0}, timeout=30)
        time.sleep(1.0)
    except Exception:
        pass


def local_models(endpoint=OLLAMA):
    return [m["name"] for m in _post(endpoint.replace("/api/chat", "") + "/api/tags",
                                     {}, timeout=5) if False] or _get_models(endpoint)


def _get_models(endpoint=OLLAMA):
    req = urllib.request.Request(endpoint + "/api/tags")
    return [m["name"] for m in json.loads(urllib.request.urlopen(req, timeout=5).read())["models"]]


def _run_probe(model, prompt, num_predict=2500):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "stream": False, "think": False,
            "options": {"num_predict": num_predict}, "keep_alive": 600}
    r = _post("/api/chat", body)
    m_ = r.get("message", {})
    txt = m_.get("content", "")
    # thinking-class models (qwen3:4b) may put the code in the thinking field:
    txt += "\n" + (m_.get("thinking", "") or m_.get("reasoning", "") or "")
    tok_s = r.get("eval_count", 0) / max(r.get("eval_duration", 1) / 1e9, 0.001)
    wall = r.get("eval_duration", 0) / 1e9 + r.get("prompt_eval_duration", 0) / 1e9
    return txt, round(tok_s, 1), round(wall, 2)


def _grade_medium(txt):
    """Exec-based check: extract is_palindrome (fenced block first), run cases."""
    import re, textwrap
    blocks = re.findall(r"```(?:python)?\s*(.*?)```", txt, re.S)
    blocks += re.findall(r"def is_palindrome.*?(?=\n\S|\Z)", txt, re.S)
    for code in blocks:
        if "def is_palindrome" not in code:
            continue
        try:
            ns = {}
            exec(textwrap.dedent(code), ns)
            return [ns["is_palindrome"](s) for s in
                    ["racecar", "Racecar", "hello", "Aba"]] == [True, True, False, True]
        except Exception:
            continue
    return False


def probe_model(model):
    """One combined sweep: cold-load + EASY + MEDIUM + HARD (timed AND graded)."""
    out = {"model": model, "source": "measured",
           "ts": datetime.datetime.now().isoformat(timespec="seconds")}
    # 1. cold-load: unload then time the first (EASY) probe from zero
    unload(model)
    p_easy, check_easy = PROBES[0][1], PROBES[0][2]
    t0 = time.time()
    txt, tok_s, _ = _run_probe(model, p_easy)
    out["cold_load_s"] = round(time.time() - t0, 2)
    out["easy_pass"] = bool(check_easy(txt))
    out["tok_s"] = tok_s
    # 2. MEDIUM + HARD (warm now - steady-state timing)
    for name, prompt, check in PROBES[1:]:
        txt, tok_s, wall = _run_probe(model, prompt)
        if check is None:
            check = _grade_medium
        passed = bool(check(txt))
        if not passed:  # best-of-2 on flaky probes (single-shot grading is noisy)
            txt, tok_s, wall = _run_probe(model, prompt)
            passed = bool(check(txt))
        out[f"{name.lower()}_pass"] = passed
        out[f"{name.lower()}_s"] = wall
    # 3. classify: NOW vs LATER (speed knob) - steady-state tok/s
    out["timing_fit"] = "NOW" if out["tok_s"] >= 20 and out["cold_load_s"] < 15 else "LATER"
    # 4. competence knob: EASY->EASY tier, +MEDIUM->MEDIUM, +HARD->HARD
    if out.get("hard_pass"):
        out["max_fit"] = "HARD"
    elif out.get("medium_pass"):
        out["max_fit"] = "MEDIUM"
    elif out["easy_pass"]:
        out["max_fit"] = "EASY"
    else:
        out["max_fit"] = "UNRELIABLE"
    BENCH_LOG.open("a", encoding="utf-8").write(json.dumps(out) + "\n")
    return out


def bench_all(progress_cb=None):
    models = _get_models()
    results = []
    for i, m in enumerate(models):
        if progress_cb:
            progress_cb(i, len(models), m)
        try:
            results.append(probe_model(m))
        except Exception as e:
            results.append({"model": m, "error": str(e)[:120]})
    return results