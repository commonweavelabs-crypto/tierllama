"""Tests for tierllama/capability.py (J14 task 2+3: ledger + gradual bump rule).
Run: python -m unittest tests.test_capability -v"""
import sys, unittest, tempfile, shutil, json
from pathlib import Path
from datetime import datetime, timedelta
sys.path.insert(0, str(Path(__file__).parent.parent))

from tierllama import capability as C
from tierllama.capability import Ledger, BumpState, class_key, bump_tier, evaluate_bump

NOW = datetime(2026, 9, 29, 14, 0)
KEY_ARGS = dict(bench_key="qwen3:4b@localhost", difficulty="MEDIUM", timing="NOW", when="NOW")
KEY = class_key(KEY_ARGS["bench_key"], "MEDIUM", "NOW", "NOW")


def _ev(outcome, lat=1.0, at=None):
    return dict(KEY_ARGS, outcome="failure", latency_s=lat, ts=(at or NOW).isoformat(timespec="seconds"))


class TestLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.log = Path(self.tmp) / "cap.jsonl"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_key_includes_all_dimensions(self):
        k1 = class_key("q@localhost", "MEDIUM", "NOW", "NOW")
        k2 = class_key("q@localhost", "MEDIUM", "NOW", "DEADLINE")
        k3 = class_key("q@box", "MEDIUM", "NOW", "NOW")
        self.assertEqual(len({k1, k2, k3}), 3)   # machine + all dims distinguish

    def test_rolling_window(self):
        from tierllama import config as cfg
        old = cfg.CAPABILITY["window_n"]
        cfg.CAPABILITY["window_n"] = 5
        try:
            led = Ledger(self.log)
            for _ in range(8):
                led.record(_ev("x"))
            self.assertEqual(len(led.events[KEY]), 5)
        finally:
            cfg.CAPABILITY["window_n"] = old

    def test_stats_and_streak(self):
        led = Ledger(self.log)
        for i in range(7):
            ev = _ev("x")
            ev["outcome"] = "success" if i in (0, 3) else "failure"
            led.record(ev)
        st = led.stats(KEY)
        self.assertEqual(st["samples"], 7)
        self.assertEqual(st["failures"], 5)
        self.assertEqual(st["failure_rate"], round(5/7, 3))
        # streak: last event failure, before it failure, before that success -> 2? events: F F S F F F F
        # order recorded: 7 events alternating at idx0=S? recorded: i0 S, i1 F, i2 S, i3 F... let me recompute:
        # i in 0..6: success if i in (0,3): S F F S F F F? no: i=0 S, 1 F, 2 F?? i in (0,3): 0 S,1 F,2 F,3 S,4 F,5 F,6 F
        self.assertEqual(led.consecutive_failures(KEY), 3)   # tail F F F

    def test_success_breaks_streak(self):
        led = Ledger(self.log)
        led.record(_ev("x"))                                  # F
        ok = _ev("x"); ok["outcome"] = "success"
        led.record(ok)                                        # S breaks streak
        led.record(_ev("x")); led.record(_ev("x"))            # F F
        self.assertEqual(led.consecutive_failures(KEY), 2)


class TestBumpLadder(unittest.TestCase):
    def test_one_step_at_a_time(self):
        self.assertEqual(bump_tier("EASY", 1), "MEDIUM")
        self.assertEqual(bump_tier("MEDIUM", 1), "HARD")

    def test_never_global_jumps(self):
        # bump_level forced high still caps at 1 step in evaluate; bump_tier honors level but caller uses 1
        self.assertEqual(bump_tier("EASY", 2), "HARD")   # utility only; rule passes level=1
        self.assertEqual(bump_tier("HARD", 1), "EXPERT")

    def test_unknown_tier_unchanged(self):
        self.assertEqual(bump_tier("WEIRD", 1), "WEIRD")


class TestBumpRule(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.log = Path(self.tmp) / "cap.jsonl"
        self.state_path = Path(self.tmp) / "state.json"
        self.old_cap = dict(__import__("tierllama.config", fromlist=["CAPABILITY"]).CAPABILITY)
        import tierllama.config as cfg
        cfg.CAPABILITY.update({"min_samples": 10, "bump_after_failures": 3,
                               "cooldown_h": 12, "max_moves_per_day": 1})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        import tierllama.config as cfg
        cfg.CAPABILITY.clear()
        cfg.CAPABILITY.update(self.old_cap)

    def _ledger_with(self, outcomes):
        led = Ledger(self.log)
        for o in outcomes:
            ev = _ev("x"); ev["outcome"] = o
            led.record(ev, persist=False)
        return led

    def test_no_bump_below_min_samples(self):
        led = self._ledger_with(["failure"] * 5)
        d = C.evaluate_bump(led, BumpState(self.state_path), now=NOW,
                            current_tier="MEDIUM", **KEY_ARGS)
        self.assertFalse(d["would_bump"])
        self.assertIn("min_samples", d["reason"])

    def _ledger_with(self, outcomes):
        led = Ledger(self.log)
        for o in outcomes:
            ev = _ev("x"); ev["outcome"] = o
            led.record(ev, persist=False)
        return led

    def test_bump_after_consecutive_failures(self):
        led = self._ledger_with(["success"] * 7 + ["failure"] * 3)   # 10 samples, streak 3
        d = C.evaluate_bump(led, BumpState(self.state_path), now=NOW,
                            current_tier="MEDIUM", **KEY_ARGS)
        self.assertTrue(d["would_bump"])
        self.assertEqual(d["from_tier"], "MEDIUM")
        self.assertEqual(d["to_tier"], "HARD")      # +1 only, never global jump

    def test_unknown_does_not_break_streak_but_success_does(self):
        led = self._ledger_with(["success"] * 6 + ["failure"] + ["unknown"] + ["failure"] * 3)
        d = C.evaluate_bump(led, BumpState(self.state_path), now=NOW,
                            current_tier="MEDIUM", **KEY_ARGS)
        self.assertTrue(d["would_bump"])   # unknowns ignored, streak still 4? -> failures after success: 5 -> >=3

    def test_cooldown_blocks_second_move(self):
        led = self._ledger_with(["failure"] * 10)
        st = BumpState(self.state_path)
        st.apply_bump(KEY, "MEDIUM", "HARD", "initial move", datetime(2026, 9, 28, 23, 0))
        # eval next morning 09:00: 10h since move (<12h cooldown) but different day (rate OK) -> blocked
        d2 = C.evaluate_bump(led, st, now=datetime(2026, 9, 29, 9, 0), current_tier="MEDIUM", **KEY_ARGS)
        self.assertFalse(d2["would_bump"])
        self.assertIn("cooldown", d2["reason"])
        # 25h after the move: cooldown passed, new day -> allowed again
        d3 = C.evaluate_bump(led, st, now=datetime(2026, 9, 30, 0, 30), current_tier="MEDIUM", **KEY_ARGS)
        self.assertTrue(d3["would_bump"])

    def test_rate_limit_one_move_per_day(self):
        led = self._ledger_with(["failure"] * 10)
        st = BumpState(self.state_path)
        st.apply_bump(KEY, "MEDIUM", "HARD", "earlier today", NOW - timedelta(hours=1))
        d = C.evaluate_bump(led, st, now=NOW, current_tier="MEDIUM", **KEY_ARGS)
        self.assertFalse(d["would_bump"])
        self.assertIn("rate limit", d["reason"])

    def test_gate_off_means_dry_run_not_routing(self):
        # the DECISION is computed; routing change is the CALLER's gate. Verify config gate is OFF:
        from tierllama import config as cfg
        self.assertFalse(cfg.CAPABILITY["enabled"])


from datetime import timedelta  # noqa: E402 (used in tests above)

if __name__ == "__main__":
    unittest.main()