"""Tierllama engine manifest loader (J12+ T4).

Schema + example live in engines/. SCOPE (deliberate, per goal): schema + loader
stub + validation only. Engine auto-detection, install, and start/stop are NOT
implemented in this milestone - this module exists so future engine work starts
from a stable data contract.

Adapted from NVIDIA Personal-AI-Router, Apache-2.0 (nvpair-engine-manager:
"adding an engine is a JSON manifest, not code").
https://github.com/NVIDIA/Personal-AI-Router
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
ENGINES_DIR = ROOT / "engines"
SCHEMA_PATH = ENGINES_DIR / "tierllama-engine-manifest.schema.json"


def load_manifest(path: Path) -> dict:
    """Load + validate one engine manifest. Raises ValueError with a precise
    message on any shape error. Minimal validation (no jsonschema dependency):
    required keys, enum membership, placeholder sanity in start_command."""
    m = json.loads(path.read_text(encoding="utf-8"))
    for key in ("name", "kind", "endpoints"):
        if key not in m:
            raise ValueError(f"manifest {path.name}: missing required key '{key}'")
    if not (m["name"][0].isalpha() and m["name"].replace("-", "").isalnum()):
        raise ValueError(f"manifest {path.name}: 'name' must be kebab-case")
    if m["kind"] not in ("ollama", "openai-compat", "llama-swap"):
        raise ValueError(f"manifest {path.name}: kind '{m['kind']}' not in enum")
    ep = m["endpoints"]
    for key in ("chat", "models", "dialect"):
        if key not in ep:
            raise ValueError(f"manifest {path.name}: endpoints.{key} required")
    if ep["dialect"] not in ("openai", "ollama"):
        raise ValueError(f"manifest {path.name}: endpoints.dialect must be openai|ollama")
    sc = m.get("runtime", {}).get("start_command")
    if sc is not None:
        if not isinstance(sc, list) or not all(isinstance(x, str) for x in sc):
            raise ValueError(f"manifest {path.name}: runtime.start_command must be argv list")
        joined = " ".join(sc)
        for placeholder in ("{port}", "{bind}"):
            if placeholder in joined and "runtime" not in m:
                raise ValueError(f"manifest {path.name}: {placeholder} used but runtime block missing")
    return m


def list_manifests() -> list[dict]:
    """All valid manifests in engines/ (invalid ones are reported, not raised)."""
    out = []
    if not ENGINES_DIR.exists():
        return out
    for f in sorted(ENGINES_DIR.glob("*.manifest.json")):
        try:
            m = load_manifest(f)
            out.append({"file": f.name, "ok": True, "name": m["name"], "kind": m["kind"]})
        except Exception as e:
            out.append({"file": f.name, "ok": False, "error": str(e)[:150]})
    return out


def get_engine(name: str) -> dict | None:
    """Manifest by engine name, or None."""
    for f in ENGINES_DIR.glob("*.manifest.json"):
        try:
            m = load_manifest(f)
            if m["name"] == name:
                return m
        except Exception:
            continue
    return None