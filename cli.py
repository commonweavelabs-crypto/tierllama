"""tierllama CLI (MVP): python cli.py route "message" | bench | tail"""
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tierllama.router import route

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "route"
    if cmd == "route":
        msg = " ".join(sys.argv[2:]) or sys.stdin.read().strip()
        r = route(msg)
        print(json.dumps(r, indent=2))
    elif cmd == "tail":
        log = Path(__file__).parent / "logs" / "decisions.jsonl"
        lines = log.read_text().strip().splitlines()[-10:]
        for l in lines: print(json.dumps(json.loads(l), indent=None))
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
