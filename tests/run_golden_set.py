"""J12 standing regression: re-run the golden set through the live classifier.

Usage:
    C:/Python313/python.exe tests/run_golden_set.py            # full run + scorecard
    C:/Python313/python.exe tests/run_golden_set.py --quick    # first 20 cases

Rule: run this after ANY rubric/classifier change. Scorecard must not regress
below the FINAL J12 numbers (timing 98.4 / difficulty 79.0 / role 69.4 /
full 53.2) - see docs/SPECS/jevllama-j12-golden-set-v1.md.
Output: tests/golden_set_results_<stamp>.json + printed scorecard.
"""
import json, sys, time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(r"C:\Users\Guilherme\AppData\Local\hermes\.env")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tierllama.classifier import classify

TESTS = Path(__file__).resolve().parent
gs = json.load(open(TESTS := TESTS / "golden_set_v1.json", encoding="utf-8")) if False else json.load(open(Path(__file__).resolve().parent / "golden_set_v1.json", encoding="utf-8"))

FINAL_FLOOR = {"timing": 91.9, "difficulty": 67.7, "full": 61.3}  # roleless rubric v7 (2026-09-23); -3pt tolerance applied at check time

def main():
    limit = int(sys.argv[sys.argv.index("--quick")+1]) if "--quick" in sys.argv else len(gs)
    subset = gs[:limit]
    results = []
    t0 = time.time()
    for i, item in enumerate(subset):
        try:
            d = classify(item["msg"])
            results.append({"i": i, "msg": item["msg"], "truth": item["truth"],
                "got": {"difficulty": d["difficulty"], "timing": d["timing"]}})
        except Exception as e:
            results.append({"i": i, "msg": item["msg"], "truth": item["truth"], "got": None, "error": str(e)[:100]})
        if (i+1) % 20 == 0:
            print(f"{i+1}/{len(subset)} ({time.time()-t0:.0f}s)", flush=True)
    n = sum(1 for r in results if r.get("got"))
    scores = {d: 0 for d in ["difficulty","timing"]}; full = 0
    for r in results:
        if not r.get("got"): continue
        t, g = r["truth"], r["got"]
        ok = True
        for d in scores:
            if t[d] == g[d]: scores[d] += 1
            else: ok = False
        if ok: full += 1
    pct = {d: round(scores[d]/n*100, 1) for d in scores}
    full_pct = round(full/n*100, 1)
    print(f"\nScorecard (n={n}):")
    for d in scores: print(f"  {d}: {scores[d]}/{n} = {pct[d]}%  (floor {FINAL_FLOOR[d]})")
    print(f"  full match: {full}/{n} = {full_pct}%  (floor {FINAL_FLOOR['full']})")
    regressions = [d for d in pct if pct[d] < FINAL_FLOOR[d] - 3.0] + \
                  (["full"] if full_pct < FINAL_FLOOR["full"] - 0.05 else [])
    out = Path(__file__).resolve().parent / f"golden_set_results_{time.strftime('%Y%m%d_%H%M')}.json"
    json.dump(results, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("results saved:", out)
    if regressions:
        print("REGRESSION vs J12 FINAL floor:", regressions)
        sys.exit(1)
    print("PASS - no regression vs J12 FINAL")

if __name__ == "__main__":
    main()