"""J13 golden set v2: WHEN-dimension scoring (18 WHEN cases + resolver checks).
Run: C:/Python313/python.exe tests/run_golden_set_v2_when.py
"""
import json, sys, time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(r"C:\Users\Guilherme\AppData\Local\hermes\.env")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tierllama.classifier import classify
from tierllama.router import _resolve_due

TESTS = Path(__file__).resolve().parent
gs = json.load(open(TESTS / "golden_set_v2_when.json", encoding="utf-8"))

results = []
t0 = time.time()
for i, item in enumerate(gs):
    try:
        d = classify(item["msg"])
        got = {"when": d.get("when", "NOW"), "when_raw": d.get("when_raw") or None}
    except Exception as e:
        d = None
        results.append({"i": i, "msg": item["msg"], "truth": item["truth"], "got": None, "error": str(e)[:100]})
        continue
    # truth for when_raw: match if the raw phrase is contained or both None
    when_ok = got["when"] == item["truth"]["when"]
    raw_ok = True
    tr = item["truth"]["when_raw"]
    gr = got["when_raw"]
    if tr:
        raw_ok = bool(gr) and tr.lower() in (gr or "").lower()
    else:
        raw_ok = True  # raw phrase optional when truth has none
    results.append({"i": i, "msg": item["msg"], "truth": item["truth"], "got": got,
                    "when_ok": when_ok, "raw_ok": raw_ok})
    print(f"{i+1}/{len(gs)} ({time.time()-t0:.0f}s)", flush=True)

n = sum(1 for r in results if r.get("got"))
w = sum(1 for r in results if r.get("when_ok"))
rw = sum(1 for r in results if r.get("raw_ok"))
print(f"\nWHEN scorecard (n={n}):")
print(f"  when:    {w}/{n} = {round(w/n*100,1)}%")
print(f"  when_raw phrase match: {rw}/{n} = {round(rw/n*100,1)}%")
misses = [{"msg": r["msg"], "truth": r["truth"], "got": r["got"]}
          for r in results if r.get("got") and not (r["when_ok"] and r["raw_ok"])]
print(f"misses ({len(misses)}):")
for m in misses:
    print(f"  - '{m['msg']}' truth={m['truth']} got={m['got']}")

# resolver sanity: DEADLINE truths with a parseable phrase MUST resolve via dumb code
res_ok = 0
for item in gs:
    if item["truth"]["when"] == "DEADLINE" and item["truth"]["when_raw"]:
        if _resolve_due(item["truth"]["when_raw"]):
            res_ok += 1
print(f"resolver: {res_ok} DEADLINE phrases parsed by dumb regex (no LLM)")

out = TESTS / f"golden_set_v2_results_{time.strftime('%Y%m%d_%H%M')}.json"
json.dump({"scorecard": {"when": f"{w}/{n}", "raw": f"{rw}/{n}", "resolver": res_ok},
           "results": results}, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("saved:", out)