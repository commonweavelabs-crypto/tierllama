"""tierllama CLI: route | tail | discover | doctor"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "route"
    if cmd == "route":
        from tierllama.router import route
        msg = " ".join(sys.argv[2:]) or sys.stdin.read().strip()
        print(json.dumps(route(msg), indent=2))
    elif cmd == "tail":
        log = Path(__file__).parent / "logs" / "decisions.jsonl"
        if log.exists():
            for l in log.read_text().strip().splitlines()[-10:]:
                print(json.dumps(json.loads(l)))
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
    elif cmd == "doctor":
        import doctor
        doctor.main()
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
