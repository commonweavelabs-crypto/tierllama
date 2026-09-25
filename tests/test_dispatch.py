"""Tests for tierllama/dispatch.py (J12+ T4, PAIR-derived reservations + bounds).
Run: python -m unittest tests.test_dispatch -v"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tierllama import dispatch as D


class TestReservations(unittest.TestCase):
    def test_take_release(self):
        r = D.Reservations()
        self.assertEqual(r.take("a"), 1)
        self.assertEqual(r.take("a"), 2)
        self.assertEqual(r.pending("a"), 2)
        r.release("a"); r.release("a"); r.release("a")
        self.assertEqual(r.pending("a"), 0)

    def test_move(self):
        r = D.Reservations()
        r.take("a")
        r.move("a", "b")
        self.assertEqual(r.pending("a"), 0)
        self.assertEqual(r.pending("b"), 1)


class TestDispatchRequest(unittest.TestCase):
    def setUp(self):
        # three candidates, distinct ids
        self.nodes = [{"node_id": f"n{i}", "host": "10.0.0.%d" % i, "port": 11434,
                       "models": ["m"]} for i in range(1, 4)]

    def test_first_candidate_success(self):
        calls = []
        def post(node, body, dl):
            calls.append(node["node_id"])
            return True, "ok", 200
        r = D.dispatch_request(self.nodes, "m", {}, post)
        self.assertTrue(r["ok"])
        self.assertEqual(r["node_id"], "n1")      # least-loaded first, stable id order
        self.assertEqual(r["round"], 1)
        self.assertEqual(len(calls), 1)

    def test_failover_moves_reservation(self):
        seq = {"n1": (False, "boom", 500), "n2": (True, "ok", 200)}
        seen = []
        def post(node, body, dl):
            seen.append(node["node_id"])
            return seq[node["node_id"]]
        r = D.dispatch_request(self.nodes, "m", {}, post)
        self.assertTrue(r["ok"])
        self.assertEqual(r["node_id"], "n2")
        self.assertEqual(seen, ["n1", "n2"])       # failover stepped to n2
        # all reservations released at request end
        self.assertEqual(D._res.pending("n1"), 0)
        self.assertEqual(D._res.pending("n2"), 0)

    def test_budget_exhausted(self):
        def post(node, body, dl):
            return False, "boom", 503              # retryable every time
        r = D.dispatch_request(self.nodes, "m", {}, post)
        self.assertFalse(r["ok"])
        self.assertEqual(len(r["tried"]), D.MAX_DISPATCH_ROUNDS)

    def test_non_retryable_stops(self):
        tried = []
        def post(node, body, dl):
            tried.append(node["node_id"])
            return False, "bad request", 400       # NOT retryable
        r = D.dispatch_request(self.nodes, "m", {}, post)
        self.assertFalse(r["ok"])
        self.assertEqual(len(tried), 1)            # stopped after ONE failure (any node)

    def test_deadline_stops(self):
        def post(node, body, dl):
            return False, "slow", 503
        r = D.dispatch_request(self.nodes, "m", {}, post, deadline_s=0.0)
        self.assertFalse(r["ok"])
        self.assertEqual(r["tried"], [])           # deadline hit before first round

    def test_least_loaded_first(self):
        D._res.take("n1"); D._res.take("n1")       # n1 already busy
        order = []
        def post(node, body, dl):
            order.append(node["node_id"])
            return True, "ok", 200
        D.dispatch_request(self.nodes, "m", {}, post)
        self.assertEqual(order[0], "n2")           # least pending first


import time


if __name__ == "__main__":
    unittest.main()