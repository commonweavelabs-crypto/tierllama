"""tierllama CLI: route | tail | discover | doctor"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "route"
    if cmd == "route":
        from tierllama.router import route
        msg = " ".join(sys.argv[2:]) or sys.stdin.read().strip()
        if len(msg) > 8192:
            print(json.dumps({"error": "message too long (max 8KB)"})); return
        print(json.dumps(route(msg), indent=2))
    elif cmd == "tail":
        log = Path(__file__).parent / "logs" / "decisions.jsonl"
        if log.exists():
            for l in log.read_text().strip().splitlines()[-10:]:
                d = json.loads(l)
                m = d.get("message", "")
                if len(m) > 256: d["message"] = m[:120] + f"...[{len(m)} chars masked]"
                print(json.dumps(d))
        else:
            print("no decisions yet")
    elif cmd == "discover":
        from tierllama.discover import discover
        import time as T
        t0 = T.time()
        hosts = discover()
        print(f"LAN scan: {T.time()-t0:.1f}s, {len(hosts)} hosts")
        for h in hosts:
            print(f"  {h['host']}:{h['port']} [{h['kind']}] models={h['models'][:6]}")
    elif cmd == "serve":
        import uvicorn
        uvicorn.run("tierllama.webapp:app", host="127.0.0.1", port=8848)
    elif cmd == "doctor":
        import doctor
        doctor.main()
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
