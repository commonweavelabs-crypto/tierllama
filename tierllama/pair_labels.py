"""J16 Gap C: pair labeling — every model@machine pair gets its fit labels.

The J16 spec's core insight (Gui's box = 4GB-class hardware running a 27B):
the CATEGORY is the PAIR (hardware + model), not hardware alone. The bench
already measures the pair (Gap A keys); this module LABELS each pair and
derives the J13 worker classes from labeled pairs + user-confirmed machine
class:

  pair NOW-fit + HARD-capable on user's daily machine   -> workhorse
  pair LATER-fit + HARD-capable                          -> always_on or night_only (user picks)
  cloud models                                           -> cloud_scheduled

Also provides profile-aware worker-class resolution used by the scheduler:
machine_profile class wins; PROVISIONAL lane mapping remains the fallback
for un-profiled machines (documented in worker_classes.py).
"""
from . import machines, bench_keys

def label_pairs(host: str) -> dict | None:
    """Label all measured pairs for a host from bench data (Gap A) and
    persist them onto the machine profile. Returns the updated profile
    or None if the host has no profile."""
    bench = bench_keys.load_bench_by_key()
    return machines.attach_pairs_from_bench(host, bench)

def pair_worker_class(pair: dict, machine_class: str | None) -> str:
    """Derive a worker class for ONE model@machine pair (J16 spec mapping)."""
    if machine_class == "cloud_scheduled" or pair.get("cloud"):
        return "cloud_scheduled"
    now_fit = pair.get("timing_fit") == "NOW"
    hard_capable = pair.get("max_fit") in ("MEDIUM", "HARD")
    if machine_class == "workhorse":
        return "workhorse" if (now_fit and hard_capable) else "workhorse"  # user's daily machine stays workhorse; unfit pairs flagged via max_fit
    if machine_class in ("always_on", "night_only"):
        # spec: LATER-fit + HARD-capable -> always_on or night_only (user picked already)
        return machine_class
    # no machine class: derive from the pair alone (conservative)
    if now_fit:
        return "always_on"
    return "night_only"

def best_pair_for_lane(host: str, lane: str) -> dict | None:
    """The best measured pair on this host for a lane's difficulty needs.
    lane -> required max_fit: LOCAL/HARD work -> HARD; MEDIUM -> MEDIUM+;
    EASY -> EASY+."""
    prof = machines.load_profile(host)
    if not prof:
        return None
    need = {"CLOUD_HARD": "HARD", "HARD": "HARD"}.get(lane, "MEDIUM" if lane in ("CLOUD_MEDIUM",) else "EASY")
    ranked = [p for p in (prof.get("pairs") or [])
              if p.get("max_fit") in ("EASY", "MEDIUM", "HARD")]
    def rank(p):
        # MIN wins: 0 = qualifies for the lane's need; -tok_s so fastest qualifies first
        order = {"EASY": 0, "MEDIUM": 1, "HARD": 2}
        return (0 if order[p.get("max_fit")] >= order[need] else 1,
                -(p.get("tok_s") or 0))
    return min(ranked, key=rank) if ranked else None