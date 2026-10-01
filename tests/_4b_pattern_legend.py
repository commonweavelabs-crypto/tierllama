"""4b LAST RESUME ATTEMPT: Gui's pre-baked-pattern idea (9/30 late).

Hypothesis: give the 4b a LEGEND that pre-computes all reasoning into word
labels (EASY needs skill 'weak'+; NOW needs speed 'fast'...), and tag
candidates with the same word labels. Then 4b only PATTERN-MATCHES words
(its proven skill) instead of comparing numbers (its proven failure).

Purest form: the legend makes matching ~literal ("HARD requires the skill tag
'competent'"). Includes must-FAIL cases: a pattern-matcher that never rejects
is useless — rejection IS pattern matching here ('fast' does not appear in a
NOW job's requirement).

Two shapes tested:
  A) ADEQUATE/INADEQUATE verdict (match = ADEQUATE)
  B) forced-choice tier classify (which tier's spec does the candidate satisfy)
"""
import json, urllib.request, time

LEGEND = (
    "JOB SPEC LEGEND (use ONLY these labels):\n"
    "TIER skill requirements: EASY needs skill tag 'weak' (or any stronger tag).\n"
    "MEDIUM needs skill tag 'competent' (or any stronger tag).\n"
    "HARD needs skill tag 'competent' (or any stronger tag).\n"
    "EXPERT needs skill tag 'frontier' only.\n"
    "TIMING requirements: NOW jobs need speed tag 'fast'. LATER jobs accept any speed.\n"
    "ORDER of skill tags: weak < competent < frontier.\n"
    "A candidate PASSES a job when: its skill tag meets the tier requirement by the order above,\n"
    "AND its speed tag meets the timing requirement. Otherwise it FAILS.\n")

CANDS = [
    # (job desc, candidate desc, truth_pass, why)
    ("JOB: HARD, LATER",        "skill tag 'competent', speed tag 'slow'",   True,  "competent>=competent, LATER allows slow"),
    ("JOB: HARD, NOW",          "skill tag 'competent', speed tag 'slow'",   False, "NOW requires 'fast'"),
    ("JOB: EASY, NOW",          "skill tag 'weak', speed tag 'fast'",        True,  "weak>=weak, fast>=fast"),
    ("JOB: EXPERT, NOW",        "skill tag 'weak', speed tag 'fast', cloud", False, "weak < frontier"),
    ("JOB: EASY, NOW",          "skill tag 'competent', speed tag 'fast'",   True,  "competent >= weak required"),
    ("JOB: EXPERT, LATER",      "skill tag 'competent', speed tag 'slow'",   False, "competent < frontier"),
    ("JOB: MEDIUM, NOW",        "skill tag 'competent', speed tag 'fast'",   True,  "meets both"),
    ("JOB: MEDIUM, NOW",        "skill tag 'weak', speed tag 'fast'",        False, "weak < competent"),
]

def ask_adequate(job, cand):
    q = (LEGEND + "\nJOB: " + job.split(": ")[1] + "\nCANDIDATE: " + cand +
         "\nDoes the candidate PASS this job's spec? One word: ADEQUATE or INADEQUATE.")
    body = {"model": "qwen3:4b", "stream": False, "think": True,
            "options": {"num_predict": 2000, "temperature": 0},
            "messages": [{"role": "user", "content": q}]}
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    r = json.loads(urllib.request.urlopen(req, timeout=420).read())
    el = round(time.time() - t0, 1)
    a = (r["message"].get("content") or "").strip()
    got = a[:12] if a else "<empty>"
    if not a and (r["message"].get("thinking") or ""):
        got = "think-burned(" + str(r.get("eval_count")) + ")"
    return got, a.upper().startswith("ADEQUATE"), el, r.get("eval_count")

def main():
    ok = 0; n = 0; pos_ok = neg_ok = 0; n_pos = n_neg = 0
    print("=== SHAPE A: legend word-matching -> ADEQUATE/INADEQUATE ===", flush=True)
    for job, cand, truth, why in CANDS:
        n += 1
        got, pred, el, ev = ask_adequate(job, cand)
        hit = pred == truth
        ok += hit
        if truth: n_pos += 1; pos_ok += hit
        else: n_neg += 1; neg_ok += hit
        print(f"{job:16s} {cand[:42]:44s} want={str(truth):5s} got={got:22s} {'OK' if hit else 'MISS'} ({el}s ev={ev})", flush=True)
    print(f"SHAPE A: {ok}/{n}   positives {pos_ok}/{n_pos}  negatives {neg_ok}/{n_neg}", flush=True)

if __name__ == "__main__":
    main()