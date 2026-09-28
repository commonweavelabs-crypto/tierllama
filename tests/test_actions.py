"""Tests for tierllama/actions.py (J13 v2 task 1: per-action confidence gates).
Run: python -m unittest tests.test_actions -v"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tierllama import actions as A


class TestThresholdTable(unittest.TestCase):
    def test_cost_ordering(self):
        # the whole point: query < schedule < destructive (cost of being wrong)
        self.assertLess(A.action_conf_threshold("query"), A.action_conf_threshold("schedule"))
        self.assertLess(A.action_conf_threshold("schedule"), A.action_conf_threshold("destructive"))

    def test_exact_values(self):
        self.assertEqual(A.action_conf_threshold("query"), 0.60)
        self.assertEqual(A.action_conf_threshold("schedule"), 0.85)
        self.assertEqual(A.action_conf_threshold("destructive"), 0.95)

    def test_unknown_action_safest(self):
        # unknown action keys must fall to the SAFEST threshold, never the loosest
        self.assertEqual(A.action_conf_threshold("teleport"), 0.95)
        self.assertEqual(A.action_conf_threshold(""), 0.95)
        self.assertEqual(A.action_conf_threshold(None), 0.95)


class TestGate(unittest.TestCase):
    def test_proceed_at_or_above(self):
        self.assertEqual(A.gate("query", 0.60), "proceed")
        self.assertEqual(A.gate("query", 0.95), "proceed")
        self.assertEqual(A.gate("schedule", 0.85), "proceed")

    def test_below_is_always_clarify(self):
        # clarify-or-ask absolute: below threshold NEVER proceeds
        self.assertEqual(A.gate("query", 0.5999), "clarify")
        self.assertEqual(A.gate("schedule", 0.84), "clarify")
        self.assertEqual(A.gate("destructive", 0.9499), "clarify")

    def test_boundary_crossing(self):
        # same confidence, different action -> different verdicts (per-action!)
        self.assertEqual(A.gate("query", 0.70), "proceed")
        self.assertEqual(A.gate("schedule", 0.70), "clarify")
        self.assertEqual(A.gate("destructive", 0.70), "clarify")


class TestResolveAction(unittest.TestCase):
    def test_deadline_is_schedule(self):
        self.assertEqual(A.resolve_action("DEADLINE", "LOCAL"), "schedule")
        self.assertEqual(A.resolve_action("DEADLINE", None), "schedule")

    def test_dispatch_is_query_scale(self):
        self.assertEqual(A.resolve_action("NOW", "LOCAL"), "query")
        self.assertEqual(A.resolve_action("NOW", "CLOUD_HARD"), "query")
        self.assertEqual(A.resolve_action(None, "BOX"), "query")

    def test_unknown_lane_defaults_query(self):
        self.assertEqual(A.resolve_action(None, "NOT_A_LANE"), "query")


if __name__ == "__main__":
    unittest.main()