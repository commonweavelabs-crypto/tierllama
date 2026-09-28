"""J13 v2 task 1: golden boundary cases for per-action thresholds.
These run through the LIVE router with a stubbed classifier (sandboxed
dispatch — never touches box/queues/network). Run: python -m unittest tests.test_action_gate_golden -v"""
import sys, unittest, tempfile, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _route_with(when, when_conf, dispatch=True):
    """Route with a canned classifier result (stubbed live network)."""
    import tierllama.router as R
    from tierllama import config as C
    old_q = C.SCHEDULER["queue_path"]
    tmp = tempfile.mkdtemp()
    C.SCHEDULER["queue_path"] = str(Path(tmp) / "sched.json")
    orig_classify = R.classify
    orig_dispatch = R.dispatch
    orig_escalate = R.escalate
    R.classify = lambda m, last_exchanges=None, timeout=60: {
        "difficulty": "MEDIUM", "difficulty_conf": 0.95, "timing": "NOW",
        "timing_conf": 0.95, "when": when, "when_conf": when_conf,
        "when_raw": "by friday 5pm" if when == "DEADLINE" else "",
        "confidence": 0.95, "lane": "CLOUD_MEDIUM", "latency_s": 0.0}
    R.dispatch = lambda lane, message, **kw: {"status": "ok", "lane": lane,
                                              "model": "stub", "result": "x", "latency_s": 0.0}
    R.escalate = lambda record, message, lane: ({"status": "ok"}, lane)  # no live ladder
    orig_enabled = C.SCHEDULER["enabled"]
    C.SCHEDULER["enabled"] = True
    try:
        return R.route("test message", dispatch=dispatch)
    finally:
        R.classify = orig_classify
        R.dispatch = orig_dispatch
        R.escalate = orig_escalate
        C.SCHEDULER["enabled"] = orig_enabled
        C.SCHEDULER["queue_path"] = old_q
        shutil.rmtree(tmp, ignore_errors=True)


class TestScheduleGate(unittest.TestCase):
    """schedule action threshold = 0.85. Boundary behavior via the live router."""

    def test_at_threshold_schedules(self):
        rec = _route_with("DEADLINE", 0.85)
        self.assertIn("scheduled", rec)
        self.assertNotIn("needs_clarification", rec)

    def test_below_threshold_clarifies(self):
        rec = _route_with("DEADLINE", 0.84)
        self.assertNotIn("scheduled", rec)   # never silently scheduled
        self.assertEqual(rec["needs_clarification"]["reason"], "below per-action threshold (schedule)")
        self.assertEqual(rec["needs_clarification"]["confidence"], 0.84)
        self.assertIn("guess", rec["needs_clarification"])   # guess surfaced, not executed

    def test_way_below_clarifies(self):
        rec = _route_with("DEADLINE", 0.30)
        self.assertIn("needs_clarification", rec)
        self.assertNotIn("scheduled", rec)


class TestQueryGate(unittest.TestCase):
    """query action threshold = 0.60 — dispatches at confidence above 0.60."""

    def test_query_conf_does_not_gate_dispatch(self):
        # NOW-lane work at 0.65 confidence proceeds (query threshold), the
        # global classifier confidence gate (0.75 -> FALLBACK) is separate.
        rec = _route_with("NOW", 0.65)
        self.assertNotIn("needs_clarification", rec)
        self.assertEqual(rec.get("dispatched"), True)


if __name__ == "__main__":
    unittest.main()