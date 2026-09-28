"""J14 task 4: canary probes — Gui's downgrade idea.

Sample canary_pct of HARD-classified traffic to the tier below. If the
down-tiered output is USABLE (graded by bench-style deterministic probes)
canary_successes times, promote that class one tier DOWN.

Consent-gated per spec: canary_pct = 0 while CAPABILITY.enabled is False —
and the percentage itself only means anything when the gate is ON. Every
canary attempt is LOGGED (decision log carries canary=true) — never silent.

Usability grading: delegates to bench.py's probe graders where the output
matches a probe shape; generic fallback = non-empty content that isn't an
error. (Semantic quality = J14 v2 / telemetry flywheel.)
"""
import random, json
from pathlib import Path
from . import config

CAP = lambda: config.CAPABILITY

def should_canary(difficulty: str, rng=None) -> bool:
    """True if this request should be sampled down a tier.
    Gate: CAPABILITY.enabled AND canary_pct > 0 AND difficulty == HARD.
    Deterministic-off when the gate is off (consent rule).
    NOTE: rng=0.0 is a valid roll (0% < pct) — never treat 0 as missing."""
    c = CAP()
    if not c.get("enabled") or c.get("canary_pct", 0) <= 0:
        return False
    if difficulty != "HARD":
        return False
    roll = random.random() if rng is None else rng
    return roll * 100 < c["canary_pct"]

def canary_tier(tier: str) -> str:
    """One tier DOWN from HARD = MEDIUM (never below EASY, never from non-HARD)."""
    order = ["EASY", "MEDIUM", "HARD", "EXPERT"]
    if tier not in order or tier == "EASY":
        return tier
    return order[order.index(tier) - 1]

def grade_usable(prompt: str, response: str) -> bool:
    """Usable = passes a deterministic check when the prompt matches a known
    probe shape; otherwise non-empty non-error content. Same philosophy as
    bench.py grading (deterministic checks, no LLM judging)."""
    if not response or not response.strip():
        return False
    low = response.lower()
    if "error" in low[:20] and len(low) < 60:
        return False
    # reuse bench probe checks when the prompt is a bench probe:
    from .bench import PROBES
    for _, p, check in PROBES:
        if prompt.strip() == p.strip():
            txt = response
            try:
                return bool(check(txt))
            except Exception:
                return False
    return True   # generic content: usable by default

class CanaryTracker:
    """Tracks per-class canary successes toward promotion."""
    def __init__(self, path=None):
        self.path = path or (Path(__file__).parent.parent / "logs" / "canary_state.json")
        self.state = {}
        if self.path.exists():
            try:
                self.state = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.state = {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=1), encoding="utf-8")

    def note(self, class_key: str, usable: bool, now_iso: str):
        st = self.state.setdefault(class_key, {"successes": 0, "attempts": 0, "history": []})
        st["attempts"] += 1
        if usable:
            st["successes"] += 1
        st["history"] = (st.get("history") or [])[-19:] + [{"at": now_iso, "usable": usable}]
        self._save()

    def should_promote(self, class_key: str) -> bool:
        return self.state.get(class_key, {}).get("successes", 0) >= CAP()["canary_successes"]

    def promote(self, class_key: str, from_tier: str, to_tier: str, now_iso: str) -> dict:
        st = self.state.setdefault(class_key, {})
        st["promoted"] = {"at": now_iso, "from": from_tier, "to": to_tier,
                          "reason": f"{st.get('successes', 0)} usable canary outputs (down-tier held)"}
        st["successes"] = 0    # reset the counter after promotion
        self._save()
        return st

