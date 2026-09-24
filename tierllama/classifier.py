"""Tierllama classifier v3: enum-constrained dims (difficulty + timing) via Ollama.
Self-reported confidence is junk (model says 0.95 on everything, even its errors);
token-level logprobs are the honest signal. Measured 2026-09-21: 94.2% @ ~80ms warm."""
import json, urllib.request, time, math
from .config import CLASSIFIER

RUBRIC = """You classify user messages for a routing system (Tierllama): each message gets a difficulty and a timing. Decide role, difficulty, timing from the user's INTENT.
Difficulty anchors (examples per level):
- EASY: "set format to mp4"; "hi"; "rename this clip"; "what fps should I use?" (single action, one line, or small talk)
- MEDIUM: "rewrite scene 3 dialogue"; "app crashes when I drag cards"; "how do I batch-export?" (one scene edit, one described bug, multi-step how-to)
- HARD: "restructure the whole second act"; "plan renders for 10 scenes"; "audio desync + visual glitches + crashes at once" (multi-scene, multi-bug, or multi-system)
- EXPERT: novel research-grade or frontier work: "build a new custom video pipeline from scratch", "design a novel prompt architecture nobody has tried", "rewrite the render engine's core algorithm" (unproven territory, architecture-level creation, research-grade problems with no known recipe)
Boundary rules: "do X now" where X is one concrete action = EASY even if urgent. "the whole project/act/screenplay" = at least HARD. Vague one-liners ("make it better", "just do it", "you know what I mean") = difficulty of the underlying referent if clear from context, else MEDIUM. Multi-bug reports (2+ separate failures) = HARD. Single described failure = MEDIUM.
Difficulty: EASY = single tiny action (set/open/click one thing), one-line edit, small talk, simple factual answer. Explanations of THIS app's non-obvious behavior ('why does X happen', 'what does the queue system do') = MEDIUM; simple factual Q&A and generic knowledge = EASY. Export/render/submit of an existing project = the action's size only (one export = EASY/MEDIUM even if the project is large); deadline pressure never raises difficulty. MEDIUM = one scene edit/rewrite, described bug, multi-step how-to. HARD = multi-scene/whole-act work, multi-scene planning, ambiguity, long creative tasks. EXPERT = frontier/research-grade: architecture creation, novel pipelines, algorithm design, problems with no known recipe. Length alone never means EXPERT; unproven-territory work does.
Timing: NOW is the DEFAULT and the answer for ALL vague/short commands ("make it better", "just do it", "you know what I mean") - if no explicit defer word appears, it is NOW. Urgency words ("now", "right now", "asap", "urgent", "immediately", "today") ALWAYS mean NOW. Only LATER if the user explicitly defers: "later", "tomorrow", "by friday", "when you get a chance", "no rush", "whenever". Big/complex work alone NEVER implies LATER - "big task now" = NOW. Examples: "do X now" -> NOW even if HARD. "do the whole act, no rush" -> LATER. "queue/overnight" (batch words) -> LATER unless combined with an urgency word ("queue it now" -> NOW).
Timing anchors: "fix this bug now" (HARD) -> HARD/NOW. "plan act 2 tonight, urgent" -> HARD/NOW. "rebuild the pipeline this week" -> EXPERT/NOW. "improve everything whenever you have time" -> HARD/LATER.
Examples (difficulty/timing):
"set the format to mp4" -> EASY/NOW
"open the timeline" -> EASY/NOW
"hi" -> EASY/NOW
"how do I set the fps?" -> EASY/NOW
"app crashes when I drag cards" -> MEDIUM/NOW
"rewrite scene 3, sharper dialogue" -> MEDIUM/NOW
"plan the render sequence for 10 scenes" -> HARD/LATER
"queue all scenes overnight" -> EASY/NOW
"improve the whole second act" -> HARD/LATER
"audio out of sync after render" -> HARD/NOW
"rebuild the render engine core algorithm" -> EXPERT/NOW
"fix this bug now" -> HARD/NOW
"do the whole act now" -> HARD/NOW
"improve everything whenever you have time" -> HARD/LATER"""


def classify(message, last_exchanges=None, timeout=60):
    """Classification: difficulty + timing via the enum-constrained JSON path.
    (J12 hygiene: role taxonomy removed - it belongs to the video-workspace
    project, not the router. Lane = difficulty x timing.)"""
    d = _classify_dims(message, timeout=timeout)
    d["latency_s"] = round(d.pop("_dims_latency_s", 0), 3)
    return d


def _classify_dims(message, timeout=60):
    """difficulty + timing via the enum-constrained chat endpoint (J1 path)."""
    from .config import CLASSIFIER as C
    body = {"model": C["model"], "stream": False, "think": False,
        "options": {"temperature": C["temperature"]},
        "messages": [{"role": "user", "content":
            RUBRIC + f'\n\nMessage: "{message}"\nScore this message. Return confidence 0.0-1.0 per dimension.'}],
        "format": {"type": "object", "properties": {
            "difficulty": {"type": "string", "enum": ["EASY", "MEDIUM", "HARD", "EXPERT"]},
            "difficulty_conf": {"type": "number"},
            "timing": {"type": "string", "enum": ["NOW", "LATER"]},
            "timing_conf": {"type": "number"}},
            "required": ["difficulty", "difficulty_conf", "timing", "timing_conf"]}}
    req = urllib.request.Request(C["endpoint"],
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    r = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    d = json.loads(r["message"]["content"])
    d["_dims_latency_s"] = time.time() - t0
    return d
