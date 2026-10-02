"""J20.5 dogfood summary — CLI + webapp panel data source.
Agreement analytics on live-traffic pairs: Jev vs agent judgment."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DECISIONS = ROOT / "logs" / "decisions.jsonl"
PAIRS = ROOT / "logs" / "dogfood_pairs.jsonl"
HOOK_LOG = Path.home() / ".hermes" / "hooks" / "tierllama-dogfood" / "dogfood.log"


def summary(n: int = 200) -> dict:
    """Agreement of MY ratings vs JEV's, from dogfood_pairs.jsonl (latest n)."""
    rows = []
    if PAIRS.exists():
        lines = PAIRS.read_text(encoding="utf-8").splitlines()
        for l in lines[-n:]:
            try:
                rows.append(json.loads(l))
            except Exception:
                continue
    out = {"pairs": len(rows)}
    if rows:
        for dim in ("difficulty", "timing"):
            agrees = sum(1 for r in rows
                         if (r.get("mine") or {}).get(dim) == (r.get("jev") or {}).get(dim))
            out[f"{dim}_agreement_pct"] = round(100.0 * agrees / len(rows), 1)
        # disagreement buckets (the distiller's grain, privacy-law: bucket only)
        from tierllama.clarify import bucket_for
        buckets: dict[str, int] = {}
        for r in rows:
            mine = (r.get("mine") or {})
            jev = (r.get("jev") or {})
            for dim in ("difficulty", "timing"):
                if mine.get(dim) and jev.get(dim) and mine[dim] != jev[dim]:
                    b = bucket_for(r.get("message") or "", dim)
                    buckets[b] = buckets.get(b, 0) + 1
        out["disagreement_buckets"] = sorted(buckets.items(), key=lambda kv: -kv[1])
    # hook health: taps captured vs router_down
    taps = router_down = 0
    last_tap = None
    if HOOK_LOG.exists():
        for l in HOOK_LOG.read_text(encoding="utf-8").splitlines()[-n:]:
            try:
                r = json.loads(l)
            except Exception:
                continue
            taps += 1
            if r.get("router_down"):
                router_down += 1
            last_tap = r.get("ts")
    out["hook_taps"] = taps
    out["router_down_taps"] = router_down
    out["last_tap_ts"] = last_tap
    return out


if __name__ == "__main__":
    print(json.dumps(summary(), indent=1))