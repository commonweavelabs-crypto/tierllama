"""Re-run ONLY the one-brain comparison arm with the fixed verdict-token read.

Bug in _j19_pipeline_bench.py's arm: the assistant-prefill 'VERDICT:' turn makes
Ollama start a NEW assistant message (first token ' Candidate'), so the scored
token was never ADEQUATE/INADEQUATE -> all p=0.00. Fix: no assistant prefill;
user message ends in 'VERDICT:'; score the FIRST sampled token.
Truth = measured capability floors + Gui stances (same as bench).
"""
import json, sys, math, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
for m in [k for k in sys.modules if k.startswith("tierllama")]:
    del sys.modules[m]

from tierllama.rater import gather_pool, rate_all  # noqa: E402

TIERS = [(d, t) for d in ("EASY", "MEDIUM", "HARD", "EXPERT") for t in ("NOW", "LATER")]
NEED = {"EASY": 25, "MEDIUM": 45, "HARD": 62, "EXPERT": 82}
ARM_MODELS = ["kimi-k3:cloud", "glm-5.3-flash:cloud", "gemma3:12b", "qwen3-vl:8b", "ornith-1.5:35b"]
STANCE = lambda model, d: "kimi" in model.lower() and d != "EXPERT"

RUBRIC = ("You judge whether a candidate model can do a routing tier's job. Tier jobs: "
          "EASY=short replies/simple QA; MEDIUM=summarization/rewriting/reliable instructions; "
          "HARD=code gen/technical analysis/structured reasoning; "
          "EXPERT=long-form technical writing/multi-step reasoning/harness driving; "
          "NOW=user waiting ~1min; LATER=async overnight. Weigh capability, dollar cost, "
          "latency, specialty match. End your answer with exactly 'VERDICT: ADEQUATE' or "
          "'VERDICT: INADEQUATE'.")

def read_p_adequate(model, task_line, timeout=60):
    """One call; returns P(ADEQUATE) from the first sampled verdict-token position."""
    body = {"model": model, "stream": False, "logprobs": True, "top_logprobs": 20,
            "max_tokens": 24, "temperature": 0,
            "messages": [{"role": "user", "content":
                          RUBRIC + "\n\n" + task_line + "\nVERDICT:"}]}
    req = urllib.request.Request("http://127.0.0.1:11434/v1/chat/completions",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    txt = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    lp = txt["choices"][0]["logprobs"]["content"]
    # find the first token position at which ADEQUATE/INADEQUATE appears in top-k
    for t in lp:
        for cand in t["top_logprobs"]:
            tok = cand["token"].strip().upper()
            if tok.startswith(("ADEQUATE", "INADEQUATE")):
                probs = {"A": 0.0, "I": 0.0}
                for c2 in t["top_logprobs"]:
                    k = c2["token"].strip().upper()
                    if k.startswith("ADEQUATE"):
                        probs["A"] += math.exp(c2["logprob"])
                    elif k.startswith("INADEQUATE"):
                        probs["I"] += math.exp(c2["logprob"])
                tot = probs["A"] + probs["I"]
                if tot > 0:
                    return probs["A"] / tot
    return None

def main():
    pool = gather_pool()
    rows = rate_all(pool)
    def arm_truth(m, tk):
        d, t = tk.split("/")
        row = next((r for r in rows if r["model"] == m), None)
        if row is None: return None, "not-in-pool"
        if STANCE(m, d): return False, "stance-reserve"
        if row["capability"] < NEED[d]: return False, "capability-floor"
        if t == "NOW" and not row.get("cloud"):
            cdn = (row.get("can_do_now") or {}).get("med" if d in ("EASY", "MEDIUM") else "hard")
            if not cdn: return False, "too-slow-for-NOW"
        return True, "meets-floor"

    out = []
    for m in ARM_MODELS:
        for d, t in TIERS:
            tk = f"{d}/{t}"
            truth, why = arm_truth(m, tk)
            if truth is None: continue
            p = read_p_adequate("qwen3:4b", f"Can model '{m}' do this tier? {tk}")
            out.append({"model": m, "tier": tk, "truth": truth, "truth_why": why,
                        "qwen4b_p_adequate": p})
            print(f"{m:20s} {tk:14s} truth={truth!s:5s} ({why:14s}) p={p}", flush=True)
    valid = [r for r in out if r["qwen4b_p_adequate"] is not None]
    for th in (0.5,):
        ok = sum(1 for r in valid if (r["qwen4b_p_adequate"] >= th) == r["truth"])
        acc = round(100 * ok / len(valid), 1) if valid else None
    best, bestacc = 0.5, -1
    for i in range(5, 96):
        t2 = i / 100
        ok2 = sum(1 for r in valid if (r["qwen4b_p_adequate"] >= t2) == r["truth"])
        if ok2 > bestacc: best, bestacc = t2, ok2
    print(f"\nARM n={len(out)} (valid={len(valid)})  p>=0.5 acc={acc}%")
    print(f"best-calibrated threshold={best:.2f} -> {bestacc}/{len(valid)} = {round(100*bestacc/len(valid),1)}%")
    ts = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M")
    p = ROOT / "tests" / f"onebrain_arm_{ts}.json"
    p.write_text(json.dumps({"n": len(out), "acc_at_0.5": acc,
                             "best_threshold": best, "best_acc": round(100*bestacc/len(valid), 1) if valid else None,
                             "rows": out}, indent=2), encoding="utf-8")
    print("saved:", p)

if __name__ == "__main__":
    main()