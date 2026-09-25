"""Tests for tierllama/health.py (J12+ T1, PAIR-derived EWMA pressure).
Run: python -m unittest tests.test_health -v"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tierllama.health import NodePressure, FleetPressure, _band, _pressure_with_hysteresis


class TestBand(unittest.TestCase):
    def test_upward_bands(self):
        self.assertEqual(_band(0.39), 0)
        self.assertEqual(_band(0.40), 1)
        self.assertEqual(_band(0.69), 1)
        self.assertEqual(_band(0.70), 2)
        self.assertEqual(_band(0.84), 2)
        self.assertEqual(_band(0.85), 3)


class TestHysteresis(unittest.TestCase):
    def test_no_thrash_on_boundary(self):
        # node at pressure 2 (EWMA just past 0.70); util wobbles 0.68<->0.72
        # downward release needs < 0.65, so 0.66-0.72 must HOLD at 2
        self.assertEqual(_pressure_with_hysteresis(0.66, 2), 2)
        self.assertEqual(_pressure_with_hysteresis(0.65, 2), 2)   # exactly at lower edge holds
        self.assertEqual(_pressure_with_hysteresis(0.64, 2), 1)   # below edge -> releases to plain band
        self.assertEqual(_pressure_with_hysteresis(0.72, 2), 2)   # stays
    def test_release_from_3(self):
        self.assertEqual(_pressure_with_hysteresis(0.81, 3), 3)   # <0.80 would release; 0.81 holds
        self.assertEqual(_pressure_with_hysteresis(0.79, 3), 2)   # below 0.80 -> plain band -> 2


class TestNodePressure(unittest.TestCase):
    def test_first_sample_anchors(self):
        n = NodePressure("a")
        # PAIR behavior: first sample anchors EWMA directly
        self.assertEqual(n.update(0.9, now=100.0), 3)

    def test_ewma_smooths(self):
        n = NodePressure("a")
        n.update(0.0, now=0)
        # burst to 100%: EWMA = 0.35*1.0 = 0.35 -> still band 0 (<0.40)
        self.assertEqual(n.update(1.0, now=1), 0)
        # second burst: 0.35*1 + 0.65*0.35 = 0.5775 -> band 1
        self.assertEqual(n.update(1.0, now=2), 1)

    def test_never_sampled_is_neutral(self):
        n = NodePressure("a")
        self.assertEqual(n.pressure(now=1000), 1)

    def test_stale_going_neutral(self):
        n = NodePressure("a")
        n.update(0.9, now=100)
        self.assertEqual(n.pressure(now=105), 3)     # fresh: 3
        self.assertEqual(n.pressure(now=111), 1)     # >10s: neutral
        # recovery: fresh sample resumes real pressure
        self.assertEqual(n.update(0.9, now=112), 3)

    def test_0_100_scale_accepted(self):
        n = NodePressure("a")
        self.assertEqual(n.update(90, now=100), 3)   # 90/100 -> 0.9


class TestFleetPressure(unittest.TestCase):
    def test_ranking_actual(self):
        f = FleetPressure()
        f.feed("n-busy", 0.95, now=100)
        f.feed("n-idle", 0.05, now=100)
        r = f.ranking(now=101)
        self.assertEqual([d["node_id"] for d in r], ["n-idle", "n-busy"])
        self.assertEqual(r[0]["rank"], 0)

    def test_never_sampled_neutral_mid_rank(self):
        f = FleetPressure()
        f.feed("n-idle", 0.05, now=100)
        f.node("n-unknown")            # never fed
        f.feed("n-busy", 0.95, now=100)
        r = f.ranking(now=101)
        self.assertEqual([d["node_id"] for d in r], ["n-idle", "n-unknown", "n-busy"])
        self.assertEqual(r[1]["pressure"], 1)

    def test_snapshot_stale_flag(self):
        f = FleetPressure()
        f.feed("a", 0.5, now=100)
        s = f.snapshot(now=120)
        self.assertTrue(s["a"]["stale"])
        self.assertEqual(s["a"]["pressure"], 1)


if __name__ == "__main__":
    unittest.main()