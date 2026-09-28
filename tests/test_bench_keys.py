"""Tests for tierllama/bench_keys.py (J16 Gap A: model@host bench keys).
Run: python -m unittest tests.test_bench_keys -v"""
import sys, unittest, tempfile, shutil, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tierllama import bench_keys as B
from tierllama.bench_keys import bench_key, stamp_host, migrate_existing, load_bench_by_key


class TestKeys(unittest.TestCase):
    def test_key_format(self):
        self.assertEqual(bench_key("qwen3:4b"), "qwen3:4b@localhost")
        self.assertEqual(bench_key("qwen3:4b", "box"), "qwen3:4b@box")

    def test_stamp_host_does_not_mutate_input(self):
        rec = {"model": "m1", "tok_s": 50}
        out = stamp_host(rec)
        self.assertNotIn("host", rec)      # caller's dict untouched
        self.assertEqual(out["host"], "localhost")
        self.assertEqual(out["bench_key"], "m1@localhost")


class TestMigration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_log = B.BENCH_LOG
        B.BENCH_LOG = Path(self.tmp) / "bench.jsonl"

    def tearDown(self):
        B.BENCH_LOG = self.old_log
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, records):
        B.BENCH_LOG.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

    def test_migrates_unstamped_records(self):
        self._write([{"model": "a", "tok_s": 40}, {"model": "b", "tok_s": 10}])
        report = migrate_existing()
        self.assertEqual(report["migrated"], 2)
        recs = [json.loads(l) for l in B.BENCH_LOG.read_text(encoding="utf-8").strip().split("\n")]
        self.assertTrue(all("bench_key" in r and r["host"] == "localhost" for r in recs))
        self.assertTrue(all("migration_note" in r for r in recs))

    def test_idempotent(self):
        self._write([{"model": "a", "tok_s": 40}])
        migrate_existing()
        report2 = migrate_existing()
        self.assertEqual(report2["migrated"], 0)
        self.assertEqual(report2["already_stamped"], 1)

    def test_keeps_existing_host(self):
        self._write([{"model": "a", "host": "box", "bench_key": "a@box"}])
        report = migrate_existing()
        self.assertEqual(report["migrated"], 0)
        recs = [json.loads(l) for l in B.BENCH_LOG.read_text(encoding="utf-8").strip().split("\n")]
        self.assertEqual(recs[0]["host"], "box")   # not overwritten with localhost


class TestLoadByKey(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_log = B.BENCH_LOG
        B.BENCH_LOG = Path(self.tmp) / "bench.jsonl"

    def _write(self, records):
        B.BENCH_LOG.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

    def tearDown(self):
        B.BENCH_LOG = self.old_log
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_two_machines_distinguishable(self):
        # THE bug Gap A fixes: same model on 2 machines was indistinguishable
        self._write([{"model": "q", "tok_s": 10, "host": "localhost", "bench_key": "q@localhost"},
                     {"model": "q", "tok_s": 55, "host": "box", "bench_key": "q@box"}])
        keyed = load_bench_by_key()
        self.assertEqual(len(keyed), 2)
        self.assertEqual(keyed["q@localhost"]["tok_s"], 10)
        self.assertEqual(keyed["q@box"]["tok_s"], 55)

    def test_newer_wins_per_key(self):
        self._write([{"model": "q", "tok_s": 10, "host": "localhost", "bench_key": "q@localhost"},
                     {"model": "q", "tok_s": 22, "host": "localhost", "bench_key": "q@localhost"}])
        keyed = load_bench_by_key()
        # second record (later line) overwrote the first
        self.assertEqual(keyed["q@localhost"]["tok_s"], 22)
        self.assertEqual(len(keyed), 1)


if __name__ == "__main__":
    unittest.main()