
import json, time, statistics
import laya

agent = laya.load("convaiinnovations/laya-typed-decisions")

gs = json.load(open(r"C:\Users\Guilherme\tierllama\tests\golden_set_v1.json", encoding="utf-8"))
results = []; lat=[]
for i, item in enumerate(gs):
    questions = {
        "difficulty": {"type": "choice",
            "instructions": "Classify the difficulty of this request.",
            "criteria": {
                "EASY": "one tiny action, one-line edit, small talk, factual answer",
                "MEDIUM": "one scene edit or rewrite, a described bug, a multi-step how-to",
                "HARD": "multi-scene or whole-project work, multiple bugs, big rewrites",
                "EXPERT": "frontier or research-grade novel architecture work"}},
        "timing": {"type": "choice",
            "instructions": "Classify the urgency of this request.",
            "criteria": {
                "NOW": "handle immediately, the default",
                "LATER": "user explicitly deferred: overnight, whenever, no rush"}},
    }
    t0 = time.time()
    try:
        r = agent.predict(item["msg"], questions)
        lat.append(time.time()-t0)
        a = r["answers"]
        results.append({"i": i, "msg": item["msg"], "truth": item["truth"],
            "got": {"difficulty": a["difficulty"]["choice"],
                    "timing": a["timing"]["choice"],
                    "difficulty_probs": a["difficulty"]["probabilities"],
                    "answer_confidence": a["difficulty"]["answer_confidence"]}})
    except Exception as e:
        results.append({"i": i, "msg": item["msg"], "truth": item["truth"], "got": None, "error": str(e)[:200]})
    if (i+1) % 20 == 0: print(f"{i+1}/62", flush=True)

json.dump(results, open(r"C:\Users\Guilherme\tierllama\tests\laya_typed_bench_results.json","w",encoding="utf-8"), indent=1, ensure_ascii=False)
scores={"difficulty":0,"timing":0}; full=0; n=0
for r in results:
    if not r.get("got"): continue
    n+=1; t,g=r["truth"],r["got"]; ok=True
    for d in scores:
        if t[d]==g[d]: scores[d]+=1
        else: ok=False
    if ok: full+=1
print(f"LAYA-TYPED SCORECARD (n={n}):")
for d,s in scores.items(): print(f"  {d}: {s}/{n} = {s/n*100:.1f}%")
print(f"  full: {full}/{n} = {full/n*100:.1f}%")
if lat: print(f"  latency p50={statistics.median(lat)*1000:.0f}ms")
