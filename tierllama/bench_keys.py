"""J16 Gap A: machine dimension in bench data — key becomes model@host.

Every bench record now carries `host` (the machine the measurement was taken
on) and `bench_key` = f"{model}@{host}". Migration: the 24 pre-J16 entries
were measured on THIS machine (localhost) — the docstring always promised
model@machine; entries just never carried it. Migration stamps them with
host="localhost" and writes a migration note (documented assumption).
"""
import json, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
BENCH_LOG = ROOT / "logs" / "bench.jsonl"

def local_host_id() -> str:
    """This machine's identity for bench keys. v1 = 'localhost' (the machine
    running tierllama); J16 machines.py can rename it via machine_profile."""
    return "localhost"

def bench_key(model: str, host: str | None = None) -> str:
    return f"{model}@{host or local_host_id()}"

def stamp_host(record: dict, host: str | None = None) -> dict:
    """Add host + bench_key to a bench record (mutates a copy, returns it)."""
    out = dict(record)
    h = host or local_host_id()
    out["host"] = h
    out["bench_key"] = bench_key(out["model"], h)
    return out

def migrate_existing() -> dict:
    """One-time migration: stamp host=localhost + bench_key on every record
    missing them, rewrite bench.jsonl. Idempotent. Returns a report."""
    if not BENCH_LOG.exists():
        return {"records": 0, "migrated": 0, "note": "no bench log"}
    lines = BENCH_LOG.read_text(encoding="utf-8").strip().split("\n")
    out_lines = []
    migrated = 0
    already = 0
    for ln in lines:
        if not ln.strip():
            continue
        d = json.loads(ln)
        if "host" in d and "bench_key" in d:
            already += 1
            out_lines.append(json.dumps(d))
            continue
        d = stamp_host(d)
        d["migration_note"] = "pre-J16 record: measured on localhost (documented assumption, 2026-09-29)"
        migrated += 1
        out_lines.append(json.dumps(d))
    BENCH_LOG.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return {"records": migrated + already, "migrated": migrated, "already_stamped": already,
            "assumption": "all pre-J16 records measured on localhost (tierllama machine)"}

def load_bench_by_key() -> dict:
    """Latest record per bench_key (newer wins). Returns {bench_key: record}."""
    if not BENCH_LOG.exists():
        return {}
    out = {}
    for ln in BENCH_LOG.read_text(encoding="utf-8").strip().split("\n"):
        if not ln.strip():
            continue
        d = json.loads(ln)
        if "bench_key" not in d:
            d = stamp_host(d)
        out[d["bench_key"]] = d   # later lines overwrite = newer wins
    return out