"""OneBrain experiment: can Jev (gemma3:12b) do Brain 1's job too?

Stratified 32-case subset (4 per tier) from the same bench set; same rubric +
enum-JSON format as classifier.py, model swapped to gemma3:12b.
Compares accuracy vs the qwen3:4b 209-case bench (74.6 diff / 91.4 timing).
"""
import json, sys, urllib.request, time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
for m in [k for k in sys.modules if k.startswith("tierllama")]:
    del sys.modules[m]

sys.path.insert(0, str(ROOT / "tests"))
import importlib.util
spec = importlib.util.spec_from_file_location("bench", ROOT / "tests" / "_j19_pipeline_bench.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)   # build_set_stratified without running main

RUBRIC = bench.__dict__.get("build_set_stratified")  # noqa - just to prove load
from tierllama.classifier import RUBRIC as CLASSIFIER_RUBRIC, _classify_dims  # noqa: E402

FORMAT = {"type": "object", "properties": {
    "difficulty": {"type": "string", "enum": ["EASY", "MEDIUM", "HARD", "EXPERT"]},
    "timing": {"type": "string", "enum": ["NOW", "LATER"]}},
    "required": ["difficulty", "timing"]}

def classify_with(model, msg, timeout=120):
    body = {"model": model, "stream": False,
            "options": {"temperature": 0, "num_predict": 100},
            "format": FORMAT,
            "messages": [{"role": "user", "content":
                CLASSIFIER_RUBRIC + f'\n\nMessage: "{msg}"\nScore this message. Return difficulty and timing only.'}]}
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    r = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    latency = time.time() - t0
    try:
        dims = json.loads(r["message"]["content"])
        return dims.get("difficulty"), dims.get("timing"), latency, None
    except Exception:
        return None, None, latency, (r["message"]["content"] or "")[:80]

def main(n_per_tier=4, seed=7):
    import random
    cases = bench.build_set_stratified(25)
    random.Random(seed).shuffle(cases)
    picking = {}
    for c in cases:
        picking.setdefault((c["truth_difficulty"], c["truth_timing"]), [])
    sel = []
    seen = {}
    for c in cases:
        k = (c["truth_difficulty"], c["truth_timing"])
        if seen.get(k, 0) < n_per_tier:
            sel.append(c); seen[k] = seen.get(k, 0) + 1
    print(f"gemma3:12b subset n={len(sel)} ({n_per_tier}/tier)")
    ok_d = ok_t = ok_e = 0
    lat = []
    errs = 0
    for i, c in enumerate(sel):
        d, t, el, err = classify_with("gemma3:12b", c["msg"])
        lat.append(el)
        if err: errs += 1
        hit_d = d == c["truth_difficulty"]; hit_t = t == c["truth_timing"]
        ok_d += hit_d; ok_t += hit_t; ok_e += (hit_d and hit_t)
        flag = "" if (hit_d and hit_t) else "  <-- MISS"
        if not (hit_d and hit_t):
            print(f"  '{c['msg'][:50]}' truth={c['truth_difficulty']}/{c['truth_timing']} pred={d}/{t}{flag}")
    n = len(sel)
    print(f"\ngemma3:12b  diff={round(100*ok_d/n,1)}%  timing={round(100*ok_t/n,1)}%  exact={round(100*ok_e/n,1)}%  (n={n}, parse_err={errs})")
    print(f"median latency {round(sorted(lat)[len(lat)//2],1)}s   (qwen3:4b bench median was 6.1s; 4b got 74.6/91.4 exact 67.9 on n=209)")

if __name__ == "__main__":
    main()