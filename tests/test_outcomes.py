"""Tests for tierllama/outcomes.py (J14 task 1: outcome signals).
Run: python -m unittest tests.test_outcomes -v"""
import sys, unittest, tempfile, shutil, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tierllama import outcomes as O


class TestClassify(unittest.TestCase):
    def test_error_is_failure(self):
        self.assertEqual(O.classify_result({"status": "error", "error": "HTTP 500"}), "failure")

    def test_empty_content_is_failure(self):
        self.assertEqual(O.classify_result({"status": "ok", "result": "  "}), "failure")
        self.assertEqual(O.classify_result({"status": "ok", "result": ""}), "failure")

    def test_ok_with_content_is_success(self):
        self.assertEqual(O.classify_result({"status": "ok", "result": "answer"}), "success")

    def test_queued_is_unknown(self):
        # BOX async: never judged at dispatch time
        self.assertEqual(O.classify_result({"status": "queued"}), "unknown")

    def test_none_is_failure(self):
        self.assertEqual(O.classify_result(None), "failure")


class TestRetrySignal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_log = O.OUTCOME_LOG
        O.OUTCOME_LOG = Path(self.tmp) / "outcomes.jsonl"
        O._retry_counts.clear()

    def tearDown(self):
        O.OUTCOME_LOG = self.old_log
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_retry_marks_failure_signal(self):
        rec = {"message": "Clean up the transcriptions", "lane": "LOCAL"}
        res = {"status": "ok", "result": "done", "model": "qwen3:4b", "latency_s": 1.0}
        out = O.note_dispatch_result(rec, res)
        self.assertEqual(out, "success")
        # user re-sends the same message -> failure signal per spec
        O.note_user_retry("clean up  the  transcriptions ")   # normalized: same key
        self.assertTrue(O.is_retried("Clean up the transcriptions"))

    def test_retry_survives_whitespace_case(self):
        O.note_user_retry("Hello World")
        self.assertTrue(O.is_retried("hello   world"))
        self.assertFalse(O.is_retried("different message"))

    def test_log_records_masked_key_not_content(self):
        rec = {"message": "secret user content here", "lane": "LOCAL",
               "difficulty": "EASY", "timing": "NOW", "when": "NOW"}
        O.note_dispatch_result(rec, {"status": "ok", "result": "x", "model": "m", "latency_s": 0.1})
        entry = json.loads(O.OUTCOME_LOG.read_text(encoding="utf-8").strip())
        self.assertNotIn("secret", json.dumps(entry))   # privacy: content never logged
        self.assertIn("msg_key_hash", entry)            # hashed key only
        self.assertEqual(len(entry["msg_key_hash"]), 16)
        self.assertEqual(entry["outcome"], "success")


class TestSummary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_log = O.OUTCOME_LOG
        O.OUTCOME_LOG = Path(self.tmp) / "outcomes.jsonl"
        O._retry_counts.clear()

    def tearDown(self):
        O.OUTCOME_LOG = self.old_log
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_summary_counts(self):
        rec = {"message": "m", "lane": "LOCAL"}
        O.note_dispatch_result(rec, {"status": "ok", "result": "x", "model": "m1"})
        O.note_dispatch_result(dict(rec), {"status": "error", "error": "boom", "model": "m1"})
        O.note_dispatch_result(dict(rec), {"status": "queued", "model": "m1"})
        s = O.summary()
        self.assertEqual(s["success"], 1)
        self.assertEqual(s["failure"], 1)
        self.assertEqual(s["unknown"], 1)


if __name__ == "__main__":
    unittest.main()