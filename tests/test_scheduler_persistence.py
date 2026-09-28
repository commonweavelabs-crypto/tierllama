"""J13 v1 E2E: queue persistence across a process restart + night-window edges.

Simulates a restart by re-importing the scheduler module fresh (a new process
would do the same since the queue is file-backed and there is no in-memory
state beyond threading.Lock). Real cross-process test: spawn python -c that
enqueues, then THIS process ticks. Run: python -m unittest tests.test_scheduler_persist -v
"""
import sys, unittest, subprocess, json, tempfile, datetime, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
ROOT = Path(__file__).parent.parent

ENV = dict(os.environ, PYTHONPATH=str(ROOT))


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.qpath = Path(self.tmp) / "sched.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _subprocess_enqueue(self, msg, lane, due_at):
        """Separate interpreter: enqueue, exit. Proves file survives 'restart'."""
        code = (
            "import sys; sys.path.insert(0, r'%s');"
            "from tierllama import config; config.SCHEDULER['enabled'] = True;"
            "config.SCHEDULER['queue_path'] = r'%s';"
            "from tierllama import scheduler as S;"
            "S.QUEUE_PATH = __import__('pathlib').Path(r'%s');"
            "job = S.enqueue(r'%s', '%s', r'%s');"
            "print(job['id'])" % (ROOT, self.qpath, self.qpath, msg, lane, due_at)
        )
        r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, timeout=60, env=ENV)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip().splitlines()[-1]

    def test_enqueue_new_process_then_tick_here(self):
        due = (datetime.datetime.now() - datetime.timedelta(seconds=5)).isoformat(timespec="seconds")
        jid = self._subprocess_enqueue("persist me across restarts", "LOCAL", due)
        # fresh module state HERE (simulates the service restarting):
        for mod in list(sys.modules):
            if mod.startswith("tierllama"):
                del sys.modules[mod]
        from tierllama import config as C
        C.SCHEDULER["queue_path"] = str(self.qpath)
        from tierllama import scheduler as S
        jobs = S.list_jobs()
        self.assertEqual(len(jobs), 1, "queue must survive the process boundary")
        self.assertEqual(jobs[0]["id"], jid)
        self.assertEqual(jobs[0]["status"], "pending")
        # tick dispatches it — but through a FAKE adapters.dispatch (2026-09-29:
        # a real Ollama call in a persistence test makes the test flaky + loads GPU)
        import tierllama.adapters as A
        real_dispatch = A.dispatch
        A.dispatch = lambda lane, message, **kw: {"status": "ok", "lane": lane,
            "model": "test-stub", "result": "test", "latency_s": 0.0}
        try:
            summary = S.tick()
        finally:
            A.dispatch = real_dispatch
        self.assertEqual(summary["dispatched"], 1)
        self.assertEqual(summary["jobs"][0]["status"], "dispatched")
        # and the file agrees:
        on_disk = json.loads(self.qpath.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["jobs"][0]["status"], "dispatched")

    def test_corrupt_queue_file_resets_to_empty(self):
        self.qpath.write_text("{not json", encoding="utf-8")
        for mod in list(sys.modules):
            if mod.startswith("tierllama"):
                del sys.modules[mod]
        from tierllama import config as C
        C.SCHEDULER["queue_path"] = str(self.qpath)
        from tierllama import scheduler as S
        self.assertEqual(S.list_jobs(), [])


class TestNightWindow(unittest.TestCase):
    def _is_night_at(self, hhmm, window):
        from tierllama import config as C
        old = C.SCHEDULER["night_window"]
        C.SCHEDULER["night_window"] = window
        try:
            from tierllama import scheduler as S
            dt = datetime.datetime(2026, 9, 25, int(hhmm[:2]), int(hhmm[3:]))
            return S._is_night(now=dt)
        finally:
            C.SCHEDULER["night_window"] = old

    def test_normal_window(self):
        self.assertTrue(self._is_night_at("23:30", {"start": "23:00", "end": "06:00"}))
        self.assertFalse(self._is_night_at("12:00", {"start": "23:00", "end": "06:00"}))

    def test_midnight_wrap(self):
        self.assertTrue(self._is_night_at("01:00", {"start": "23:00", "end": "06:00"}))
        self.assertTrue(self._is_night_at("23:59", {"start": "23:00", "end": "06:00"}))
        self.assertFalse(self._is_night_at("06:00", {"start": "23:00", "end": "06:00"}))
        self.assertFalse(self._is_night_at("22:59", {"start": "23:00", "end": "06:00"}))

    def test_start_equals_end_edge(self):
        # 00:00-00:00 is a degenerate window: treat as always-night (h>=s or h<e covers all h)
        self.assertTrue(self._is_night_at("12:00", {"start": "00:00", "end": "00:00"}))
        self.assertTrue(self._is_night_at("00:00", {"start": "00:00", "end": "00:00"}))


if __name__ == "__main__":
    unittest.main()