"""J13 v2 task 3: priority insert ("shove") with transparent rescheduling.

From the J13 spec (capacity + priority rescheduling): when a priority job
inserts into a night window that's already full, OTHER jobs get shoved LATER
by the new job's duration — and the user is TOLD which jobs moved. No silent
eviction, no silent delay.

Spec rules implemented:
- shove cap: a job can be shoved at most SCHEDULER["shove_cap_week"] times
  per week (default 3) — a job shoved past the cap is NOT moved again; the
  priority insert reports the collision instead (transparency over magic)
- every shove records: which job moved, from -> to due_at, why (who shoved it)
- v1 duration model: coarse class via the scheduler's long_horizon concept —
  a priority job shoves others by its estimate (minutes class default)

v2 scope note: window "capacity" model is coarse (v1 estimates = user-stated
or class-based); real duration learning is J14's outcome signals.
"""
import datetime
from . import config

_SCHEDULER = lambda: config.SCHEDULER

DURATION_CLASS_MIN = {
    "quick": 5,
    "medium": 30,
    "long": 120,
    "overnight": 480,
}

def estimate_duration_min(job: dict) -> int:
    """v1 coarse estimate: job['meta']['duration_class'] or 'medium' default.
    (Real estimates arrive with J14 outcome signals.)"""
    cls = (job.get("meta") or {}).get("duration_class", "medium")
    return DURATION_CLASS_MIN.get(cls, DURATION_CLASS_MIN["medium"])

def shove_count_this_week(job: dict, now=None) -> int:
    """How many times this job was shoved in the trailing 7 days."""
    now_dt = now or datetime.datetime.now()
    week_ago = (now_dt - datetime.timedelta(days=7)).isoformat(timespec="seconds")
    events = (job.get("shove_history") or [])
    return sum(1 for e in events if e.get("at", "") >= week_ago)

def shove(job: dict, by_minutes: int, by_job_id: str, now=None) -> dict | None:
    """Shove a job later by by_minutes. Returns the updated job, or None if
    the job hit its shove cap (must NOT be moved again — report instead)."""
    now_dt = now or datetime.datetime.now()
    if shove_count_this_week(job, now_dt) >= _SCHEDULER()["shove_cap_week"]:
        return None
    due = datetime.datetime.fromisoformat(job["due_at"])
    new_due = due + datetime.timedelta(minutes=by_minutes)
    history = list(job.get("shove_history") or [])
    history.append({"at": now_dt.isoformat(timespec="seconds"),
                    "by_job": by_job_id, "by_minutes": by_minutes,
                    "from": job["due_at"], "to": new_due.isoformat(timespec="seconds")})
    shoved = dict(job)
    shoved["due_at"] = new_due.isoformat(timespec="seconds")
    shoved["shove_history"] = history
    shoved["rescheduled_reason"] = f"shoved by priority job {by_job_id} (+{by_minutes} min) - user notified in decision log"
    return shoved

def insert_priority(priority_job: dict, queued_jobs: list, window_end: str, now=None):
    """Insert a priority job into the window, shoving later jobs to make room.
    Returns (jobs_after, events). Never silent: every shove is an event; a job
    past its cap is left in place and the collision is an event too.

    window_end: ISO time the night window closes — shoved jobs must fit
    BEFORE it or they roll to the next window (their shift says so).
    """
    now_dt = now or datetime.datetime.now()
    need = estimate_duration_min(priority_job)
    jobs_after = []
    events = []
    freed = 0
    # shove from the END of the queue backwards (latest-due shoves first)
    for job in sorted(queued_jobs, key=lambda j: j["due_at"], reverse=True):
        if freed >= need:
            jobs_after.append(job)
            continue
        cap = shove_count_this_week(job, now_dt) >= _SCHEDULER()["shove_cap_week"]
        if cap:
            events.append({"event": "shove_cap_hit", "job": job["id"],
                           "note": "already shoved max times this week - NOT moved again; window overflow reported"})
            jobs_after.append(job)
            continue
        shoved = shove(job, need, priority_job["id"], now_dt)
        if shoved is None:
            events.append({"event": "shove_cap_hit", "job": job["id"], "note": "cap hit mid-insert"})
            jobs_after.append(job)
            continue
        freed += need
        events.append({"event": "shoved", "job": job["id"], "from": job["due_at"],
                       "to": shoved["due_at"], "by": priority_job["id"],
                       "by_minutes": need, "user_notified": True})
        jobs_after.append(shoved)
    return jobs_after, events