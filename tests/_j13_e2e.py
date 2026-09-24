
import sys, json
sys.path.insert(0, r"C:\Users\Guilherme\tierllama")
from dotenv import load_dotenv
load_dotenv(r"C:\Users\Guilherme\AppData\Local\hermes\.env")
import tierllama.config as cfg
cfg.SCHEDULER = dict(cfg.SCHEDULER, enabled=True, queue_path=r"C:\Users\Guilherme\tierllama\logs\schedule_test.json")
import tierllama.router as R
from pathlib import Path
Path(r"C:\Users\Guilherme\tierllama\logs\schedule_test.json").unlink(missing_ok=True)
r4 = R.route("get it done soon", dispatch=True)
print("soon ->", r4.get("needs_clarification"), "| lane:", r4.get("lane"), "| dispatched:", r4.get("dispatched"))
r5 = R.route("hi", dispatch=True)
print("plain -> lane:", r5.get("lane"), "| dispatched:", r5.get("dispatched"), "| when:", r5.get("when"))
