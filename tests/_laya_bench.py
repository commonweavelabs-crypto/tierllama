
import json, time, statistics, sys
import laya

agent = laya.load("convaiinnovations/laya")

gs = json.load(open(r"C:\Users\Guilherme\tierllama\tests\golden_set_v1.json", encoding="utf-8"))
results = []
lat = []
for i, item in enumerate(gs):
    questions = {
        "difficulty": {"type": "choice",
            "instructions": "Difficulty of this user message for a routing system: EASY = single tiny action, one-line edit, small talk, factual answer. MEDIUM = one scene edit/rewrite, described bug, multi-step how-to, non-trivial explanation of this app's behavior. HARD = multi-scene/whole-project work, multiple bugs, big rewrites, urgent multi-part work. EXPERT = frontier/research-grade, novel architecture.",
            "criteria": ["EASY","MEDIUM","HARD","EXPERT"]},
        "timing": {"type": "choice",
            "instructions": "When should this be handled? NOW is the default and the answer for ALL vague/short commands; LATER only if the user explicitly defers (overnight, whenever you have time, no rush, later).",
            "criteria": ["NOW","LATER"]},
    }
    t0 = time.time()
    try:
        r = agent.predict(item["msg"], questions)
        dt = time.time()-t0
        lat.append(dt)
        a = r["answers"]
        results.append({"i": i, "msg": item["msg"],
            "truth": item["truth"],
            "got": {"difficulty": a["difficulty"]["choice"],
                    "timing": a["timing"]["choice"],
                    "difficulty_probs": a["difficulty"]["probabilities"],
                    "confidence": a["difficulty"]["confidence"],
                    "answer_confidence": a["difficulty"]["answer_confidence"]}})
    except Exception as e:
        results.append({"i": i, "msg": item["msg"], "truth": item["truth"],
                        "got": None, "error": str(e)[:200]})
    if (i+1) % 20 == 0: print(f"{i+1}/62 done", flush=True)

json.dump(results, open(r"C:\Users\Guilherme\tierllama\tests\laya_bench_results.json","w",encoding="utf-8"), indent=1, ensure_ascii=False)
scores = {"difficulty":0,"timing":0}; full=0; n=0
for r in results:
    if not r.get("got"): continue
    n += 1; t,g = r["truth"], r["got"]; ok=True
    for d in scores:
        if t[d]==g[d]: scores[d]+=1
        else: ok=False
    if ok: full+=1
print(f"LAYA SCORECARD (n={n}):")
for d,s in scores.items(): print(f"  {d}: {s}/{n} = {s/n*100:.1f}%")
print(f"  full: {full}/{n} = {full/n*100:.1f}%")
print(f"  latency p50={statistics.median(lat)*1000:.0f}ms p95={sorted(lat)[int(len(lat)*0.95)]*1000:.0f}ms")
