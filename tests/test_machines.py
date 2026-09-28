"""Tests for tierllama/machines.py (J16 Gap B: machine profiles, consent boundary).
Run: python -m unittest tests.test_machines -v"""
import sys, unittest, tempfile, shutil, json
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).parent.parent))

from tierllama import machines as M
from tierllama.machines import upsert_profile, load_profile, load_all, worker_class_for


class TestProfiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_dir = M.FLEET_DIR
        M.FLEET_DIR = Path(self.tmp) / "fleet"

    def tearDown(self):
        M.FLEET_DIR = self.old_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_upsert_creates_and_persists(self):
        p = upsert_profile("box", name="The Mini Box", machine_class="night_only",
                           windows={"start": "00:00", "end": "08:00"})
        self.assertEqual(p["class"], "night_only")
        self.assertEqual(p["class_confirmed_by"], "user")   # consent stamp
        on_disk = json.loads(M.FLEET_DIR.joinpath("box.json").read_text(encoding="utf-8"))
        self.assertEqual(on_disk["name"], "The Mini Box")

    def test_class_validation(self):
        with self.assertRaises(ValueError):
            upsert_profile("x", machine_class="i-made-this-up")

    def test_class_never_guessed(self):
        # profile without a class must have NO class field at all — no inference
        upsert_profile("mystery", name="Unknown Box")
        p = load_profile("mystery")
        self.assertNotIn("class", p)

    def test_update_preserves_user_data(self):
        upsert_profile("box", name="Mini Box", machine_class="night_only")
        upsert_profile("box", name="Renamed Box")   # update name only
        p = load_profile("box")
        self.assertEqual(p["class"], "night_only")   # class survives
        self.assertEqual(p["name"], "Renamed Box")

    def test_load_all_and_delete(self):
        upsert_profile("a", machine_class="always_on")
        upsert_profile("b", machine_class="workhorse")
        allp = load_all()
        self.assertEqual(set(allp.keys()), {"a", "b"})
        self.assertTrue(M.delete_profile("a"))
        self.assertEqual(set(load_all().keys()), {"b"})
        self.assertFalse(M.delete_profile("ghost"))

    def test_unknown_host_returns_none(self):
        self.assertIsNone(load_profile("nonexistent"))


class TestWorkerClassHookup(unittest.TestCase):
    """J13 hookup: machine_profile replaces provisional mapping when present."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_dir = M.FLEET_DIR
        M.FLEET_DIR = Path(self.tmp) / "fleet"

    def tearDown(self):
        M.FLEET_DIR = self.old_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_profile_class_wins(self):
        # BOX would provisionally be night_only, but the user confirmed workhorse
        upsert_profile("box", machine_class="workhorse")
        self.assertEqual(worker_class_for("box", "BOX"), "workhorse")

    def test_unprofiled_falls_back_to_provisional(self):
        self.assertEqual(worker_class_for("unprofiled-host", "BOX"), "night_only")
        self.assertEqual(worker_class_for("unprofiled-host", "LOCAL"), "always_on")


class TestPairsFromBench(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old_dir = M.FLEET_DIR
        M.FLEET_DIR = Path(self.tmp) / "fleet"
        upsert_profile("localhost", machine_class="workhorse")

    def tearDown(self):
        M.FLEET_DIR = self.old_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pairs_attached_only_for_this_host(self):
        bench = {"q@localhost": {"model": "q", "timing_fit": "NOW", "max_fit": "HARD",
                                 "tok_s": 55, "cold_load_s": 3.1},
                 "k@box": {"model": "k", "timing_fit": "LATER", "max_fit": "HARD",
                           "tok_s": 2, "cold_load_s": 40}}
        prof = M.attach_pairs_from_bench("localhost", bench)
        models = [p["model"] for p in prof["pairs"]]
        self.assertIn("q", models)
        self.assertNotIn("k", models)   # other machine's bench not leaked in

    def test_no_profile_returns_none(self):
        self.assertIsNone(M.attach_pairs_from_bench("ghost", {}))


if __name__ == "__main__":
    unittest.main()