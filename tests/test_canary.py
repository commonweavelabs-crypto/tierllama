"""Tests for tierllama/canary.py (J14 task 4: canary probes, consent-gated).
Run: python -m unittest tests.test_canary -v"""
import sys, unittest, tempfile, shutil, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tierllama import canary as K
from tierllama.canary import should_canary, canary_tier, grade_usable, CanaryTracker
import tierllama.config as cfg


def _cap_on(pct=100):
    cfg.CAPABILITY["enabled"] = True
    cfg.CAPABILITY["canary_pct"] = pct

def _gate_off():
    cfg.CAPABILITY["enabled"] = False
    cfg.CAPABILITY["canary_pct"] = 0


class TestSampling(unittest.TestCase):
    def setUp(self): _gate_off()
    def tearDown(self): _gate_off()

    def test_gate_off_never_samples(self):
        # consent rule: gate OFF -> canary NEVER fires, regardless of pct
        _gate_off()
        cfg.CAPABILITY["canary_pct"] = 100
        self.assertFalse(should_canary("HARD"))
        self.assertFalse(should_canary("HARD", rng=0.0))   # even guaranteed roll

    def test_pct_zero_never_samples_even_when_enabled(self):
        _gate_off(); _gate_on_no_pct = None
        cfg.CAPABILITY["enabled"] = True
        cfg.CAPABILITY["canary_pct"] = 0
        self.assertFalse(should_canary("HARD"))

    def test_hard_only_sampling(self):
        _canary(50)
        self.assertTrue(should_canary("HARD", rng=0.0))
        self.assertFalse(should_canary("MEDIUM", rng=0.0))  # only HARD traffic sampled
        self.assertFalse(should_canary("EASY", rng=0.0))

    def test_percentage_respected(self):
        _canary(50)
        results = [should_canary("HARD", rng=r) for r in (0.0, 0.4, 0.6, 0.9)]
        self.assertEqual(results, [True, True, False, False])


def _canary(pct):
    cfg.CAPABILITY["enabled"] = True
    cfg.CAPABILITY["canary_pct"] = pct


class TestTier(unittest.TestCase):
    def test_one_step_down(self):
        self.assertEqual(canary_tier("HARD"), "MEDIUM")
        self.assertEqual(canary_tier("EXPERT"), "HARD")

    def test_never_below_easy(self):
        self.assertEqual(canary_tier("EASY"), "EASY")


class TestGrading(unittest.TestCase):
    def test_empty_is_unusable(self):
        self.assertFalse(grade_usable("anything", ""))
        self.assertFalse(grade_usable("anything", "  "))

    def test_error_prefix_unusable(self):
        self.assertFalse(grade_usable("anything", "Error: connection refused"))

    def test_bench_probe_graded_deterministically(self):
        from tierllama.bench import PROBES
        easy_prompt = PROBES[0][1]
        self.assertTrue(grade_usable(easy_prompt, "391"))
        self.assertFalse(grade_usable(easy_prompt, "banana"))

    def test_generic_content_usable(self):
        self.assertTrue(grade_usable("write a summary", "Here is a summary of the document..."))


class TestTracker(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tracker = K.CanaryTracker(Path(self.tmp) / "canary.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_promotion_after_threshold(self):
        k = "q@localhost|MEDIUM|NOW|NOW"
        self.assertFalse(self.tracker.should_promote(k))
        for _ in range(3):   # canary_successes = 3
            self.tracker.note(k, usable=True, now_iso="2026-09-29T14:00:00")
        self.assertTrue(self.tracker.should_promote(k))
        st = self.tracker.promote(k, "HARD", "MEDIUM", "2026-09-29T15:00:00")
        self.assertEqual(st["promoted"]["from"], "HARD")
        self.assertEqual(st["successes"], 0)   # counter resets after promotion

    def test_failures_do_not_promote(self):
        k = "q@localhost|MEDIUM|NOW|NOW"
        for _ in range(5):
            self.tracker.note(k, usable=False, now_iso="2026-09-29T14:00:00")
        self.assertFalse(self.tracker.should_promote(k))


if __name__ == "__main__":
    unittest.main()