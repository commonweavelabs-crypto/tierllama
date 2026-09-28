"""Tests for tierllama/pair_labels.py (J16 Gap C: pair labeling + worker classes).
Run: python -m unittest tests.test_pair_labels -v"""
import sys, unittest, tempfile, shutil, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tierllama import pair_labels as P, machines as M
from tierllama.pair_labels import pair_worker_class, best_pair_for_lane


class TestPairWorkerClass(unittest.TestCase):
    def test_spec_mapping(self):
        # spec: NOW-fit + HARD on daily machine -> workhorse
        self.assertEqual(pair_worker_class({"timing_fit": "NOW", "max_fit": "HARD"}, "workhorse"), "workhorse")
        # LATER-fit + HARD-capable -> always_on or night_only (user picks)
        self.assertEqual(pair_worker_class({"timing_fit": "LATER", "max_fit": "HARD"}, "night_only"), "night_only")
        self.assertEqual(pair_worker_class({"timing_fit": "LATER", "max_fit": "HARD"}, "always_on"), "always_on")

    def test_cloud(self):
        self.assertEqual(pair_worker_class({"timing_fit": "NOW", "max_fit": "HARD", "cloud": True}, None), "cloud_scheduled")
        self.assertEqual(pair_worker_class({"timing_fit": "NOW"}, "cloud_scheduled"), "cloud_scheduled")

    def test_no_machine_class_conservative(self):
        self.assertEqual(pair_worker_class({"timing_fit": "NOW", "max_fit": "HARD"}, None), "always_on")
        self.assertEqual(pair_worker_class({"timing_fit": "LATER", "max_fit": "HARD"}, None), "night_only")

    def test_unfit_pairs_never_earn_workhorse_beyond_class(self):
        # EASY-only pair on a workhorse: class stays workhorse (user-confirmed),
        # the pair's own max_fit carries the limitation (labeling, not hiding)
        self.assertEqual(pair_worker_class({"timing_fit": "NOW", "max_fit": "EASY"}, "workhorse"), "workhorse")


class TestLabelPairs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_dir = M.FLEET_DIR
        M.FLEET_DIR = Path(self.tmp) / "fleet"
        self.old_log = P.bench_keys.BENCH_LOG
        P.bench_keys.BENCH_LOG = Path(self.tmp) / "bench.jsonl"
        P.bench_keys.BENCH_LOG.write_text(
            json.dumps({"model": "q", "tok_s": 55, "timing_fit": "NOW", "max_fit": "HARD",
                        "cold_load_s": 3, "host": "localhost", "bench_key": "q@localhost"}) + "\n" +
            json.dumps({"model": "big", "tok_s": 2, "timing_fit": "LATER", "max_fit": "HARD",
                        "cold_load_s": 40, "host": "localhost", "bench_key": "big@localhost"}) + "\n" +
            json.dumps({"model": "other", "tok_s": 9, "timing_fit": "LATER", "max_fit": "MEDIUM",
                        "cold_load_s": 9, "host": "box", "bench_key": "other@box"}) + "\n", encoding="utf-8")
        M.upsert_profile("localhost", machine_class="workhorse")

    def tearDown(self):
        M.FLEET_DIR = self.old_dir
        P.bench_keys.BENCH_LOG = self.old_log
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_labels_persist_host_scoped(self):
        prof = P.label_pairs("localhost")
        models = {p["model"] for p in prof["pairs"]}
        self.assertEqual(models, {"q", "big"})   # 'other' belongs to box, not leaked
        q = [p for p in prof["pairs"] if p["model"] == "q"][0]
        self.assertEqual(q["timing_fit"], "NOW")
        self.assertEqual(q["max_fit"], "HARD")
        self.assertEqual(q["tok_s"], 55)

    def test_class_data_survives_relabel(self):
        P.label_pairs("localhost")
        p = M.load_profile("localhost")
        self.assertEqual(p["class"], "workhorse")   # user consent untouched by bench refresh


class TestBestPair(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_dir = M.FLEET_DIR
        M.FLEET_DIR = Path(self.tmp) / "fleet"
        M.upsert_profile("box", machine_class="night_only", pairs=[
            {"model": "fast", "max_fit": "MEDIUM", "tok_s": 40},
            {"model": "strong", "max_fit": "HARD", "tok_s": 2},
            {"model": "tiny", "max_fit": "EASY", "tok_s": 90},
        ])

    def tearDown(self):
        M.FLEET_DIR = self.old_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_hard_lane_picks_hard_capable(self):
        self.assertEqual(best_pair_for_lane("box", "CLOUD_HARD")["model"], "strong")

    def test_easy_lane_picks_fastest_sufficient(self):
        # need EASY: tiny (EASY, 90 tok/s) and fast (MEDIUM, 40) both qualify; fastest wins
        self.assertEqual(best_pair_for_lane("box", "LOCAL")["model"], "tiny")

    def test_empty_profile_returns_none(self):
        self.assertIsNone(best_pair_for_lane("ghost", "LOCAL"))


if __name__ == "__main__":
    unittest.main()