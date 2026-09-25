"""Tests for tierllama/grid_health.py (J12+ T1 wiring: health into the provider
grid, informationally). Run: python -m unittest tests.test_grid_health -v"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tierllama import grid_health as G


class TestProviderNode(unittest.TestCase):
    def test_local_maps_localhost(self):
        self.assertEqual(G.provider_node(None), "localhost")
        self.assertEqual(G.provider_node("local"), "localhost")
        self.assertEqual(G.provider_node("LOCAL"), "localhost")

    def test_fleet_provider_maps_fleet_node(self):
        providers = [{"name": "local-fleet-desktop", "provenance": "local-fleet"}]
        self.assertEqual(G.provider_node("local-fleet-desktop", providers),
                         "fleet-local-fleet-desktop")

    def test_cloud_has_no_node(self):
        providers = [{"name": "openai", "provenance": "seed"}]
        self.assertIsNone(G.provider_node("openai", providers))


class TestAttachPressure(unittest.TestCase):
    def test_informational_only(self):
        # unknown provider: neutral, record keys otherwise untouched
        rec = {"lane": "LOCAL", "model": "qwen3:4b"}
        out = G.attach_pressure(dict(rec), "unknown-provider")
        self.assertEqual(out["gpu_pressure"]["pressure"], None)  # unknown -> no node
        self.assertIn("lane", out)
        self.assertIn("model", out)

    def test_local_provider_pressure_reflects_samples(self):
        import time as _t
        G.gpu_sample("localhost", 0.95, now=_t.time())   # fresh real-clock sample
        out = G.attach_pressure({}, "local")
        self.assertEqual(out["gpu_pressure"]["pressure"], 3)
        self.assertEqual(out["gpu_pressure"]["provider"], "local")


class TestSnapshot(unittest.TestCase):
    def setUp(self):
        # isolate module state: fresh registry + never-sampled flag per test
        G._pressure = G._health.FleetPressure()
        G._ever_sampled = False

    def test_empty_fleet_writes_nothing(self):
        self.assertIsNone(G.snapshot_line())

    def test_line_after_sample(self):
        G.gpu_sample("localhost", 0.9)
        line = G.snapshot_line()
        self.assertIsNotNone(line)
        self.assertIn("pressure", line)

    def test_write_creates_log(self):
        import tempfile
        from pathlib import Path as P
        G.gpu_sample("localhost", 0.5)
        # redirect ROOT log under a temp dir via monkeypatching ROOT
        old = G.ROOT
        try:
            G.ROOT = Path(tempfile.mkdtemp())
            G.snapshot_write()
            self.assertTrue((G.ROOT / "logs" / "health.jsonl").exists())
        finally:
            G.ROOT = old


if __name__ == "__main__":
    unittest.main()