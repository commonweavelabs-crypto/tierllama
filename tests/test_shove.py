"""Tests for tierllama/shove.py (J13 v2 task 3: priority insert + transparent rescheduling).
Run: python -m unittest tests.test_shove -v"""
import sys, unittest, tempfile, shutil
from pathlib import Path
from datetime import datetime, timedelta
sys.path.insert(0, str(Path(__file__).parent.parent))

from tierllama import shove as V
from tierllama.shove import estimate_duration_min, shove, shove_count_this_week, insert_priority

NOW = datetime(2026, 9, 29, 14, 0)


def _job(jid, due, lane="BOX", cls="medium", shoves=None):
    return {"id": jid, "lane": lane, "due_at": due, "message": "m", "status": "pending",
            "tries": 0, "meta": {"duration_class": cls}, "shove_history": shoves or []}


class TestDuration(unittest.TestCase):
    def test_class_estimates(self):
        self.assertEqual(estimate_duration_min({"meta": {}}), 30)
        self.assertEqual(estimate_duration_min({"meta": {"duration_class": "quick"}}), 5)
        self.assertEqual(estimate_duration_min({"meta": {"duration_class": "overnight"}}), 480)
        self.assertEqual(estimate_duration_min({"meta": {"duration_class": "bogus"}}), 30)


class TestShove(unittest.TestCase):
    def test_shove_moves_due_and_records(self):
        job = _job("j1", "2026-09-30T03:00:00")
        shoved = shove(job, 30, "priority-1", NOW)
        self.assertEqual(shoved["due_at"], "2026-09-30T03:30:00")
        self.assertEqual(len(shoved["shove_history"]), 1)
        self.assertEqual(shoved["shove_history"][0]["by_job"], "priority-1")
        self.assertIn("user notified", shoved["rescheduled_reason"])

    def test_original_not_mutated(self):
        job = _job("j1", "2026-09-30T03:00:00")
        shoved = shove(job, 30, "p", NOW)
        self.assertEqual(job["due_at"], "2026-09-30T03:00:00")  # caller's copy intact
        self.assertEqual(len(job.get("shove_history") or []), 0)


class TestShoveCap(unittest.TestCase):
    def test_cap_blocks_after_3(self):
        from tierllama import config as C
        old = C.SCHEDULER["shove_cap_week"]
        C.SCHEDULER["shove_cap_week"] = 3
        try:
            history = [{"at": (NOW - timedelta(days=d)).isoformat(timespec="seconds"),
                        "by_job": "p0", "by_minutes": 10, "from": "x", "to": "y"}
                       for d in (0, 1, 2)]
            job = _job("j1", "2026-09-30T03:00:00", shoves=history)
            self.assertEqual(shove_count_this_week(job, NOW), 3)
            self.assertIsNone(shove(job, 30, "p9", NOW))  # cap hit -> None, NOT moved
            self.assertEqual(job["due_at"], "2026-09-30T03:00:00")
        finally:
            C.SCHEDULER["shove_cap_week"] = old

    def test_old_shoves_expire(self):
        history = [{"at": (NOW - timedelta(days=10)).isoformat(timespec="seconds"),
                    "by_job": "old", "by_minutes": 10, "from": "x", "to": "y"}]
        job = _job("j1", "2026-09-30T03:00:00", shoves=history)
        self.assertEqual(shove_count_this_week(job, NOW), 0)  # outside 7d window


class TestInsertPriority(unittest.TestCase):
    def test_insert_shoves_later_jobs_first(self):
        prio = _job("prio", "2026-09-30T01:00:00", cls="quick")   # needs 5 min
        q1 = _job("q1", "2026-09-30T02:00:00")
        q2 = _job("q2", "2026-09-30T03:00:00")
        after, events = insert_priority(prio, [q1, q2], "2026-09-30T08:00:00", NOW)
        # need (5) is met by the FIRST shove; no further jobs touched
        shoved = [e for e in events if e["event"] == "shoved"]
        self.assertEqual(len(shoved), 1)
        self.assertEqual(shoved[0]["by_minutes"], 5)
        self.assertEqual(shoved[0]["job"], "q2")   # latest-due shoves first
        self.assertTrue(shoved[0]["user_notified"])
        # untouched job keeps its due_at
        q1_after = [j for j in after if j["id"] == "q1"][0]
        self.assertEqual(q1_after["due_at"], "2026-09-30T02:00:00")

    def test_needs_met_stops_shoving(self):
        prio = _job("prio", "2026-09-30T01:00:00", cls="quick")   # needs 5
        q1 = _job("q1", "2026-09-30T02:00:00")
        after, events = insert_priority(prio, [q1], "2026-09-30T08:00:00", NOW)
        # first shove (5 min) frees the whole 5-min need -> done
        self.assertEqual(len([e for e in events if e["event"] == "shoved"]), 1)

    def test_cap_hit_job_not_moved_but_reported(self):
        from tierllama import config as C
        old = C.SCHEDULER["shove_cap_week"]
        C.SCHEDULER["shove_cap_week"] = 3
        try:
            prio = _job("prio", "2026-09-30T01:00:00", cls="overnight")  # needs 480
            history = [{"at": NOW.isoformat(timespec="seconds"), "by_job": "p0",
                        "by_minutes": 10, "from": "x", "to": "y"} for _ in range(3)]
            free = _job("free", "2026-09-30T02:00:00")
            capped = _job("capped", "2026-09-30T04:00:00", shoves=history)  # later-due: encountered FIRST
            after, events = insert_priority(prio, [capped, free], "2026-09-30T08:00:00", NOW)
            caps = [e for e in events if e["event"] == "shove_cap_hit"]
            self.assertEqual(len(caps), 1)
            self.assertEqual(caps[0]["job"], "capped")
            # the capped job's due_at must be UNCHANGED in the result
            capped_after = [j for j in after if j["id"] == "capped"][0]
            self.assertEqual(capped_after["due_at"], "2026-09-30T04:00:00")
        finally:
            C.SCHEDULER["shove_cap_week"] = old


if __name__ == "__main__":
    unittest.main()