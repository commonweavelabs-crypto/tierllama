"""Tests for tierllama/engines.py (J12+ T4, manifest-driven engines).
Run: python -m unittest tests.test_engines -v"""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tierllama import engines as E

EXAMPLE = E.ENGINES_DIR / "llamacpp-example.manifest.json"


class TestManifests(unittest.TestCase):
    def test_example_manifest_validates(self):
        m = E.load_manifest(EXAMPLE)
        self.assertEqual(m["name"], "llamacpp-example")
        self.assertEqual(m["endpoints"]["dialect"], "openai")

    def test_list_manifests_reports(self):
        out = E.list_manifests()
        self.assertTrue(any(x["ok"] and x["name"] == "llamacpp-example" for x in out))

    def test_get_engine(self):
        m = E.get_engine("llamacpp-example")
        self.assertIsNotNone(m)
        self.assertIsNone(E.get_engine("does-not-exist"))

    def test_invalid_manifest_rejected(self):
        import tempfile, json
        bad = {"display_name": "no name key"}   # missing required 'name'
        p = Path(tempfile.NamedTemporaryFile(suffix=".manifest.json", delete=False).name)
        p.write_text(json.dumps(bad), encoding="utf-8")
        try:
            with self.assertRaises(ValueError):
                E.load_manifest(p)
        finally:
            p.unlink(missing_ok=True)

    def test_bad_kind_rejected(self):
        import tempfile, json
        bad = {"name": "x", "kind": "wasm", "endpoints": {"chat": "/c", "models": "/m", "dialect": "openai"}}
        p = Path(tempfile.NamedTemporaryFile(suffix=".manifest.json", delete=False).name)
        p.write_text(json.dumps(bad), encoding="utf-8")
        try:
            with self.assertRaises(ValueError):
                E.load_manifest(p)
        finally:
            p.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()