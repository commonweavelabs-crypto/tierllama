"""J20 Part 2 clarify-lane Web UI card (J20.5): pending list + one-tap answers.

Web-app E2E: index.html/app.js card vs the /api/clarify/* endpoints in webapp.py.
Runs the endpoints' FULL handler flow in-process against a TEMP ledger copy —
never touches the real logs/clarify_ledger.jsonl (sandbox law).
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from tierllama import webapp  # noqa: E402

client = TestClient(webapp.app)


class ClarifyCardE2E(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.ledger = Path(self.tmpdir) / "clarify_ledger.jsonl"

    def _patch(self):
        return mock.patch.object(webapp, "LEDGER_PATH", self.ledger) if hasattr(
            webapp, "LEDGER_PATH") else None

    def _row_full(self):
        return {"ts": "2026-10-04T15:00:00", "message": "plan my week I guess",
                "dim": "timing", "jev_conf": {"difficulty": 0.9, "timing": 0.4},
                "jev_verdict": {"difficulty": "MEDIUM", "timing": "LATER"},
                "asked": {"answer": "NOW", "confidence": 0.7,
                          "probabilities": {"NOW": 0.7, "LATER": 0.3}},
                "user_answer": None, "bucket": "planner-verb-timing",
                "asker_model": "tev1:0.8b"}

    def _write(self, rows):
        self.ledger.write_text("".join(json.dumps(r) + "\n" for r in rows),
                               encoding="utf-8")

    def test_pending_shape(self):
        """pending returns the fields the card renders"""
        self._write([self._row_full()])
        from tierllama.clarify import LEDGER_PATH
        with mock.patch("tierllama.clarify.LEDGER_PATH", self.ledger):
            r = client.get("/api/clarify/pending").json()
        self.assertEqual(len(r["pending"]), 1)
        p = r["pending"][0]
        for k in ("ts", "message", "dim", "suggested", "asker_conf"):
            self.assertIn(k, p)
        self.assertEqual(p["suggested"], "NOW")
        # answered rows never appear as pending
        self._write([{**self._row_full(), "user_answer": "NOW"}])
        with mock.patch("tierllama.clarify.LEDGER_PATH", self.ledger):
            r = client.get("/api/clarify/pending").json()
        self.assertEqual(r["pending"], [])

    def test_pending_empty(self):
        r = client.get("/api/clarify/pending").json()
        self.assertEqual(r["pending"], [])

    def test_answer_flow(self):
        """one-tap answer fills user_answer in place; patterns aggregate it"""
        rows = [self._row_full()]
        self._write(rows)
        from tierllama import clarify
        with mock.patch("tierllama.clarify.LEDGER_PATH", self.ledger):
            r = client.post("/api/clarify/answer",
                            json={"ts": "2026-10-04T15:00:00",
                                  "message": "plan my week I guess",
                                  "dim": "timing", "answer": "NOW"}).json()
        self.assertTrue(r["ok"])
        filled = [json.loads(l) for l in self.ledger.read_text().splitlines()]
        self.assertEqual(filled[0]["user_answer"], "NOW")
        # patterns export stays distilled: no message text in the payload
        with mock.patch("tierllama.clarify.LEDGER_PATH", self.ledger):
            pat = client.get("/api/clarify/patterns").json()
        blob = json.dumps(pat)
        self.assertNotIn("plan my week", blob)
        self.assertEqual(pat["patterns"][0]["user_answer_top"], "NOW")

    def test_answer_privacy_gate(self):
        """answered-row export carries buckets only (design doc law)"""
        rows = [{**self._row_full(), "user_answer": "LATER"}]
        self._write(rows)
        from tierllama import clarify
        with mock.patch("tierllama.clarify.LEDGER_PATH", self.ledger):
            pat = client.get("/api/clarify/patterns").json()
        blob = json.dumps(pat)
        self.assertNotIn("plan my week", blob)


if __name__ == "__main__":
    unittest.main()