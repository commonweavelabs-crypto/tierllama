"""J26 consolidation (Gui approved 2026-10-06): dispatch.py is now WIRED into
proxy.py /v1/chat/completions for LOCAL lanes. Seam tests, all sandboxed
(no real network, no real Ollama; FastAPI TestClient + mocks).

Run: python -m unittest tests.test_proxy_dispatch -v
"""
import sys, unittest, json, io, threading
from pathlib import Path
from unittest.mock import patch, MagicMock
import urllib.error

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tierllama import proxy  # noqa: E402

_REAL_DISPATCH = proxy._dispatch.dispatch_request   # restored after each test


class TestPostNode(unittest.TestCase):
    """_post_node transport contract: (ok, result, status)."""

    def tearDown(self):
        proxy._dispatch.dispatch_request = _REAL_DISPATCH

    def test_ok_shape(self):
        class R:
            def read(self):
                return json.dumps({"message": {"content": "hello"},
                                   "prompt_eval_count": 11, "eval_count": 22}).encode()
        with patch("urllib.request.urlopen", return_value=R()):
            ok, res, status = proxy._post_node(
                {"host": "127.0.0.1", "port": 11434},
                {"model": "qwen3:4b", "messages": []}, 30)
        self.assertTrue(ok)
        self.assertEqual(status, 200)
        self.assertEqual(res["text"], "hello")
        self.assertEqual((res["prompt_tokens"], res["completion_tokens"]), (11, 22))

    def test_http_error_carries_status(self):
        err = urllib.error.HTTPError("u", 503, "overloaded", {},
                                     io.BytesIO(b'{"error": "overloaded"}'))
        with patch("urllib.request.urlopen", side_effect=err):
            ok, res, status = proxy._post_node(
                {"host": "127.0.0.1", "port": 11434}, {}, 30)
        self.assertFalse(ok)
        self.assertEqual(status, 503)          # dispatch retryable set
        self.assertIn("overloaded", res)

    def test_transport_failure_status_none(self):
        with patch("urllib.request.urlopen",
                   side_effect=urllib.error.URLError("Conn refused")):
            ok, res, status = proxy._post_node(
                {"host": "127.0.0.1", "port": 9999}, {}, 30)
        self.assertFalse(ok)
        self.assertIsNone(status)


class TestFleetPicture(unittest.TestCase):
    """_fleet_nodes_for: self always present + live LAN nodes appended."""

    def tearDown(self):
        proxy._dispatch.dispatch_request = _REAL_DISPATCH

    def test_self_only_when_no_lan_nodes(self):
        with patch.object(proxy._fleet_mod.Fleet, "list", return_value=[]):
            nodes = proxy._fleet_nodes_for(["qwen3:4b"])
        self.assertEqual([n["node_id"] for n in nodes], [proxy.SELF_NODE_ID])
        self.assertEqual(nodes[0]["host"], "127.0.0.1")
        self.assertIn("qwen3:4b", nodes[0]["models"])

    def test_lan_nodes_appended(self):
        lan = [{"node_id": "box", "host": "192.0.2.50", "port": 11434,
                "models": ["qwen3:4b"]}]
        with patch.object(proxy._fleet_mod.Fleet, "list", return_value=lan):
            nodes = proxy._fleet_nodes_for([])
        self.assertEqual([n["node_id"] for n in nodes], ["local", "box"])

    def test_self_not_duplicated_from_lan(self):
        lan = [{"node_id": proxy.SELF_NODE_ID, "host": "1.2.3.4", "port": 1,
                "models": []}]
        with patch.object(proxy._fleet_mod.Fleet, "list", return_value=lan):
            nodes = proxy._fleet_nodes_for([])
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["node_id"], proxy.SELF_NODE_ID)


class TestChatSeam(unittest.TestCase):
    """The real seam: chat()'s local path dispatches over the fleet with
    reservations + failover; cloud bypasses dispatch entirely.
    SANDBOX LAW: log + fleet writes are redirected to a temp dir — the tests
    previously appended fake dispatch rows to the REAL logs/proxy.jsonl
    (caught in the J26 consolidation pass: latency 0.0 rows with test-node ids)."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        from fastapi.testclient import TestClient
        cls._tmp = tempfile.mkdtemp(prefix="tierllama_seam_")
        cls._log_patcher = patch.object(proxy, "PROXY_LOG",
                                       Path(cls._tmp) / "proxy.jsonl")
        cls._log_patcher.start()
        cls.client = TestClient(proxy.app)

    @classmethod
    def tearDownClass(cls):
        cls._log_patcher.stop()

    def setUp(self):
        proxy._dispatch.dispatch_request = _REAL_DISPATCH

    def tearDown(self):
        proxy._dispatch.dispatch_request = _REAL_DISPATCH

    def _chat(self, model="qwen3:4b", content="ping"):
        return self.client.post("/v1/chat/completions", json={
            "model": model,
            "messages": [{"role": "user", "content": content}]})

    def test_local_lane_dispatches_and_answers(self):
        def fake_dispatch(nodes, model, body, do_post, log=None):
            return {"ok": True, "node_id": nodes[0]["node_id"],
                    "result": {"text": "from-local", "prompt_tokens": 1,
                               "completion_tokens": 2},
                    "tried": [nodes[0]["node_id"]]}
        with patch.object(proxy._fleet_mod.Fleet, "list", return_value=[]):
            proxy._dispatch.dispatch_request = fake_dispatch
            r = self._chat()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["choices"][0]["message"]["content"], "from-local")

    def test_all_nodes_dead_returns_502(self):
        def fake_dispatch(nodes, model, body, do_post, log=None):
            return {"ok": False, "node_id": None, "result": None,
                    "tried": [n["node_id"] for n in nodes],
                    "error": "dispatch budget/deadline exhausted"}
        with patch.object(proxy._fleet_mod.Fleet, "list", return_value=[]):
            proxy._dispatch.dispatch_request = fake_dispatch
            r = self._chat()
        self.assertEqual(r.status_code, 502)
        self.assertIn("error", r.json())

    def test_cloud_bypasses_dispatch(self):
        def boom(*a, **k):
            raise AssertionError("cloud must not hit dispatch")
        decision = {"difficulty": "EXPERT", "timing": "NOW", "lane": "CLOUD",
                    "confidence": 0.9, "classifier_latency_s": 0.1}
        with patch.object(proxy, "route", return_value=decision), \
             patch.object(proxy, "_load_tree",
                          return_value={"EXPERT/NOW": {"model": "glm-5.3-flash:cloud",
                                                       "thinking": "normal"}}), \
             patch.object(proxy, "_upstream") as up, \
             patch.object(proxy._dispatch, "dispatch_request", side_effect=boom):
            up.return_value = {"id": "t",
                               "choices": [{"message": {"content": "ok"}}]}
            r = self._chat(model="glm-5.3-flash:cloud", content="hi")
        self.assertEqual(r.status_code, 200)

    def test_success_vouches_fleet(self):
        def fake_dispatch(nodes, model, body, do_post, log=None):
            return {"ok": True, "node_id": "lan-9",
                    "result": {"text": "x", "prompt_tokens": 0,
                               "completion_tokens": 0},
                    "tried": ["lan-9"]}
        with patch.object(proxy._fleet_mod, "Fleet") as F:
            F.return_value.list.return_value = []
            F.return_value.vouch_inference = MagicMock()
            proxy._dispatch.dispatch_request = fake_dispatch
            r = self._chat()
        self.assertEqual(r.status_code, 200)
        F.return_value.vouch_inference.assert_called_once_with("lan-9")


if __name__ == "__main__":
    unittest.main()


class TestClassifierSingleFlight(unittest.TestCase):
    """J26 Finding 1 fix: concurrent classify() calls serialize through one
    lock (no driver-level stampede); identical messages would be one GPU call
    under a shared-flight variant, callers never receive interleaved results."""

    def test_lock_is_threading_lock(self):
        from tierllama import classifier as C
        self.assertIsInstance(C._cls_lock, type(threading.Lock()))

    def test_concurrent_classify_serialized(self):
        from tierllama import classifier as C
        order = []
        orig = C._classify_dims
        def fake_dims(message, timeout=120):
            order.append(("start", message))
            import time as _t; _t.sleep(0.05)
            order.append(("end", message))
            return {"difficulty": "EASY", "difficulty_conf": 0.9,
                    "timing": "NOW", "timing_conf": 0.9,
                    "when": "NOW", "when_conf": 1.0, "when_raw": ""}
        with patch.object(C, "_classify_dims", side_effect=fake_dims):
            threads = [threading.Thread(target=C.classify, args=(f"m{i}",))
                       for i in range(5)]
            for t in threads: t.start()
            for t in threads: t.join()
        # strict alternation proves the lock serializes: no start after a start
        starts = [i for i, (k, _) in enumerate(order) if k == "start"]
        ends = [i for i, (k, _) in enumerate(order) if k == "end"]
        self.assertEqual(len(starts), 5)
        self.assertEqual(len(ends), 5)
        for s_i, e_i in zip(starts, ends):
            self.assertTrue(any(ee > s_i for ee in ends[:ends.index(e_i)+1]),
                            "every start is followed by its end before next start" if False else "")
        # stronger: sequence must be s,e,s,e,... (all starts at even idx)
        kinds = [k for k, _ in order]
        self.assertEqual(kinds, [k for i, k in enumerate(kinds) if True][:0] or
                         ["start", "end"] * 5)
