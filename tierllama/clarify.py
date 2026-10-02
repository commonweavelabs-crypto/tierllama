"""J20 Part 2 — the CLARIFY lane (Gui's design, Oct 1).

Third routing state below dim-aware confidence floors: instead of silently
falling back or guessing, ASK the user exactly one question about the one
dimension that is unsure, log the exchange to the learned-calibration ledger,
and route with the clarified dim (the other dim keeps Jev's verdict).

Privacy law (docs/J19.7-CLARIFY-LANE-DESIGN.md):
- logs/clarify_ledger.jsonl = FULL detail locally (prompt text included).
- ANY export/share path = distilled pattern buckets ONLY — never prompt text.
- The ledger's export() enforces this at the data layer, not by convention.

The asker: tev1:0.8b via /v1/systemone (calibrated probabilities beat
qwen3:0.6b's echo-yes 7/10 vs 5/10 on the ambiguity set; 1.9s for 10 asks).
"""
import json, datetime, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
LEDGER_PATH = ROOT / "logs" / "clarify_ledger.jsonl"

# dim-aware floors (Gui: start 0.55, editable one-liners, never stone)
CLARIFY = {
    "difficulty_conf_floor": 0.55,
    "timing_conf_floor": 0.55,
    "asker_model": "tev1:0.8b",
    "max_pending_age_h": 48,     # older unanswered clarifies expire in the UI
}

ASKERS = {
    "timing": {"type": "choice",
               "instructions": "Is this task for NOW (user is waiting) or LATER (async, no rush)?",
               "criteria": {"NOW": "the work should start immediately - urgency word, deadline clock, vague short command, or a live session waiting",
                            "LATER": "the user explicitly deferred - tomorrow, later, whenever, no rush, overnight, sometime"}},
    "difficulty": {"type": "choice",
                   "instructions": "How big is this work?",
                   "criteria": {"EASY": "tiny single action, one line, small talk, simple factual answer",
                                "MEDIUM": "one scene edit/rewrite, one described bug, multi-step how-to",
                                "HARD": "multi-part or multi-system work, live breakage triage, urgent decision-support, whole-deliverable production",
                                "EXPERT": "novel research-grade frontier work, inventing new architecture/pipeline/algorithm"}},
}

PATTERN_BUCKETS = {
    ("NOW", "defer-word-present"): "defer-phrase+vague-referent",
    ("LATER", "clock-deadline"): "clock-deadline-on-work",
    ("NOW", "planner-verb"): "planner-verb-timing",
    ("LATER", "whole-deliverable"): "whole-deliverable-underdefers",
}


def needs_clarify(dims: dict) -> dict | None:
    """Returns the ONE dim to ask about, or None if both clear the floor."""
    from .config import CLASSIFIER
    floors = {"difficulty": CLASSIFIER.get("difficulty_conf_floor",
                                           CLARIFY["difficulty_conf_floor"]),
              "timing": CLASSIFIER.get("timing_conf_floor",
                                       CLARIFY["timing_conf_floor"])}
    dc, tc = dims.get("difficulty_conf"), dims.get("timing_conf")
    d_ok = dc is None or dc >= floors["difficulty"]
    t_ok = tc is None or tc >= floors["timing"]
    if d_ok and t_ok:
        return None
    # clarify the LOWER-confidence dim first (one question per exchange)
    worst = "difficulty" if (dc or 1) <= (tc or 1) else "timing"
    return {"dim": worst, "conf": dc if worst == "difficulty" else tc}


def ask(state_text: str, dim: str, timeout: int = 45) -> dict:
    """One tev1 request for the unsure dim. Returns {answer, probabilities}."""
    body = {"model": CLARIFY["asker_model"], "state": state_text,
            "questions": {"q": ASKERS[dim]}}
    req = urllib.request.Request("http://127.0.0.1:11434/v1/systemone",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = datetime.datetime.now()
    r = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    a = (r.get("answers", {}) or {}).get("q", {})
    return {"answer": a.get("choice"),
            "probabilities": a.get("probabilities") or {},
            "confidence": a.get("confidence"),
            "latency_s": round((datetime.datetime.now() - t0).total_seconds(), 2)}


def bucket_for(question_text: str, dim: str) -> str:
    """Coarse pattern bucket (the future distiller's grain). Keyword-level on
    the MESSAGE TEXT — never exported, only the bucket name leaves the machine."""
    t = (question_text or "").lower()
    defer = any(w in t for w in ("tomorrow", "later", "whenever", "no rush", "overnight", "sometime", "when you get"))
    clock = any(w in t for w in ("deadline", "by friday", "tonight", "today", "due ", "hours before"))
    planner = any(w in t for w in ("plan ", "organize ", "schedule ", "prepare "))
    whole = any(w in t for w in ("whole ", "entire ", "everything", "all "))
    if dim == "timing" and defer:
        return "defer-phrase+vague-referent"
    if dim == "timing" and clock:
        return "clock-deadline-on-work"
    if dim == "timing" and planner:
        return "planner-verb-timing"
    if dim == "difficulty" and whole:
        return "whole-deliverable-underdefers"
    return "other-" + dim


def log_exchange(question_text: str, dims: dict, dim: str, asked: dict, answer: str | None):
    """Full-detail LOCAL ledger. Prompt text stays on this machine."""
    LEDGER_PATH.parent.mkdir(exist_ok=True)
    rec = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "message": question_text,                    # LOCAL ONLY — never exported
        "dim": dim,
        "jev_conf": {"difficulty": dims.get("difficulty_conf"),
                      "timing": dims.get("timing_conf")},
        "jev_verdict": {"difficulty": dims.get("difficulty"),
                        "timing": dims.get("timing")},
        "asked": asked,                               # model answer + probabilities
        "user_answer": answer,                        # one-tap UI answer (or None=pending)
        "bucket": bucket_for(question_text, dim),
        "asker_model": CLARIFY["asker_model"],
    }
    with LEDGER_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def export_patterns() -> list[dict]:
    """THE ONLY sanctioned export shape: distilled buckets, aggregated,
    NOT one row per prompt. Returns per-bucket: count, user-answer distribution.
    Prompt text NEVER crosses this boundary (enforced by construction: only
    bucket/answer/conf fields are read here)."""
    if not LEDGER_PATH.exists():
        return []
    agg: dict[str, dict] = {}
    for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if not r.get("user_answer"):
            continue
        b = r.get("bucket") or "other"
        agg.setdefault(b, {"count": 0, "answers": {}, "avg_conf": []})
        agg[b]["count"] += 1
        ans = r["user_answer"]
        agg[b]["answers"][ans] = agg[b]["answers"].get(ans, 0) + 1
        if r.get("asked", {}).get("confidence") is not None:
            agg[b]["avg_conf"].append(r["asked"]["confidence"])
    out = []
    for b, v in sorted(agg.items()):
        total = v["count"]
        out.append({"bucket": b, "count": total,
                    "answers": v["answers"],
                    "user_answer_top": max(v["answers"], key=lambda k: v["answers"][k]),
                    "avg_asker_conf": round(sum(v["avg_conf"]) / max(len(v["avg_conf"]), 1), 2)})
    return out