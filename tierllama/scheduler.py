"""Tierllama scheduler (J13 BETA): dumb file-backed job queue.
Jev classifies; boring code schedules. Pure stdlib, no daemons - a 30s loop.

Queue file: logs/schedule.json - {"jobs": [job, ...]} with jobs shaped:
{id, created_at, due_at, lane, message, status, tries, meta}
status: pending -> due -> dispatched -> done | failed | cancelled
Beta gate: callers must check config.SCHEDULER["enabled"] before enqueueing.
"""
import json, threading, time, uuid, datetime, os
from pathlib import Path
from . import config
_SCHEDULER = lambda: config.SCHEDULER

ROOT = Path(__file__).parent.parent
QUEUE_PATH = Path(SCHEDULER.get("queue_path") or (ROOT / "logs" / "schedule.json"))

_lock = threading.Lock()

def _load():
    if not QUEUE_PATH.exists():
        return {"jobs": []}
    try:
        return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"jobs": []}

def _save(q):
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_PATH.write_text(json.dumps(q, indent=1, ensure_ascii=False), encoding="utf-8")

def _is_night(now=None):
    """True if now is inside the configured night window (handles midnight wrap)."""
    now = now or datetime.datetime.now()
    w = _SCHEDULER()["night_window"]
    h = now.hour + now.minute / 60.0
    s = int(w["start"][:2]) + int(w["start"][3:]) / 60.0
    e = int(w["end"][:2]) + int(w["end"][3:]) / 60.0
    return (h >= s and h < e) if s < e else (h >= s or h < e)

def enqueue(message, lane, due_at, title="job", meta=None):
    """Add a scheduled job. Beta-gated: raises RuntimeError when disabled."""
    if not _SCHEDULER().get("enabled"):
        raise RuntimeError("scheduler is a BETA feature and is disabled (config.SCHEDULER.enabled)")
    job = {"id": f"sch-{datetime.datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}",
           "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
           "due_at": due_at, "lane": lane, "message": message, "title": title,
           "status": "pending", "tries": 0, "meta": meta or {}}
    with _lock:
        q = _load(); q["jobs"].append(job); _save(q)
    return job

def resolve(job_id, due_at=None, lane=None, action="schedule"):
    """User answered a clarification: confirm/override due_at+lane, or run now, or cancel."""
    with _lock:
        q = _load()
        for j in q["jobs"]:
            if j["id"] == job_id and j["status"] in ("pending", "clarify"):
                if action == "cancel":
                    j["status"] = "cancelled"
                elif action == "now":
                    j["status"] = "due"; j["due_at"] = datetime.datetime.now().isoformat(timespec="seconds")
                else:
                    if due_at: j["due_at"] = due_at
                    if lane: j["lane"] = lane
                    j["status"] = "pending"
                _save(q)
                return j
    raise KeyError(f"job {job_id} not found or not resolvable")

def cancel(job_id):
    return resolve(job_id, action="cancel")

def due_jobs(now=None):
    """Jobs whose due_at has passed and are pending (due loop consumes these)."""
    now = (now or datetime.datetime.now()).isoformat(timespec="seconds")
    with _lock:
        q = _load()
        due = [j for j in q["jobs"] if j["status"] in ("pending", "clarify") and j["due_at"] <= now]
        for j in due:
            j["status"] = "due"
        _save(q)
    return due

def _dispatch(j):
    from .adapters import dispatch
    from . import ladder  # escalation ladder stays active for scheduled jobs
    j["tries"] += 1
    try:
        r = dispatch(j["lane"], j["message"])
        j["last_result"] = {"status": r.get("status"), "ts": datetime.datetime.now().isoformat(timespec="seconds")}
        j["status"] = "dispatched" if r.get("status") in ("ok", "queued") else "pending"
    except Exception as e:
        j["last_result"] = {"error": str(e)[:200]}
        j["status"] = "pending"
    if j["tries"] >= _SCHEDULER()["max_tries"] and j["status"] != "dispatched":
        j["status"] = "failed"
    return j

def tick():
    """One due-loop pass: dispatch everything due. Returns summary."""
    due = due_jobs()
    out = []
    for j in due:
        _dispatch(j)
        with _lock:
            q = _load()
            for i, qj in enumerate(q["jobs"]):
                if qj_id := (qj["id"] if False else None):
                    pass
            for i, qj in enumerate(q["jobs"]):
                if qj["id"] == j["id"]:
                    q["jobs"][i] = j
            _save(q)
        out.append(j)
    return {"dispatched": len(out), "jobs": [{"id": j["id"], "status": j["status"]} for j in out]}

def start_background(interval_s=None):
    """Daemon thread running tick() every due_loop_s. For webapp integration."""
    interval = interval_s or _SCHEDULER()["due_loop_s"]
    def loop():
        while True:
            try:
                if _SCHEDULER().get("enabled"):
                    tick()
            except Exception:
                pass
            time.sleep(interval)
    th = threading.Thread(target=loop, daemon=True)
    th.start()
    return th

def list_jobs(status=None):
    with _lock:
        q = _load()
    jobs = q["jobs"]
    if status:
        jobs = [j for j in jobs if j["status"] == status]
    return sorted(jobs, key=lambda j: (j.get("due_at") or "", j["created_at"]))
