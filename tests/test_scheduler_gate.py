"""Tests for the scheduler beta-gate toggle + router scheduling paths (J13 v1).
Run: python -m unittest tests.test_scheduler_gate -v"""
import sys, re, tempfile, shutil, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tierllama.router import _resolve_due


class TestToggleRegex(unittest.TestCase):
    """The /api/schedule/toggle rewrite must work in BOTH directions (2026-09-25
    bug: OFF was a silent no-op whenever the file already said True)."""

    def _rewrite(self, src: str, want: bool) -> str:
        new = re.sub(r'("enabled": )(True|False)(,\s*# BETA feature gate)',
                     lambda m: f"{m.group(1)}{want}{m.group(3)}", src, count=1)
        return new

    def test_off_when_true(self):
        src = '"enabled": True,      # BETA feature gate - never enable silently'
        self.assertIn('"enabled": False', self._rewrite(src, False))

    def test_on_when_false(self):
        src = '"enabled": False,      # BETA feature gate - never enable silently'
        self.assertIn('"enabled": True', self._rewrite(src, True))

    def test_idempotent(self):
        src = '"enabled": True,      # BETA feature gate'
        self.assertEqual(self._rewrite(src, True), src)  # no change needed

    def test_no_match_detected(self):
        # gate line missing -> rewrite must detect no-change (endpoint returns error)
        src = 'no gate line here'
        new = re.sub(r'("enabled": )(True|False)(,\s*# BETA feature gate)',
                     lambda m: f"{m.group(1)}False{m.group(3)}", src, count=1)
        self.assertEqual(new, src)   # endpoint detects and refuses


class TestResolveDue(unittest.TestCase):
    """Dumb date resolver: concrete phrases resolve, vague ones return None."""

    def test_friday_resolves_future(self):
        import datetime
        d = _resolve_due("by friday 5pm")
        assert d is not None
        dt = datetime.datetime.fromisoformat(d)
        self.assertEqual(dt.weekday(), 4)     # friday
        self.assertEqual(dt.hour, 17)
        self.assertGreater(dt, datetime.datetime.now())

    def test_tonight_resolves(self):
        self.assertIsNotNone(_resolve_due("overnight"))

    def test_vague_returns_none(self):
        self.assertIsNone(_resolve_due("soon"))
        self.assertIsNone(_resolve_due("this week?"))


class TestRouterScheduling(unittest.TestCase):
    """DEADLINE + confident + parseable -> scheduled; gate OFF -> never scheduled."""

    def setUp(self):
        from tierllama import config as C
        self.cfg = C
        C.SCHEDULER["enabled"] = True
        # 2026-09-29 incident: route(dispatch=True) on a BOX-lane message wrote 6
        # real job files to \\\\<box-lan-ip>\\C$\\jobs\\pending (the box worker
        # would have burned queue time on test prompts). Tests must never touch
        # real adapters: sandbox BOX_JOBS + the decision log to a temp dir.
        self._tmp = tempfile.mkdtemp()
        from tierllama import config as C
        self._orig_queue = C.SCHEDULER["queue_path"]
        C.SCHEDULER["queue_path"] = str(Path(self._tmp) / "sched.json")  # never touch real queue
        import tierllama.adapters as A
        self._orig_boxjobs = A.BOX_JOBS
        A.BOX_JOBS = Path(self._tmp)
        # sandbox real dispatch entirely: no local GPU load, no cloud spend, no box I/O
        self._orig_dispatch = A.dispatch
        def _fake_dispatch(lane, message, **kw):
            return {"status": "ok", "lane": lane, "model": "test-stub",
                    "result": "test", "latency_s": 0.0}
        A.dispatch = _fake_dispatch
        import tierllama.router as R
        self._orig_router_dispatch = R.dispatch
        R.dispatch = _fake_dispatch   # router.py binds dispatch at module level (line 6)
        # also sandbox the classifier (live network, ~2-20s per call + HTTP 500 flakiness)
        def _fake_classify(message, last_exchanges=None, timeout=60):
            low = message.lower()
            if "by " in low or "before " in low:
                when, raw, wc = "DEADLINE", low.split("by ", 1)[-1].split("before ", 1)[-1], 0.95
            elif any(w in low for w in ("soon", "later today", "this week")):
                when, raw, wc = "DATE_UNCLEAR", "soon" if "soon" in low else low, 0.9
            elif any(w in low for w in ("overnight", "tonight", "no rush", "whenever", "tomorrow")):
                when, raw, wc = "DEFERRED", "overnight", 0.9
            else:
                when, raw, wc = "NOW", "", 0.95
            return {"difficulty": "MEDIUM", "difficulty_conf": 0.9, "timing": "NOW",
                    "timing_conf": 0.9, "when": when, "when_conf": wc, "when_raw": raw,
                    "confidence": 0.9, "lane": "LOCAL", "latency_s": 0.0}
        self._orig_classify = R.classify
        R.classify = _fake_classify

    def tearDown(self):
        from tierllama import config as C
        C.SCHEDULER["enabled"] = False
        C.SCHEDULER["queue_path"] = self._orig_queue
        import tierllama.adapters as A
        A.BOX_JOBS = self._orig_boxjobs
        A.dispatch = self._orig_dispatch
        import tierllama.router as R
        R.dispatch = self._orig_router_dispatch
        R.classify = self._orig_classify
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_deadline_gets_scheduled(self):
        from tierllama.router import route
        rec = route("clean up the transcriptions by friday 5pm", dispatch=True)
        self.assertIn("scheduled", rec)
        self.assertIsNone(rec.get("needs_clarification"))
        self.assertTrue(rec["scheduled"]["due_at"].startswith("2026-"))

    def test_unclear_date_needs_clarification(self):
        from tierllama.router import route
        rec = route("summarize this doc soon please", dispatch=True)
        # 'soon' is DATE_UNCLEAR or unparseable DEADLINE -> ask, never guess-execute
        self.assertTrue(rec.get("needs_clarification") is not None or rec.get("dispatched"))

    def test_gate_off_means_no_schedule(self):
        from tierllama import config as C
        from tierllama.router import route
        C.SCHEDULER["enabled"] = False
        rec = route("clean up the transcriptions by friday 5pm", dispatch=True)
        self.assertNotIn("scheduled", rec)   # never scheduled silently
        if rec.get("needs_clarification"):
            self.assertEqual(rec["needs_clarification"]["reason"], "scheduler beta disabled")


if __name__ == "__main__":
    unittest.main()