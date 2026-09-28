"""J13 v2 task 2: worker classes for the scheduler.

Adapted from NVIDIA Personal-AI-Router, Apache-2.0 (node availability windows
in the job-scheduler) — but Tierllama's version is USER-DECLARED machine
roles, not discovered ones. J16's machine_profile (user-confirmed classes)
will replace this mapping; until then it's a config-declared PROVISIONAL
placeholder, documented as such everywhere it's read.

Classes:
- always_on  : dispatch any time (default for every lane)
- night_only : dispatch ONLY inside the configured night_window
              (the box: slow but free, belongs to the night)
- workhorse  : dispatch any time (reserved for J16's user-confirmed daily
               machine; behaves like always_on in v2)

Policy decisions (never silent):
- a night_only job whose due_at falls OUTSIDE the window is NOT silently
  deferred forever: it stays pending and the tick records a
  "waiting_for_window" note in the decision log, dispatching at the next
  window open. Deadlines are user promises — the shift is visible, not silent.
"""
from . import config

_SCHEDULER = lambda: config.SCHEDULER

# Provisional mapping lane -> worker class. J16 machine_profile replaces this.
# BOX = the mini box = the night machine (its whole identity in our stack).
PROVISIONAL_LANE_CLASS = {
    "BOX": "night_only",
    "LOCAL": "always_on",
    "CLOUD_MEDIUM": "always_on",
    "CLOUD_HARD": "always_on",
    "FALLBACK": "always_on",
}

def class_for_lane(lane: str, host: str | None = None) -> str:
    """Worker class for a lane. Unknown lane -> always_on (safest for deadlines:
    never blocks a job the user explicitly scheduled).
    J16: when a machine_profile exists for `host`, its user-confirmed class
    wins over the PROVISIONAL lane mapping (consented data > heuristic)."""
    if host:
        try:
            from .machines import load_profile
            prof = load_profile(host)
            if prof and prof.get("class"):
                return prof["class"]
        except Exception:
            pass  # machines offline/unreadable -> provisional mapping (documented fallback)
    return PROVISIONAL_LANE_CLASS.get(lane, "always_on")

def can_dispatch_now(lane: str, now=None, host: str | None = None) -> tuple[bool, str]:
    """(dispatchable, reason). night_only lanes dispatch only in-window.
    J16: host's machine_profile class (if any) overrides the lane mapping."""
    from .scheduler import _is_night
    cls = class_for_lane(lane, host)
    if cls == "always_on":
        return True, "always_on"
    if cls == "night_only":
        if _is_night(now):
            return True, "night_only in window"
        return False, "night_only waiting_for_window"
    # workhorse behaves like always_on in v2
    return True, cls

def maybe_shift_due(job: dict, now=None) -> dict | None:
    """For a due night_only job outside the window: compute the next window
    open time and return an updated job (due_at shifted, visible reason).
    Returns None if the job is dispatchable now (no shift needed)."""
    ok, reason = can_dispatch_now(job["lane"], now)
    if ok:
        return None
    from .scheduler import _SCHEDULER
    w = _SCHEDULER()["night_window"]
    now_dt = now or __import__("datetime").datetime.now()
    s_h, s_m = int(w["start"][:2]), int(w["start"][3:])
    candidate = now_dt.replace(hour=s_h, minute=s_m, second=0, microsecond=0)
    if candidate <= now_dt:  # window start already passed today -> next open is tomorrow
        import datetime as _dt
        candidate += _dt.timedelta(days=1)
    shifted = dict(job)
    shifted["due_at"] = candidate.isoformat(timespec="seconds")
    shifted["rescheduled_reason"] = "night_only job due outside night window - shifted to next window open (visible, not silent)"
    return shifted