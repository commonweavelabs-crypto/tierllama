"""End-to-end smoke: health -> fleet -> dispatch -> engines working together.
Run: python tests/_j12_smoke.py"""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tierllama import health, fleet, dispatch, engines
from tierllama.dispatch import dispatch_request

# 1. health: feed pressure; less-utilized node must rank first
fp = health.FleetPressure()
fp.feed("desktop", 0.95, now=100)
fp.feed("mac", 0.10, now=100)
rank = fp.ranking(now=101)
assert rank[0]["node_id"] == "mac", f"ranking wrong: {rank}"

# 2. fleet: upsert with local-fleet provenance, persists
tmp = Path(tempfile.mkdtemp()) / "fleet.json"
f = fleet.Fleet(store_path=tmp)
f.upsert("desktop", "<box-lan-ip>", 11434, models=["qwen3:4b"])
assert f.as_providers()[0]["provenance"] == "local-fleet"

# 3. dispatch: both nodes idle (equal pressure -> stable-id tie-break: desktop < mac)
nodes = [{"node_id": "mac", "host": "1.2.3.4", "port": 11434, "models": ["m"]},
         {"node_id": "desktop", "host": "1.2.3.5", "port": 11434, "models": ["m"]}]
r = dispatch_request(nodes, "m", {}, lambda n, b, dl: (True, "ok", 200))
assert r["ok"] and r["node_id"] == "desktop", r   # tie-break is stable id (desktop)

# 3b. with pressure on desktop (fresh samples for both), mac must win:
d = dispatch._pressure
now = __import__("time").time()
d.feed("desktop", 0.95, now=now)   # -> pressure 3
d.feed("mac", 0.05, now=now)       # fresh -> pressure 0
r2 = dispatch_request(nodes, "m", {}, lambda n, b, dl: (True, "ok", 200))
assert r2["ok"] and r2["node_id"] == "mac", r2   # mac (0) < desktop (3)

# 4. engines: example manifest loads
m = engines.get_engine("llamacpp-example")
assert m and m["name"] == "llamacpp-example"

print("SMOKE OK: health -> fleet -> dispatch (pressure-aware failover) -> engines, all functional")