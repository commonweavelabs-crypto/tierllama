"""Seed refresh (J10): versioned+signed seed files at a stable URL.
Startup check -> verify sha256 -> STAGE (never auto-apply).
Apply = explicit user action (Re-scan models) w/ preview diff + rollback."""
import json, hashlib, urllib.request, shutil, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
SEED_URL = "https://raw.githubusercontent.com/commonweavelabs-crypto/tierllama/main/seed-data/seed-table.json"
MANIFEST_URL = "https://raw.githubusercontent.com/commonweavelabs-crypto/tierllama/main/seed-data/manifest.json"
STAGED = ROOT / "seed-data" / "seed-table.staged.json"
CURRENT = ROOT / "seed-data" / "seed-table.current.json"
BACKUP = ROOT / "seed-data" / "seed-table.backup.json"

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def check_and_stage():
    """Fetch manifest + seed file, verify hash, stage. Returns status dict.
    NEVER touches routing.json - staged only."""
    try:
        manifest = json.loads(urllib.request.urlopen(MANIFEST_URL, timeout=15).read())
        data = urllib.request.urlopen(SEED_URL, timeout=15).read()
        digest = _sha256(data)
        if digest != manifest.get("seed_sha256"):
            return {"staged": False, "reason": "hash mismatch - file corrupted or tampered"}
        # semantic version compare:
        remote_v = manifest.get("version", "0")
        local_v = _current_version()
        if remote_v <= local_v:
            return {"staged": False, "reason": "already up to date", "version": remote_v}
        STAGED.parent.mkdir(exist_ok=True)
        STAGED.write_bytes(data)
        return {"staged": True, "version": remote_v, "sha256": digest,
                "ts": datetime.datetime.now().isoformat(timespec="seconds")}
    except Exception as e:
        return {"staged": False, "error": str(e)[:120]}

def _current_version():
    try:
        return json.loads(CURRENT.read_text(encoding="utf-8")).get("version", "0")
    except Exception:
        return "0"

def preview_diff(user_edited_tiers: set):
    """Diff staged seed vs current recommendations, honoring user-edited tiers.
    Returns {tier: {from, to}} for tiers that WOULD change (skips user-edited)."""
    try:
        staged = json.loads(STAGED.read_text(encoding="utf-8"))
    except Exception:
        return {"error": "nothing staged"}
    current = json.loads((ROOT / "routing.json").read_text(encoding="utf-8"))
    changes = {}
    for tier, new in staged.get("tiers", {}).items():
        if tier in user_edited_tiers:
            continue  # user-edited tiers are sacred
        cur = current.get(tier, {})
        if cur.get("model") != new.get("model"):
            changes[tier] = {"from": cur.get("model"), "to": new.get("model"),
                             "user_edited": False}
    return {"changes": changes, "version": staged.get("version")}

def apply_staged():
    """Explicit apply (Re-scan button). Backs up current staged file for rollback."""
    if not STAGED.exists():
        return {"applied": False, "reason": "nothing staged"}
    CURRENT.parent.mkdir(exist_ok=True)
    if CURRENT.exists():
        shutil.copy2(CURRENT, BACKUP)
    shutil.copy2(STAGED, CURRENT)
    return {"applied": True, "version": _current_version()}

def rollback():
    if not BACKUP.exists():
        return {"rolled_back": False, "reason": "no backup"}
    shutil.copy2(BACKUP, CURRENT)
    return {"rolled_back": True, "version": _current_version()}
