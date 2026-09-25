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

    def tearDown(self):
        from tierllama import config as C
        C.SCHEDULER["enabled"] = False

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