"""qwen3:8b full classify run (32 stratified cases) - the lightest-Jev candidate.
think=True (qwen3 law), enum-JSON format, same rubric as classifier.py.
Compare: 4b = 74.6/91.4/67.9 (n=209), gemma3:12b = 75.0/90.6/68.8 (n=32).
"""
import json, sys, urllib.request, time, random, importlib.util
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
for m in [k for k in sys.modules if k.startswith("tierllama")]:
    del sys.modules[m]
spec = importlib.util.spec_from_file_location("bench", ROOT / "tests" / "_j19_pipeline_bench.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
from tierllama.classifier import RUBRIC  # noqa: E402

FMT = {"type": "object", "properties": {
    "difficulty": {"type": "string", "enum": ["EASY", "MEDIUM", "HARD", "EXPERT"]},
    "timing": {"type": "string", "enum": ["NOW", "LATER"]}},
    "required": ["difficulty", "timing"]}

def main(n_per_tier=4, seed=7):
    cases = bench.build_set_stratified(25)
    random.Random(seed).shuffle(cases)
    sel, seen = [], {}
    for c in cases:
        k = (c["truth_difficulty"], c["truth_timing"])
        if seen.get(k, 0) < n_per_tier:
            sel.append(c); seen[k] = seen.get(k, 0) + 1
    print(f"qwen3:8b classify n={len(sel)}", flush=True)
    okd = okt = oke = 0; lat = []; errs = 0
    for i, c in enumerate(sel):
        body = {"model": "qwen3:8b", "stream": False, "think": True,
                "options": {"num_predict": 1500, "temperature": 0}, "format": FMT,
                "messages": [{"role": "user", "content":
                    RUBRIC + f'\n\nMessage: "{c["msg"]}"\nScore this message. Return difficulty and timing only.'}]}
        req = urllib.request.Request("http://127.0.0.1:11434/api/chat",
                                     data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        t0 = time.time()
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=180).read())
            d = json.loads(r["message"]["content"]); el = time.time() - t0; lat.append(el)
            hd = d.get("difficulty") == c["truth_difficulty"]
            ht = (d.get("timing") or "NOW") == c["truth_timing"]
            okd += hd; okt += ht; oke += (hd and ht)
            if not (hd and ht):
                print(f'MISS: {c["msg"][:50]:52s} {c["truth_difficulty"]}/{c["truth_timing"]} -> {d.get("difficulty")}/{d.get("timing")}', flush=True)
        except Exception as e:
            errs += 1; print(f'ERR: {c["msg"][:50]} {str(e)[:80]}', flush=True)
        if (i + 1) % 10 == 0: print(f"  {i+1}/{len(sel)}", flush=True)
    n = len(sel)
    med = round(sorted(lat)[len(lat)//2], 1) if lat else None
    print(f'RESULT qwen3:8b: diff={round(100*okd/n,1)} timing={round(100*okt/n,1)} exact={round(100*oke/n,1)} (n={n}, err={errs}) med_lat={med}s')

if __name__ == "__main__":
    main()