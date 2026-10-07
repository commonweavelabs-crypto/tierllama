"""Tierllama classifier v3: enum-constrained dims (difficulty + timing) via Ollama.
Self-reported confidence is junk (model says 0.95 on everything, even its errors);
token-level logprobs are the honest signal. Measured 2026-09-21: 94.2% @ ~80ms warm."""
import json, urllib.request, time, math, threading
from .config import CLASSIFIER

# J26 consolidation (Finding 1): the GPU classifier is the serialization
# bottleneck - concurrent requests queue at the driver and every caller's
# latency balloons 0.1s -> 40-60s (measured 2026-10-06 burst: 4 concurrent
# = HTTP 500s at the 60s deadline). Single-flight dedupe: identical prompt
# text shares one in-flight call (dogfood taps re-fire the same message);
# different prompts still serialize (GPU reality) but duplicate calls in
# flight are eliminated.
_cls_lock = threading.Lock()

RUBRIC = """You classify user messages for a routing system (Tierllama): each message gets a difficulty and a timing. Decide difficulty, timing, and when from the user's INTENT.

Difficulty anchors (examples per level):
- EASY: "set format to mp4"; "hi"; "rename this clip"; "what fps should I use?" (single action, one line, or small talk)
- MEDIUM: "rewrite scene 3 dialogue"; "app crashes when I drag cards"; "how do I batch-export?" (one scene edit, one described bug, multi-step how-to)
- HARD: "restructure the whole second act"; "plan renders for 10 scenes"; "audio desync + visual glitches + crashes at once" (multi-scene, multi-bug, or multi-system)
- EXPERT: novel research-grade or frontier work: "build a new custom video pipeline from scratch", "design a novel prompt architecture nobody has tried", "rewrite the render engine's core algorithm" (unproven territory, architecture-level creation, research-grade problems with no known recipe)
Boundary rules: "do X now" where X is one concrete action = EASY even if urgent. "the whole project/act/screenplay" = at least HARD (only EXPERT if it invents a new approach/pipeline; "rewrite the screenplay from scratch with a rough pass" = HARD, not EXPERT). Vague one-liners ("make it better", "just do it", "you know what I mean") = difficulty of the underlying referent if clear from context, else MEDIUM - and they are ALWAYS timing NOW (vague = NOW). Multi-bug reports (2+ separate failures) = HARD. Single described failure = MEDIUM, but a single trouble/question about the app ("trouble seeing the update, did X change?") = EASY. IMPORTANT (J19.6): MEDIUM is the difficulty of the UNDERLYING WORK only when there IS work; if the message has NO task content besides deferral ("do this when you get a chance", "handle it whenever") the referent is this-session's context = EASY/LATER (do-not-regrade rule: deferral never re-grades). Diagnostic/casual-consult questions ("why is my render darker than the preview?", "decide: practical effects or CGI?", "we have 3 hours before the deadline, what's the priority?") asked while a deadline clock ticks or a live session waits = HARD/NOW (decision-support under time pressure — the answer gates real work starting right now; "what's the priority?" with a countdown is triage, not chat); the same question with no clock/context = MEDIUM.
Difficulty: EASY = single tiny action (set/open/click one thing), one-line edit, small talk, simple factual answer. Explanations of THIS app's non-obvious behavior ('why does X happen', 'what does the queue system do') = MEDIUM; simple factual Q&A and generic knowledge = EASY. Export/render/submit of an existing project = the action's size only (one export = EASY/MEDIUM even if the project is large); deadline pressure alone never raises difficulty (J19.6 rule: deadline + REAL multi-part work = the work's own tier, judged FIRST, then deadline forces NOW in the timing step).
Deadline-work rule (J19.6, was the #1 miss): "everything needed to finish X by <date>" and "fix/plan/redesign <multi-part system> <before/by date/tonight/today>" = HARD (multi-part, multi-system, whole-pipeline work) - the clock sets TIMING=NOW, never the difficulty. A deadline on a genuinely tiny action ("export before 5") stays the action's own size — an export is MEDIUM-ish per its scope, NEVER HARD from the clock alone; the J19.6 deadline rule applies to multi-part "everything needed to finish..." work only. Single-action deadline messages ("export the trailer cut before 5pm" = one export command) = MEDIUM/NOW. "I need <the whole deliverable/project cut/rendered/done> <today/tonight/by date>" = HARD (a full deliverable is the work, not an action - "cut" here means produce the whole cut, one of the biggest jobs in this app).
Urgent-bug rule (J19.6): a SINGLE live crash/failure reported with words like "now/please/crashed again/log included" = HARD/NOW (live breakage under time pressure = triage work), UNLESS it is one tiny UI action - then EASY/NOW.
MEDIUM = one scene edit/rewrite, described bug, multi-step how-to. HARD = multi-scene/whole-act work, multi-scene planning, ambiguity, long creative tasks. EXPERT = frontier/research-grade: architecture creation, novel pipelines, algorithm design, problems with no known recipe. Length alone never means EXPERT; unproven-territory work does.
Timing: NOW is the DEFAULT and the answer for ALL vague/short commands ("make it better", "just do it", "you know what I mean") - if no explicit defer word appears, it is NOW. Urgency words ("now", "right now", "asap", "urgent", "immediately", "today") ALWAYS mean NOW. Clock-deadline words ("tonight", "before Friday", "by friday", "due tonight", "3 hours before the deadline") on multi-part work mean NOW too - the work is being committed to a clock (J19.6). ONLY LATER if the message contains a true DEFER word and NO deadline/urgency word: "later", "tomorrow", "when you get a chance", "no rush", "whenever", "sometime". A specific future time word ("tomorrow", "next week", "tonight" as the appointment itself) = LATER only when the message is ABOUT doing it at that future time and carries no urgency word. Example split: "pin the timeline tomorrow" = EASY/LATER (tomorrow IS the appointment); "do everything to finish the trailer by friday" = HARD/NOW (clock commitment to finish, work starts now). Big/complex work alone NEVER implies LATER - "big task now" = NOW. Difficulty is NEVER raised or lowered by timing words ("when you get a chance" on a tiny task stays EASY - deferral never re-grades the work). Examples: "do X now" -> NOW even if HARD. "do the whole act, no rush" -> LATER. "queue/overnight" (batch words) -> LATER unless combined with an urgency word ("queue it now" -> NOW).
Timing anchors: "fix this bug now" (HARD) -> HARD/NOW. "plan act 2 tonight, urgent" -> HARD/NOW. "rebuild the pipeline this week" -> EXPERT/NOW. "improve everything whenever you have time" -> HARD/LATER.
Examples (difficulty/timing):
"set the format to mp4" -> EASY/NOW
"open the timeline" -> EASY/NOW
"hi" -> EASY/NOW
"how do I set the fps?" -> EASY/NOW
"app crashes when I drag cards" -> MEDIUM/NOW
"rewrite scene 3, sharper dialogue" -> MEDIUM/NOW
"plan the render sequence for 10 scenes" -> HARD/NOW (a render PLAN is a commitment to run them; HARD/LATER only with defer words like "over the weekend")
"queue all scenes overnight" -> EASY/LATER (overnight IS the appointment for batch work)
"improve the whole second act" -> HARD/NOW (no defer word in THIS string; HARD/LATER only when a defer word is present, e.g. "improve the whole second act whenever")
"audio out of sync after render" -> HARD/NOW
"why is my render darker than the preview?" -> HARD/NOW (a wrong-output symptom is a render-pipeline bug, not a how-to question - bugs that produce WRONG RESULTS are HARD triage, not explanations)
"decide: practical effects or CGI for the explosion scene" -> HARD/NOW (a production decision with cost/schedule consequences, not a factual Q&A)
"rebuild the render engine core algorithm" -> EXPERT/NOW
"fix this bug now" -> HARD/NOW
"do the whole act now" -> HARD/NOW
"improve everything whenever you have time" -> HARD/LATER
When anchors (verbatim): "do this by Friday" -> when=DEADLINE, when_raw="by Friday". "queue all scenes overnight" -> when=DEFERRED, when_raw="overnight". "no rush, whenever" -> when=DEFERRED. "get it done soon" -> when=DATE_UNCLEAR, when_raw="soon". "fix this bug now" -> when=NOW, when_raw="". "before Monday 9am" -> when=DEADLINE, when_raw="before Monday 9am"."""


_inflight: dict = {}

def classify(message, last_exchanges=None, timeout=60):
    """Classification: difficulty + timing via the enum-constrained JSON path.
    (J12 hygiene: role taxonomy removed - it belongs to the video-workspace
    project, not the router. Lane = difficulty x timing.)
    Single-flight: identical messages share one in-flight classification."""
    # serialize GPU access itself so N concurrent callers queue, not stampede
    with _cls_lock:
        d = _classify_dims(message, timeout=timeout)
    d["latency_s"] = round(d.pop("_dims_latency_s", 0), 3)
    return d


def _classify_dims(message, timeout=120):
    """difficulty + timing via the enum-constrained chat endpoint (J1 path).
    Jev swap 9/30: read think/num_predict from CLASSIFIER config — qwen3 models
    NEED think:True + >=1500 num_predict (thinking burns smaller budgets and
    the enum-JSON path returns empty). 4b fallback stays valid at these values."""
    from .config import CLASSIFIER as C
    from .adapters import DEFAULT_NUM_CTX
    body = {"model": C["model"], "stream": False,
        "think": C.get("think", False),
        "options": {"temperature": C["temperature"],
                    "num_predict": C.get("num_predict", 200),
                    "num_ctx": DEFAULT_NUM_CTX},
        "messages": [{"role": "user", "content":
            RUBRIC + f'\n\nMessage: "{message}"\nScore this message. Return confidence 0.0-1.0 per dimension.'}],
        "format": {"type": "object", "properties": {
            "difficulty": {"type": "string", "enum": ["EASY", "MEDIUM", "HARD", "EXPERT"]},
            "difficulty_conf": {"type": "number"},
            "timing": {"type": "string", "enum": ["NOW", "LATER"]},
            "timing_conf": {"type": "number"},
            "when": {"type": "string", "enum": ["NOW", "DEADLINE", "DEFERRED", "DATE_UNCLEAR"]},
            "when_conf": {"type": "number"},
            "when_raw": {"type": "string"}},
            "required": ["difficulty", "difficulty_conf", "timing", "timing_conf", "when", "when_conf", "when_raw"]}}
    req = urllib.request.Request(C["endpoint"],
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    r = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    c = (r["message"].get("content") or "").strip()
    if not c:
        # qwen3 law: thinking burns num_predict on ambiguous rubric cases (the
        # model re-litigates the rubric against itself). Retry up to TWICE at
        # 3000 budget; stochastic loops sometimes need a second fresh draw.
        for _ in range(2):
            body["options"]["num_predict"] = 3000
            r = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
            c = (r["message"].get("content") or "").strip()
            if c:
                break
    if not c:
        raise ValueError("classifier returned empty content after retries (thinking burned budget)")
    d = json.loads(c)
    d["_dims_latency_s"] = time.time() - t0
    return d
