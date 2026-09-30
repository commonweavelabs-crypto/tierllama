"""J19/J13v2 — Two-brain pipeline bench (built 2026-09-30, Gui-approved).

Tests the REAL composition Gui asked for: question -> Brain 1 (classifier tier)
-> Brain 2 (model matrix) -> picked model. Two graded layers:
  L1: is the TIER right (hand truth from golden set + adjudicated real traffic + authored traps)
  L2: is the picked MODEL adequate (measured capability floors + Gui stance rules, strict)

Plus a comparison arm answering "can the CLASSIFIER (qwen3:4b, Jev-class logprob
read) replace the LLM (gemma3:12b generative) for model-rating?":
  40 (tier, model) pairs, truth = measured capability data (not opinions),
  both brains judged against it.

Run:  C:/Python313/python.exe tests/_j19_pipeline_bench.py
Output: tests/j19_bench_results_<ts>.json + console report.
No writes outside tests/ logs. No dispatch. GPU: classifier + gemma3 only.
"""
import json, sys, time, re, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
# module-cache pitfall: purge any stale tierllama imports first
for m in [k for k in sys.modules if k.startswith("tierllama")]:
    del sys.modules[m]

RESULTS_DIR = ROOT / "tests"
TIERS = [(d, t) for d in ("EASY", "MEDIUM", "HARD", "EXPERT") for t in ("NOW", "LATER")]
NEED = {"EASY": 25, "MEDIUM": 45, "HARD": 62, "EXPERT": 82}   # from rater.py thresholds
STANCES_STRICT = {
    "never_outside_expert": ["kimi"],            # any model whose name contains kimi
    "later_workhorse": ["qwen38-27b"],           # box model owns LATER slots (not benched yet -> N/A note)
}

# ---------------------------------------------------------------- question set
def _golden():
    g = json.loads((ROOT / "tests" / "golden_set_v1.json").read_text(encoding="utf-8"))
    return [(e["msg"], (e["truth"]["difficulty"], e["truth"]["timing"]), "golden") for e in g]

# Adjudicated real traffic (router's recorded label in brackets vs my rubric-truth).
# Truth notes preserved verbatim below for traceability.
_REAL = [
    ("hi", ("EASY", "NOW"), "trap"),
    ("Give James a more menacing introduction", ("MEDIUM", "NOW"), None),
    ("Explain seed values like I'm new to this", ("EASY", "NOW"), None),
    ("what is 2+2?", ("EASY", "NOW"), None),
    ("Explain in one sentence why the sky is blue.", ("EASY", "NOW"), None),
    ("what is 5+5?", ("EASY", "NOW"), None),
    ("hello", ("EASY", "NOW"), None),
    ("Click export and set the format to mp4", ("EASY", "NOW"), "two trivial UI actions; export=action size; router said MEDIUM"),
    ("The app crashes when I drag cards to the edge", ("MEDIUM", "NOW"), None),
    ("Rewrite scene 3 to make the dialogue sharper", ("MEDIUM", "NOW"), None),
    ("just do the next obvious step", ("MEDIUM", "NOW"), "ambiguity trap; vague referent"),
    ("Open the timeline and zoom to scene 2", ("EASY", "NOW"), "matches golden 'open the timeline and zoom to 200%' = EASY; router said MEDIUM"),
    ("export the trailer cut with the new codec settings", ("MEDIUM", "NOW"), None),
    ("clean up the transcriptions by friday 5pm", ("MEDIUM", "NOW"), "deadline!=LATER; router got dims right"),
    ("summarize this doc soon please", ("MEDIUM", "NOW"), "soon=DATE_UNCLEAR -> NOW"),
    ("test message", ("EASY", "NOW"), "trap; router said MEDIUM"),
    ("rewrite this paragraph to sound more professional", ("MEDIUM", "NOW"), None),
    ("Plan the render sequence for the 10 scenes", ("HARD", "LATER"), "rubric anchor"),
    ("improve the whole second act", ("HARD", "LATER"), "rubric anchor example"),
    ("Convert the voiceover into dialogue", ("MEDIUM", "NOW"), "single transformation; router said HARD/LATER"),
    ("do everything needed to finish the trailer by friday", ("HARD", "NOW"), "deadline -> NOW; router said LATER"),
    ("review my project end to end and fix what's wrong", ("HARD", "NOW"), "no defer word; router said LATER"),
    ("Plan the render sequence for the 10 scenes with attention to GPU memory", ("HARD", "LATER"), "rubric anchor variant"),
    ("recreate the universe very particle and every interaction on a computer simulation now", ("EXPERT", "NOW"), "research-grade + explicit now; router said HARD/LATER double miss"),
    ("Audio out of sync after render", ("HARD", "NOW"), "rubric anchor"),
    ("Export produces a black video file", ("MEDIUM", "NOW"), "single described failure = MEDIUM per rubric; router said HARD"),
    ("write a full technical whitepaper on distributed consensus protocols", ("EXPERT", "NOW"), None),
    ("write a full technical whitepaper with deep analysis of distributed consensus", ("EXPERT", "NOW"), None),
    ("design a rate limiter for an API gateway", ("HARD", "NOW"), "standard engineering, not novel architecture; router said EXPERT"),
    ("Queue all remaining scenes overnight", ("EASY", "NOW"), "rubric anchor: batch words + no urgency = still EASY but NOW"),
    ("Make the villain's motivation clearer", ("MEDIUM", "NOW"), "no defer; router said LATER"),
    ("Should we render the trailer first or the intro?", ("MEDIUM", "NOW"), "consult question; router said LATER"),
    ("Design a database schema for multi-tenant SaaS", ("HARD", "NOW"), "multi-part technical design; router said EASY/LATER double miss"),
]

_AUTHORED = [
    # EASY/NOW
    ("rename this clip", ("EASY", "NOW"), None), ("what fps should I use?", ("EASY", "NOW"), None),
    ("set the bitrate to 8000", ("EASY", "NOW"), None), ("open settings", ("EASY", "NOW"), None),
    ("mute the audio on clip 3", ("EASY", "NOW"), None), ("thanks", ("EASY", "NOW"), None),
    ("toggle dark mode on", ("EASY", "NOW"), None), ("crop to 16:9", ("EASY", "NOW"), None),
    ("add a fade in", ("EASY", "NOW"), None), ("what time is it?", ("EASY", "NOW"), None),
    # EASY/LATER (explicit defer + tiny action)
    ("rename this clip whenever you get a chance", ("EASY", "LATER"), None),
    ("no rush, but mute clip 3", ("EASY", "LATER"), None),
    ("whenever, add a fade in", ("EASY", "LATER"), None),
    ("fix the typo in the credits tomorrow", ("EASY", "LATER"), None),
    ("crop to 16:9 later", ("EASY", "LATER"), None),
    ("mute clip 3 when you get a chance", ("EASY", "LATER"), None),
    ("cleanup temp files sometime next week", ("EASY", "LATER"), None),
    ("add the watermark whenever", ("EASY", "LATER"), None),
    ("rename these clips without any rush", ("EASY", "LATER"), None),
    ("do the thumbnail update later", ("EASY", "LATER"), None),
    # MEDIUM/NOW
    ("rewrite scene 12 to be funnier", ("MEDIUM", "NOW"), None),
    ("the export button does nothing when clicked", ("MEDIUM", "NOW"), None),
    ("how do I batch import 50 clips?", ("MEDIUM", "NOW"), None),
    ("subtitles drift on long videos, help", ("MEDIUM", "NOW"), None),
    ("explain how the render queue works", ("MEDIUM", "NOW"), None),
    ("make the intro clip punchier", ("MEDIUM", "NOW"), None),
    ("convert this transcript into blog post format", ("MEDIUM", "NOW"), None),
    ("why does color grading look washed out after export?", ("MEDIUM", "NOW"), None),
    ("add transitions between all scenes in chapter 2", ("MEDIUM", "NOW"), None),
    ("trim the dead air from the podcast intro", ("MEDIUM", "NOW"), None),
    # MEDIUM/LATER
    ("rewrite the intro scenes tomorrow", ("MEDIUM", "LATER"), None),
    ("rewrite the outro, no rush", ("MEDIUM", "LATER"), None),
    ("batch import the footage whenever you get a chance", ("MEDIUM", "LATER"), None),
    ("trim the podcast intros later this week", ("MEDIUM", "LATER"), None),
    ("convert last month's transcripts when you have time", ("MEDIUM", "LATER"), None),
    ("redo the color pass on chapter 2 sometime, no rush", ("MEDIUM", "LATER"), None),
    ("add chapter markers to the video, whenever", ("MEDIUM", "LATER"), None),
    ("summarize the meeting recording later", ("MEDIUM", "LATER"), None),
    ("polish scene 7's pacing when you have a minute", ("MEDIUM", "LATER"), None),
    ("update the thumbnail set tomorrow morning", ("MEDIUM", "LATER"), None),
    # HARD/NOW
    ("audio desync AND flickering AND crashes after the latest render", ("HARD", "NOW"), None),
    ("fix the sync bug in scene 4, scene 9, and 12 now", ("HARD", "NOW"), None),
    ("plan the launch render pipeline for 8 videos tonight", ("HARD", "NOW"), None),
    ("the whole export stack broke, get it back today", ("HARD", "NOW"), None),
    ("refactor the ingest flow, everything's due tonight", ("HARD", "NOW"), None),
    ("debug why 3 scenes dropped frames simultaneously", ("HARD", "NOW"), None),
    ("retime all dialog across the full episode now", ("HARD", "NOW"), None),
    ("the render farm reports 4 different errors, triage them now", ("HARD", "NOW"), None),
    ("redesign the thumbnail pipeline before Friday", ("HARD", "NOW"), None),
    ("asap: the whole color pipeline has banding issues", ("HARD", "NOW"), None),
    # HARD/LATER
    ("restructure the second act whenever", ("HARD", "LATER"), None),
    ("do the full audio cleanup pass tomorrow", ("HARD", "LATER"), None),
    ("plan a render for all 40 scenes over the weekend", ("HARD", "LATER"), None),
    ("fix all the sync issues across episodes, no rush", ("HARD", "LATER"), None),
    ("redesign the editor's UI flow sometime", ("HARD", "LATER"), None),
    ("rewrite the tutorial chapter when you have time", ("HARD", "LATER"), None),
    ("remaster all previous episodes later", ("HARD", "LATER"), None),
    ("organize the whole asset library whenever you get a chance", ("HARD", "LATER"), None),
    ("do the end-to-end trailer polish tomorrow", ("HARD", "LATER"), None),
    # EXPERT/NOW
    ("design a novel generative b-roll pipeline from scratch", ("EXPERT", "NOW"), None),
    ("build an agentic system that self-critiques renders, no one has tried this", ("EXPERT", "NOW"), None),
    ("invent a new codec-aware shot matching algorithm", ("EXPERT", "NOW"), None),
    ("architect a real-time collaborative editing engine from zero", ("EXPERT", "NOW"), None),
    ("design a research plan to beat the current SOTA upscaler", ("EXPERT", "NOW"), None),
    ("propose a novel prompt architecture for multi-agent film generation", ("EXPERT", "NOW"), None),
    ("create a new render-scheduling algorithm that is provably fair", ("EXPERT", "NOW"), None),
    ("write a full technical whitepaper on distributed consensus protocols", ("EXPERT", "NOW"), None),
    # EXPERT/LATER
    ("design the next-gen pipeline architecture whenever you have time", ("EXPERT", "LATER"), None),
    ("research a novel upscaling approach, no rush", ("EXPERT", "LATER"), None),
    ("invent our own shot-matching algorithm sometime", ("EXPERT", "LATER"), None),
    ("rewrite the render engine core from scratch whenever", ("EXPERT", "LATER"), None),
    ("explore a fundamentally new editing paradigm when you get time", ("EXPERT", "LATER"), None),
    ("build an experimental multi-agent film studio design, when you get a chance", ("EXPERT", "LATER"), None),
]

def build_set():
    seen, out = set(), []
    for src_pool, src_tag in ((_golden(), "golden"), (_AUTHORED, "authored"), (_REAL, "real-adjudicated")):
        for msg, truth, note in src_pool:
            k = msg.strip().lower()
            if k in seen:
                continue
            seen.add(k)
            out.append({"msg": msg, "truth_difficulty": truth[0], "truth_timing": truth[1],
                        "source": src_tag, "note": note})
    return out

def build_set_stratified(target_per_tier=25):
    """200-case design: top each tier up to 25 by cycling authored variants;
    report actual coverage honestly."""
    base = build_set()
    # authored variant generator per tier for topping up
    var = {
        ("EASY","NOW"): ["set volume to 50", "switch to the beta UI", "what does fps mean?", "open the presets menu",
                          "disable the watermark toggle", "clear the recent list", "scroll to the top", "play clip 5",
                          "pause the preview", "save my layout"],
        ("EASY","LATER"): ["mute clip 7 later on", "zoom the preview whenever", "swap the icons when you can",
                            "rename batch 3 tomorrow", "toggle grid off whenever", "clear filters later",
                            "open docs sidebar sometime", "reset zoom whenever", "pin the timeline tomorrow", "unmute track 2 later"],
        ("MEDIUM","NOW"): ["rewrite the cold-open voiceover", "batch rename won't finish, why?", "how do I split a project?", "add captions to clip 8",
                            "why is the queue stuck on scene 2?", "convert the demo to vertical format", "fix the double subtitle row",
                            "outline a 6-shot opening", "regenerate the failed thumbnails", "merge these two scenes"],
        ("MEDIUM","LATER"): ["transcribe the b-roll footage when free", "recut the sizzle reel later", "rewrite chapter 3 intros tomorrow",
                              "swap the outro music when you can", "redo alt-text tomorrow", "fix the lower thirds later",
                              "compress the scratch footage whenever", "convert interviews to text sometime", "update the release notes later", "tag the archived clips when free"],
        ("HARD","NOW"): ["three cameras desynced, the mixer died, and the export froze", "rebalance audio across 12 tracks now",
                          "the whole project timeline corrupted, recover it today", "redesign render scheduling for 60 scenes tonight",
                          "fix cross-episode continuity errors now", "migrate all projects to the new codec today",
                          "debug the multi-GPU fallback path now", "triage the five failed renders asap",
                          "the 4K export is 3x too slow, diagnose now", "fix every color mismatch across episode 7 now"],
        ("HARD","LATER"): ["restructure all three acts whenever", "plan the 40-scene render over the weekend", "full audio remaster, no rush",
                            "redesign the export presets sometime", "fix continuity across all episodes when you can",
                            "remaster season one later", "rebuild the LUT pipeline tomorrow", "audit all renders whenever",
                            "consolidate all b-roll libraries when free", "retime the full feature cut later"],
        # EXPERT variants added below (kept out of the literal for clarity)
    }
    var[("EXPERT","NOW")] = ["invent a shot-matching metric no one has tried", "design a self-improving edit model from scratch",
                              "architect a zero-latency collab pipeline, research grade", "propose a new scaling law experiment for render bots",
                              "design a novel neural color grade from zero", "create an agentic editor that plans its own renders",
                              "solve multi-agent consistency in generative film, research grade", "invent a codec that trades bitrate for editability",
                              "design a provably optimal render scheduler, research grade", "propose a new paradigm for prompt-free editing"]
    var[("EXPERT","LATER")] = ["research a new generative edit paradigm whenever", "design tomorrow's render engine architecture, no rush",
                                "invent our own diffusion-based continuity solver sometime", "architect a fleet-wide self-optimizing render mesh when free",
                                "explore prompt-free film generation whenever", "design a novel agent-verifier loop for renders, no rush",
                                "create a research roadmap for automated color science sometime", "propose a fundamentally new codec architecture when you can",
                                "invent the studio's next-gen asset graph whenever", "plan a novel multi-agent A/V pipeline when time allows"]
    for key, msgs in var.items():
        have = sum(1 for c in base if (c["truth_difficulty"], c["truth_timing"]) == key)
        i = 0
        while have < target_per_tier and i < len(msgs):
            msg = msgs[i % len(msgs)] + ("" if i < len(msgs) else f" (variant {i//len(msgs)+1})")
            if msg.strip().lower() not in {c['msg'].strip().lower() for c in base}:
                base.append({"msg": msg, "truth_difficulty": key[0], "truth_timing": key[1],
                             "source": "authored-topup", "note": None})
                have += 1
            i += 1
    return base

# ---------------------------------------------------------------- Brain 1 run
def run_brain1(cases):
    from tierllama.classifier import classify
    rows = []
    for i, c in enumerate(cases):
        try:
            r = classify(c["msg"])
            rows.append({**c, "pred_difficulty": r.get("difficulty"), "pred_timing": r.get("timing"),
                         "latency_s": r.get("latency_s"),
                         "difficulty_conf": r.get("difficulty_conf"), "timing_conf": r.get("timing_conf")})
        except Exception as e:
            rows.append({**c, "pred_difficulty": None, "pred_timing": None, "error": str(e)[:120]})
        if (i + 1) % 20 == 0:
            print(f"  brain1 {i+1}/{len(cases)}", flush=True)
    return rows

# ---------------------------------------------------------------- Brain 2 run
def run_brain2():
    from tierllama.rater import gather_pool, rate_all
    from tierllama.jev_rater import rate_tiers, apply_stance_guardrails
    pool = gather_pool()
    rows = rate_all(pool)
    # Gui's operator stances (strict, confirmed 2026-09-30)
    stances = ["kimi-k3:cloud is RESERVED for EXPERT tiers only - never suggest it elsewhere",
               "qwen38-27b (the box) is the LATER workhorse",
               "qwen3 small models (<9B) are toys - not for real Hermes lanes"]
    ratings = rate_tiers(rows, TIERS, user_stances=stances)
    ratings = apply_stance_guardrails(ratings, rows)
    return rows, ratings

def _stance_violation(model: str, difficulty: str) -> bool:
    return any(s in model.lower() for s in STANCES_STRICT["never_outside_expert"]) and difficulty != "EXPERT"

def grade_brain2(rows, ratings):
    """Top pick per tier must (a) meet measured capability need, (b) respect stances (strict), (c) NOW-speed if NOW."""
    need = NEED
    by_cap = sorted(rows, key=lambda r: -r["capability"])
    out = {}
    for d, t in TIERS:
        key = f"{d}/{t}"
        sc = ratings.get(key, {}).get("scores", {})
        ok_flag = ratings.get(key, {}).get("ok", False)
        top = max(sc.items(), key=lambda kv: kv[1]) if sc else (None, None)
        m, s = top
        if m is None:
            out[key] = {"top": None, "jev_score": None, "matrix_ok": ok_flag,
                        "cap_ok": False, "stance_ok": False, "now_ok": False,
                        "passed": False, "fail_reason": "no-matrix-scores"}
            continue
        row = next((r for r in rows if r["model"] == m), None)
        cap_ok = bool(row and row["capability"] >= need[d])
        stance_ok = not _stance_violation(m, d)
        now_ok = True
        if t == "NOW" and row and not row.get("cloud"):
            cdn = (row.get("can_do_now") or {}).get("med" if d in ("EASY", "MEDIUM") else "hard")
            now_ok = bool(cdn)
        fails = [n for n, ok in (("capability-floor", cap_ok), ("stance", stance_ok), ("too-slow-NOW", now_ok)) if not ok]
        out[key] = {"top": m, "jev_score": s, "matrix_ok": ok_flag,
                    "cap_ok": cap_ok, "stance_ok": stance_ok, "now_ok": now_ok,
                    "passed": not fails, "fail_reason": ",".join(fails) or "ok"}
    return out

# ------------------------------------------------- comparison arm: 4b vs gemma3
ARM_MODELS = ["kimi-k3:cloud", "glm-5.3-flash:cloud", "gemma3:12b", "qwen3-vl:8b", "ornith-1.5:35b"]

def _arm_truth(m, tier_key, pool_rows):
    d, t = tier_key.split("/")
    row = next((r for r in pool_rows if r["model"] == m), None)
    if row is None:
        return None, "not-in-pool"
    if _stance_violation(m, d):
        return False, "stance-reserve"
    if row["capability"] < NEED[d]:
        return False, "capability-floor"
    if t == "NOW" and not row.get("cloud"):
        cdn = (row.get("can_do_now") or {}).get("med" if d in ("EASY","MEDIUM") else "hard")
        if not cdn:
            return False, "too-slow-for-NOW"
    return True, "meets-floor"

def _jev_classify_pair(model, tier_key, reason):
    """Classifier-form adequacy read: qwen3:4b logprob ADEQUATE/INADEQUATE (skill recipe)."""
    d, t = tier_key.split("/")
    rubric = ("You judge whether a candidate model can do a routing tier's job. Tier jobs: "
              "EASY=short replies/simple QA; MEDIUM=summarization/rewriting/reliable instructions; "
              "HARD=code gen/technical analysis/structured reasoning; EXPERT=long-form technical writing/multi-step reasoning/harness driving; "
              "NOW=user waiting ~1min; LATER=async overnight. Weigh capability, dollar cost, latency, specialty match. "
              "Answer format: VERDICT:")
    user = f"Candidate: {model}. Tier: {tier_key} ({reason}). Verdict:\nVERDICT:"
    body = {"model": "qwen3:4b", "stream": False, "logprobs": True, "top_logprobs": 20,
            "max_tokens": 1, "messages": [
                {"role": "user", "content": rubric + "\n\n" + user},
                {"role": "assistant", "content": "VERDICT:"}]}
    import urllib.request
    req = urllib.request.Request("http://127.0.0.1:11434/v1/chat/completions",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    txt = json.loads(urllib.request.urlopen(req, timeout=60).read())
    lps = txt["choices"][0]["logprobs"]["content"][0]["top_logprobs"]
    probs = {}
    for cand in lps:
        tok = cand["token"].strip().upper()
        if tok in ("ADEQUATE", "INADEQUATE"):
            probs[tok] = probs.get(tok, 0.0) + pow(2.718281828, cand["logprob"])
    tot = sum(probs.values()) or 1.0
    p_adeq = probs.get("ADEQUATE", 0.0) / tot
    return p_adeq

def run_comparison_arm(pool_rows, gemma3_ratings):
    pairs = [(m, f"{d}/{t}") for m in ARM_MODELS for d, t in TIERS]
    res = []
    for m, tk in pairs:
        truth, why = _arm_truth(m, tk, pool_rows)
        if truth is None:
            continue
        try:
            p = _jev_classify_pair(m, tk, "")
        except Exception as e:
            print(f"  arm fail {m} {tk}: {str(e)[:80]}", flush=True)
            continue
        gsc = gemma3_ratings.get(tk, {}).get("scores", {}).get(m)
        res.append({"model": m, "tier": tk, "truth": truth, "truth_why": why,
                    "classifier_p_adequate": round(p, 3),
                    "gemma3_score": gsc,
                    "gemma3_adequate_at_need": bool(gsc is not None and gsc >= NEED[tk.split('/')[0]])})
    return res

# ---------------------------------------------------------------- report
def summarize(b1, b2g, arm):
    def acc(rows, pred, val):
        valid = [r for r in rows if r.get(pred) is not None]
        errs = len(rows) - len(valid)
        if not valid: return None, 0, errs
        ok = sum(1 for r in valid if r.get(pred) == r.get(val))
        return round(100.0 * ok / len(valid), 1), len(valid), errs
    rep = {}
    rep["difficulty_acc"], n, e1 = acc(b1, "pred_difficulty", "truth_difficulty")
    rep["timing_acc"], n2, e2 = acc(b1, "pred_timing", "truth_timing")
    valid_tier = [r for r in b1 if r.get("pred_difficulty") is not None]
    rep["exact_tier_acc"] = round(100.0 * sum(1 for r in valid_tier if r.get("pred_difficulty") == r["truth_difficulty"] and r.get("pred_timing") == r["truth_timing"]) / len(valid_tier), 1) if valid_tier else None
    rep["n"] = len(b1)
    rep["prediction_errors"] = {"difficulty": e1, "timing": e2,
                                "note": "calls that returned no usable dims (server/parse failures) - excluded from accuracy denominators"}
    rep["rows"] = b1
    per_tier = {}
    for d, t in TIERS:
        sel = [r for r in b1 if (r["truth_difficulty"], r["truth_timing"]) == (d, t)]
        if sel:
            dt = round(100.0 * sum(1 for r in sel if r.get("pred_difficulty") == d) / len(sel), 1)
            tm = round(100.0 * sum(1 for r in sel if r.get("pred_timing") == t) / len(sel), 1)
            per_tier[f"{d}/{t}"] = {"n": len(sel), "difficulty_acc": dt, "timing_acc": tm}
    rep["per_tier"] = per_tier
    traps = [r for r in b1 if (r.get("note") or "").startswith(("trap", "ambiguity"))]
    rep["trap_results"] = [{"msg": r["msg"], "pred": f"{r.get('pred_difficulty')}/{r.get('pred_timing')}",
                            "truth": f"{r['truth_difficulty']}/{r['truth_timing']}",
                            "ok": r.get("pred_difficulty") == r["truth_difficulty"] and r.get("pred_timing") == r["truth_timing"]} for r in traps]
    lat = [r["latency_s"] for r in b1 if isinstance(r.get("latency_s"), (int, float))]
    rep["brain1_latency_median_s"] = round(sorted(lat)[len(lat)//2], 3) if lat else None
    rep["brain2_tiers"] = b2g
    arm_ok_c = sum(1 for a in arm if (a["classifier_p_adequate"] >= 0.5) == a["truth"])
    arm_ok_g = sum(1 for a in arm if a["gemma3_adequate_at_need"] == a["truth"])
    rep["arm"] = {"n": len(arm), "classifier_acc": round(100*arm_ok_c/len(arm), 1) if arm else None,
                  "gemma3_acc": round(100*arm_ok_g/len(arm), 1) if arm else None,
                  "detail": arm}
    misses = [{"msg": r["msg"], "truth": f"{r['truth_difficulty']}/{r['truth_timing']}",
               "pred": f"{r.get('pred_difficulty')}/{r.get('pred_timing')}", "source": r["source"]}
              for r in b1 if r.get("pred_difficulty") != r["truth_difficulty"] or r.get("pred_timing") != r["truth_timing"]]
    rep["misses"] = misses
    return rep

def main():
    t0 = time.time()
    cases = build_set_stratified(25)
    print(f"set built: {len(cases)} cases")
    print("=== Brain 1: classifier on live GPU ===")
    b1 = run_brain1(cases)
    print("=== Brain 2: gemma3 matrix ===")
    pool_rows, ratings = run_brain2()
    b2g = grade_brain2(pool_rows, ratings)
    print("=== comparison arm: qwen3:4b logprob vs gemma3 ===")
    arm = run_comparison_arm(pool_rows, ratings)
    rep = summarize(b1, b2g, arm)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    out = RESULTS_DIR / f"j19_bench_results_{ts}.json"
    out.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n" + "=" * 60)
    print(f"EXACT TIER ACC: {rep['exact_tier_acc']}%   (diff {rep['difficulty_acc']}% / timing {rep['timing_acc']}%)  n={rep['n']}")
    print(f"med latency: {rep['brain1_latency_median_s']}s")
    for k, v in rep["per_tier"].items():
        print(f"  {k:14s} n={v['n']:3d}  diff={v['difficulty_acc']:5.1f}  timing={v['timing_acc']:5.1f}")
    print("=== Brain 2 (gemma3 matrix, strict stances) ===")
    for k, v in b2g.items():
        print(f"  {k:14s} top={str(v['top']):24s} cap_ok={v['cap_ok']} stance_ok={v['stance_ok']} now_ok={v['now_ok']} -> {'PASS' if v['passed'] else 'FAIL ('+str(v.get('fail_reason'))+')'}")
    a = rep["arm"]
    print(f"=== ARM (40 pairs, truth=measured floors+stances): 4b classifier {a['classifier_acc']}%  vs  gemma3 {a['gemma3_acc']}%")
    print(f"saved: {out}")
    print(f"total wall time: {round(time.time()-t0)}s")
    print("MISSES (first 12):")
    for m in rep["misses"][:12]:
        print(f"  [{m['source']}] '{m['msg'][:60]}' truth={m['truth']} pred={m['pred']}")

if __name__ == "__main__":
    main()