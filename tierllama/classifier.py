"""Tierllama classifier: one call -> {role, difficulty, timing, confidences}."""
import json, urllib.request, time
from .config import CLASSIFIER

RUBRIC = """You route user messages for an AI video-generation workspace. Decide role, difficulty, timing from the user's INTENT.
Roles:
- TEACHER: how-to questions, explanations, 'what is X', greetings, thanks, small talk. NO action requested = TEACHER.
- NAVIGATOR: concrete UI operations: click, open, set, toggle, submit, export, queue, delete, zoom, attach.
- SCREENWRITER: writing/rewriting/editing creative TEXT: dialogue, scenes, narration, shots.
- BUG_REPORTER: crashes, errors, unexpected behavior, broken things.
- DIRECTOR: plans, priorities, render strategy, decisions, 'what next', vague commands.
Difficulty: EASY = single tiny action (set/open/click one thing), one-line edit, small talk, factual answer. MEDIUM = one scene edit/rewrite, described bug, multi-step how-to. HARD = multi-scene/whole-act work, multi-scene planning, ambiguity, long creative tasks.
Timing: NOW = interactive, UI actions, questions, bug reports, quick edits. LATER = batch/queue/overnight/'by friday'/big creative work not awaited.

Examples:
"set the format to mp4" -> NAVIGATOR/EASY/NOW
"open the timeline" -> NAVIGATOR/EASY/NOW
"hi" -> TEACHER/EASY/NOW
"how do I set the fps?" -> TEACHER/EASY/NOW
"what's the difference between t2v and i2v?" -> TEACHER/EASY/NOW
"app crashes when I drag cards" -> BUG_REPORTER/MEDIUM/NOW
"rewrite scene 3, sharper dialogue" -> SCREENWRITER/MEDIUM/NOW
"give James a more menacing intro" -> SCREENWRITER/EASY/NOW
"plan the render sequence for 10 scenes" -> DIRECTOR/HARD/LATER
"queue all scenes overnight" -> NAVIGATOR/EASY/NOW
"improve the whole second act" -> SCREENWRITER/HARD/LATER
"audio out of sync after render" -> BUG_REPORTER/HARD/NOW
"convert the voiceover into dialogue" -> SCREENWRITER/HARD/LATER"""

DIFF_RULES = """Difficulty:
- EASY: one-step factual, tiny UI action, small talk, single short answer.
- MEDIUM: multi-step work, one scene edit, debugging a described issue, a how-to needing depth.
- HARD: multi-scene or cross-cutting work, architecture, ambiguity resolution, long creative tasks."""
TIMING_RULES = """Timing:
- NOW: user is waiting interactively for this result.
- LATER: big batch/creative work that can queue for later (overnight, background)."""

def classify(message, last_exchanges=None, timeout=60):
    rubric = RUBRIC + '\n\nMessage: "' + message + '"\nScore this message. Return confidence 0.0-1.0 per dimension.'
    body = {"model": CLASSIFIER["model"], "stream": False, "think": False,
        "options": {"temperature": CLASSIFIER["temperature"]},
        "messages": [{"role": "user", "content": rubric}],
        "format": {"type": "object", "properties": {
            "role": {"type": "string", "enum": ["DIRECTOR","SCREENWRITER","TEACHER","BUG_REPORTER","NAVIGATOR"]},
            "role_conf": {"type": "number"},
            "difficulty": {"type": "string", "enum": ["EASY","MEDIUM","HARD"]},
            "difficulty_conf": {"type": "number"},
            "timing": {"type": "string", "enum": ["NOW","LATER"]},
            "timing_conf": {"type": "number"}},
            "required": ["role","role_conf","difficulty","difficulty_conf","timing","timing_conf"]}}
    req = urllib.request.Request(CLASSIFIER["endpoint"],
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    r = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    dt = time.time() - t0
    d = json.loads(r["message"]["content"])
    d["latency_s"] = round(dt, 3)
    return d
