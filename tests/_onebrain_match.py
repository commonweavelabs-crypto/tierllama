"""Gui's reframe (9/30 evening): Jev (qwen3:4b) doesn't RATE models — it MATCHES
already-rated models to jobs. Descriptor-only questions, NO model names.
Hypothesis: the 4b failed rating because it anchored on NAMES; a pure
number-matching question in classifier shape may work.

Same 5 models x 8 tiers = 40 pairs from the bench truth (capability floors +
latency + stance), but the 4b never sees the name — only the numbers.
Verdict read = logprob token probability (Jev-class honest signal).
Control: same questions WITH the name, to prove/disprove the name-anchoring theory.
"""
import json, sys, math, urllib.request, importlib.util
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
for m in [k for k in sys.modules if k.startswith("tierllama")]:
    del sys.modules[m]

spec = importlib.util.spec_from_file_location("bench", ROOT / "tests" / "_j19_pipeline_bench.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
from tierllama.rater import gather_pool, rate_all  # noqa: E402

TIERS = bench.TIERS
NEED = bench.NEED
ARM_MODELS = bench.ARM_MODELS
STANCE = bench._stance_violation

def job_desc(d, t):
    return (f"JOB: difficulty {d} (EASY=25 need, MEDIUM=45, HARD=62, EXPERT=82 on the capability "
            f"scale; answer must be delivered {'NOW' if t=='NOW' else 'LATER'} "
            f"({'user is waiting, ~1 minute budget' if t=='NOW' else 'async/overnight, slow is acceptable'})")

def cand_desc(row, t, with_name):
    cap = row["capability"]
    tok = row.get("tok_s")
    cloud = bool(row.get("cloud"))
    tok_s = f"{tok} tok/s" if tok else "cloud-speed (server-side)"
    name = f"CANDIDATE MODEL: {row['model']}." if with_name else "CANDIDATE MODEL: (name withheld)."
    return (f"{name} Rated capabilities: capability-score {cap}; speed {tok_s}; "
            f"runs {'on remote cloud (fast, pays per token)' if cloud else 'on the local machine'}.")

def p_adequate(job, cand, timeout=90):
    """Logprob read on the first verdict token; returns (p_adequate, top_tokens)."""
    rubric = ("You judge whether a candidate model can take a job. Consider whether the "
              "candidate's capability-score meets the job's need, and whether its speed fits "
              "the delivery timing. Verdict: ADEQUATE if it can take the job, INADEQUATE if not.\n")
    body = {"model": "qwen3:4b", "stream": False, "logprobs": True, "top_logprobs": 20,
            "max_tokens": 16, "temperature": 0,
            "messages": [{"role": "user", "content": rubric + job + "\n" + cand + "\nVERDICT:"}]}
    req = urllib.request.Request("http://127.0.0.1:11434/v1/chat/completions",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    lp = r["choices"][0]["logprobs"]["content"]
    for tok in lp:
        probs = {"A": 0.0, "I": 0.0}
        for c in tok["top_logprobs"]:
            k = c["token"].strip().upper()
            if k.startswith("ADEQUATE") or k == "ADEQ" or k == "AD":
                probs["A"] += math.exp(c["logprob"])
            elif k.startswith("INADEQUATE") or k == "INAD":
                probs["I"] += math.exp(c["logprob"])
        tot = probs["A"] + probs["I"]
        if tot > 0:
            return probs["A"] / tot, [(c["token"], round(c["logprob"], 2)) for c in tok["top_logprobs"][:6]]
    return None, [(c["token"], round(c["logprob"], 2)) for c in lp[0]["top_logprobs"][:6]] if lp else None

def main():
    pool = gather_pool()
    rows = rate_all(pool)
    def truth(m, tk):
        d, t = tk.split("/")
        row = next((r for r in rows if r["model"] == m), None)
        if row is None: return None, None
        if STANCE(m, d): return False, "stance-reserve"
        if row["capability"] < NEED[d]: return False, "capability-floor"
        if t == "NOW" and not row.get("cloud"):
            cdn = (row.get("can_do_now") or {}).get("med" if d in ("EASY", "MEDIUM") else "hard")
            if not cdn: return False, "too-slow-for-NOW"
        return True, "meets-floor"

    results = {"blind": [], "named": []}
    for m in ARM_MODELS:
        row = next((r for r in rows if r["model"] == m), None)
        if row is None: continue
        for d, t in TIERS:
            tk = f"{d}/{t}"
            tr, why = truth(m, tk)
            if tr is None: continue
            job = job_desc(d, t)
            pb, tb = p_adequate(job, cand_desc(row, t, with_name=False))
            pn, tn = p_adequate(job, cand_desc(row, t, with_name=True))
            results["blind"].append({"model": m, "tier": tk, "truth": tr, "why": why, "p": pb})
            results["named"].append({"model": m, "tier": tk, "truth": tr, "why": why, "p": pn})
            print(f"{m:20s} {tk:14s} truth={tr!s:5s} blind_p={'None' if pb is None else round(pb,2)} named_p={'None' if pn is None else round(pn,2)}", flush=True)

    for mode in ("blind", "named"):
        v = [r for r in results[mode] if r["p"] is not None]
        if not v: print(f"\n{mode}: NO valid reads"); continue
        acc = round(100 * sum((r["p"] >= 0.5) == r["truth"] for r in v) / len(v), 1)
        best_t, best_ok = 0.5, -1
        for i in range(5, 96):
            tt = i / 100
            ok = sum((r["p"] >= tt) == r["truth"] for r in v)
            if ok > best_ok: best_t, best_ok = tt, ok
        print(f"\n{mode.upper()}: n={len(v)} acc@0.5={acc}%  best-th={best_t:.2f} -> {best_ok}/{len(v)} = {round(100*best_ok/len(v),1)}%")
    ts = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M")
    out = ROOT / "tests" / f"onebrain_match_{ts}.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("saved:", out)

if __name__ == "__main__":
    main()