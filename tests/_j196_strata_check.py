"""J19.6 strata check: re-run ONLY the previously-missed cases (HARD/NOW 15 +
EASY/LATER 6) against the patched rubric. Fast gate before the full 209 bench."""
import json, sys, time, importlib.util
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
for m in [k for k in sys.modules if k.startswith("tierllama")]:
    del sys.modules[m]
spec = importlib.util.spec_from_file_location("bench", ROOT / "tests" / "_j19_pipeline_bench.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
from tierllama.classifier import classify  # patched rubric

CASES = [
    # (msg, want_difficulty, want_timing)
    ("why is my render darker than the preview?", "HARD", "NOW"),
    ("it crashed again but only on scene 7, here's the log", "HARD", "NOW"),
    ("we have 3 hours before the deadline, what's the priority?", "HARD", "NOW"),
    ("decide: practical effects or CGI for the explosion scene", "HARD", "NOW"),
    ("fix this crash now please", "HARD", "NOW"),
    ("I need the trailer cut today", "HARD", "NOW"),
    ("optimize the particle system for 60fps on integrated graphics", "HARD", "NOW"),
    ("plan the launch render pipeline for 8 videos tonight", "HARD", "NOW"),
    ("refactor the ingest flow, everything's due tonight", "HARD", "NOW"),
    ("debug why 3 scenes dropped frames simultaneously", "HARD", "NOW"),
    ("redesign the thumbnail pipeline before Friday", "HARD", "NOW"),
    ("asap: the whole color pipeline has banding issues", "HARD", "NOW"),
    ("do everything needed to finish the trailer by friday", "HARD", "NOW"),
    ("queue all scenes overnight", "EASY", "LATER"),
    ("do this when you get a chance", "EASY", "LATER"),
    ("rename these clips without any rush", "EASY", "LATER"),
    ("zoom the preview whenever", "EASY", "LATER"),
    ("reset zoom whenever", "EASY", "LATER"),
    ("pin the timeline tomorrow", "EASY", "LATER"),
    # REGRESSION GUARDS (were correct before — must stay correct)
    ("set the format to mp4", "EASY", "NOW"),
    ("export the trailer cut before 5pm", "MEDIUM", "NOW"),
    ("rename this clip whenever you get a chance", "EASY", "LATER"),
    ("improve the whole second act", "HARD", "NOW"),
    ("hi", "EASY", "NOW"),
    ("rewrite scene 3 to make the dialogue sharper", "MEDIUM", "NOW"),
    ("plan the render sequence for the 10 scenes", "HARD", "NOW"),
]

def main():
    ok = 0; results = []
    for msg, wd, wt in CASES:
        r = classify(msg)
        d, t = r.get("difficulty"), r.get("timing")
        hit = (d == wd and t == wt); ok += hit
        results.append({"msg": msg, "want": f"{wd}/{wt}", "got": f"{d}/{t}", "ok": hit})
        print(f"{'OK  ' if hit else 'MISS'} {msg[:56]:58s} want={wd}/{wt:6s} got={d}/{t}", flush=True)
    print(f"\nSTRATA CHECK: {ok}/{len(CASES)}")
    Path(__file__).with_name("j196_strata_check.json").write_text(json.dumps(results, indent=1), encoding="utf-8")

if __name__ == "__main__":
    main()