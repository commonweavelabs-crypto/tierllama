"""Tests for tierllama/fleet.py (J12+ T3, PAIR-derived anti-flap liveness).
Run: python -m unittest tests.test_fleet -v"""
import sys, time, unittest
from pathlib import Path
import tempfile
sys.path.insert(0, str(Path(__file__).parent.parent))

from tierllama.fleet import Fleet, VOUCH_INFER_SECONDS, MISS_THRESHOLD, SUPPRESS_SCANS


class TestFleetBasics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.tmp = Path(self.tmp.name)
        self.f = Fleet(store_path=self.tmp)

    def tearDown(self):
        self.tmp.unlink(missing_ok=True)

    def test_upsert_and_persist(self):
        self.f.upsert("n1", "<box-lan-ip>", 11434, models=["qwen3:4b"])
        f2 = Fleet(store_path=self.tmp)   # new instance reads the store
        self.assertEqual(len(f2.list()), 1)
        self.assertEqual(f2.list()[0]["models"], ["qwen3:4b"])

    def test_provenance_local_fleet(self):
        self.f.upsert("n1", "10.0.0.5", 11434)
        ps = self.f.as_providers()
        self.assertEqual(ps[0]["provenance"], "local-fleet")
        self.assertEqual(ps[0]["name"], "fleet-n1")
        self.assertTrue(ps[0]["enabled"])


class TestAntiFlap(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.NamedTemporaryFile(suffix=".json", delete=False).name)
        self.f = Fleet(store_path=self.tmp)
        self.f.upsert("n1", "10.0.0.5", 11434)

    def tearDown(self):
        self.tmp.unlink(missing_ok=True)

    def test_single_miss_does_not_evict(self):
        for _ in range(MISS_THRESHOLD - 1):
            self.f.record_probe("n1", alive=False)
        self.assertEqual(len(self.f.list()), 1)   # still there
        self.f.record_probe("n1", alive=False)    # threshold reached
        self.assertEqual(len(self.f.list()), 0)   # now evicted

    def test_recovery_resets(self):
        for _ in range(MISS_THRESHOLD - 2):
            self.f.record_probe("n1", alive=False)
        self.f.record_probe("n1", alive=True)     # any contact resets
        for _ in range(MISS_THRESHOLD - 1):       # miss again from zero
            self.f.record_probe("n1", alive=False)
        self.assertEqual(len(self.f.list()), 1)   # not evicted: streak was reset

    def test_inference_bytes_vouch(self):
        for _ in range(MISS_THRESHOLD - 2):
            self.f.record_probe("n1", alive=False)
        self.f.vouch_inference("n1")              # busy node serving inference
        for _ in range(MISS_THRESHOLD + 5):       # would evict without vouching
            self.f.record_probe("n1", alive=False)
        self.assertEqual(len(self.f.list()), 1)   # vouched -> survives while busy

    def test_vouch_expires(self):
        # simulate: vouch happened, then time passes beyond the vouch window
        n = self.f._nodes["n1"]
        n.last_infer_ts = time.time() - (VOUCH_INFER_SECONDS + 5)
        for _ in range(MISS_THRESHOLD):
            self.f.record_probe("n1", alive=False)
        self.assertEqual(len(self.f.list()), 0)   # expired vouch -> normal eviction

    def test_all_lost_is_our_fault(self):
        for _ in range(SUPPRESS_SCANS):
            self.f.record_all_lost()
            self.f.record_probe("n1", alive=False)
        self.assertEqual(len(self.f.list()), 1)   # suppressed: not penalized

    def test_all_lost_expires(self):
        for _ in range(SUPPRESS_SCANS + 1):
            self.f.record_all_lost()
        self.f.record_probe("n1", alive=False)
        for _ in range(MISS_THRESHOLD - 1):
            self.f.record_probe("n1", alive=False)
        self.assertEqual(len(self.f.list()), 0)   # after suppression, normal rules


if __name__ == "__main__":
    unittest.main()