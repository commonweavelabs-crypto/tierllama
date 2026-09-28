"""Tests for tierllama/worker_classes.py + scheduler tick integration (J13 v2 task 2).
Run: python -m unittest tests.test_worker_classes -v"""
import sys, unittest, tempfile, json
from pathlib import Path
from datetime import datetime, timedelta
sys.path.insert(0, str(Path(__file__).parent.parent))

from tierllama import worker_classes as W
from tierllama.worker_classes import class_for_lane, can_dispatch_now, maybe_shift_due


class TestClassMapping(unittest.TestCase):
    def test_box_is_night_only(self):
        self.assertEqual(class_for_lane("BOX"), "night_only")

    def test_everything_else_always_on(self):
        for lane in ("LOCAL", "CLOUD_MEDIUM", "CLOUD_HARD", "FALLBACK"):
            self.assertEqual(class_for_lane(lane), "always_on")

    def test_unknown_lane_never_blocks(self):
        # safest for deadlines: an unknown lane must NOT be night-blocked
        self.assertEqual(class_for_lane("NOT_A_LANE"), "always_on")


class TestCanDispatch(unittest.TestCase):
    def test_always_on_any_hour(self):
        for hhmm in ("03:00", "12:00", "23:59"):
            ok, _ = can_dispatch_now("LOCAL", datetime(2026, 9, 29, int(hhmm[:2]), int(hhmm[3:])))
            self.assertTrue(ok)

    def test_night_only_in_window(self):
        ok, why = can_dispatch_now("BOX", datetime(2026, 9, 29, 3, 0))   # window 00:00-08:00
        self.assertTrue(ok)
        self.assertEqual(why, "night_only in window")

    def test_night_only_outside_window(self):
        ok, why = can_dispatch_now("BOX", datetime(2026, 9, 29, 14, 0))
        self.assertFalse(ok)
        self.assertEqual(why, "night_only waiting_for_window")

    def test_window_edge_exclusive_end(self):
        # 08:00 == window end -> outside (end is exclusive, matches _is_night)
        ok, _ = can_dispatch_now("BOX", datetime(2026, 9, 29, 8, 0))
        self.assertFalse(ok)


class TestShift(unittest.TestCase):
    def test_no_shift_when_dispatchable(self):
        job = {"id": "x", "lane": "BOX", "due_at": "2026-09-29T03:00:00"}
        self.assertIsNone(maybe_shift_due(job, datetime(2026, 9, 29, 3, 0)))

    def test_shift_moves_to_next_window_open(self):
        job = {"id": "x", "lane": "BOX", "due_at": "2026-09-29T14:00:00"}
        shifted = maybe_shift_due(job, datetime(2026, 9, 29, 14, 0))
        self.assertIsNotNone(shifted)
        # next window open after 14:00 (start 00:00 passed today) = tomorrow 00:00
        self.assertEqual(shifted["due_at"], "2026-09-30T00:00:00")
        self.assertIn("rescheduled_reason", shifted)
        self.assertIn("not silent", shifted["rescheduled_reason"])

    def test_shift_before_window_start_today(self):
        # due 23:50, window starts 00:00 -> next open is TOMORROW 00:00 (today's start passed)
        job = {"id": "x", "lane": "BOX", "due_at": "2026-09-29T23:50:00"}
        shifted = maybe_shift_due(job, datetime(2026, 9, 29, 23, 50))
        self.assertEqual(shifted["due_at"], "2026-09-30T00:00:00")


class TestTickIntegration(unittest.TestCase):
    """End-to-end through the real scheduler file queue (sandboxed)."""

    def setUp(self):
        import tierllama.scheduler as S
        self.S = S
        self.tmp = tempfile.mkdtemp()
        from tierllama import config as C
        self.cfg = C
        self.old_q = C.SCHEDULER["queue_path"]
        C.SCHEDULER["queue_path"] = str(Path(self.tmp) / "sched.json")
        self.old_QUEUE_PATH = S.QUEUE_PATH
        S.QUEUE_PATH = Path(self.tmp) / "sched.json"   # _load/_save read module global
        self.real_dispatch = S._dispatch
        S._dispatch = lambda j: None   # no live dispatch; status set below
        # monkey the dispatch result path: tick calls _dispatch(j) which mutates j
        def fake_dispatch(j):
            j["tries"] += 1
            j["status"] = "dispatched"
        S._dispatch = fake_dispatch
        C.SCHEDULER["enabled"] = True

    def tearDown(self):
        self.cfg.SCHEDULER["queue_path"] = self.old_q
        self.S.QUEUE_PATH = self.old_QUEUE_PATH
        self.cfg.SCHEDULER["enabled"] = False
        self.S._dispatch = self.real_dispatch
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _enqueue(self, lane, due, message="job"):
        return self.S.enqueue(message, lane, due, title="t")

    def test_always_on_due_job_dispatches_day_or_night(self):
        job = self._enqueue("LOCAL", (datetime.now() - timedelta(seconds=5)).isoformat(timespec="seconds"))
        summary = self.S.tick(now=datetime(2026, 9, 29, 14, 0))   # broad daylight
        self.assertEqual(summary["dispatched"], 1)
        self.assertEqual(summary["shifted"], [])

    def test_night_only_due_daytime_gets_visible_shift(self):
        due = (datetime(2026, 9, 29, 14, 0)).isoformat(timespec="seconds")
        job = self._enqueue("BOX", due)
        summary = self.S.tick(now=datetime(2026, 9, 29, 14, 0))
        self.assertEqual(summary["dispatched"], 0)
        self.assertEqual(len(summary["shifted"]), 1)
        self.assertEqual(summary["shifted"][0]["id"], job["id"])
        self.assertIn("rescheduled_reason", summary["shifted"][0])
        # and the queue file carries the shift (visible, not silent):
        on_disk = json.loads(Path(self.cfg.SCHEDULER["queue_path"]).read_text(encoding="utf-8"))
        summary_shift_check = "2026-09-29T14:00:00"  # shifted due must be AFTER this
        j = [x for x in on_disk["jobs"] if x["id"] == job["id"]][0]
        # status stays 'due' from due_jobs marking; the SHIFT is what matters:
        # due_at moved to the future, so due_jobs (due_at <= now) won't re-pick it
        self.assertIn("rescheduled_reason", j)
        self.assertGreater(j["due_at"], summary_shift_check)
        self.assertNotEqual(j["due_at"], due)

    def test_night_only_due_inside_window_dispatches(self):
        due = (datetime(2026, 9, 29, 3, 0)).isoformat(timespec="seconds")
        self._enqueue("BOX", due)
        summary = self.S.tick(now=datetime(2026, 9, 29, 3, 0))
        self.assertEqual(summary["dispatched"], 1)
        self.assertEqual(summary["shifted"], [])


if __name__ == "__main__":
    unittest.main()