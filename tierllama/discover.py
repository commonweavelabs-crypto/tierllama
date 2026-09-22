"""Tierllama Tier-0 discovery (J5): find every Ollama/llama-swap host on the LAN.
No accounts, no setup - any Ollama (port 11434) or llama-swap (port 8080) on the
subnet becomes an available lane. Measured: /24 scan in ~6s with 64 threads."""
import json, urllib.request, socket, concurrent.futures, ipaddress, time

def _probe(ip, port, timeout=1.2):
    s = socket.socket(); s.settimeout(timeout)
    try:
        s.connect((ip, port)); return (ip, port)
    except Exception:
        return None
    finally:
        s.close()

def _tags(ip, port, timeout=4):
    try:
        req = urllib.request.Request(f"http://{ip}:{port}/api/tags", headers={"User-Agent":"Tierllama"})
        d = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        return {"host": ip, "port": port, "kind": "ollama",
                "models": [m["name"] for m in d.get("models", [])]}
    except Exception:
        pass
    try:
        req = urllib.request.Request(f"http://{ip}:{port}/v1/models", headers={"User-Agent":"Tierllama"})
        d = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        models = [m["id"] for m in d.get("data", [])]
        kind = "llama-swap" if any(m.get("owned_by")=="llama-swap" for m in d.get("data", [])) else "openai-compat"
        return {"host": ip, "port": port, "kind": kind, "models": models}
    except Exception:
        return {"host": ip, "port": port, "kind": "unknown", "models": []}

def discover(subnet=None, ports=(11434, 8080), workers=64, timeout=1.2):
    """Scan the local subnet for Ollama/llama-swap/openai-compat hosts. Returns
    list of {host, port, kind, models}."""
    if subnet is None:
        # derive from this machine's IP (best-effort, IPv4 only):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80)); myip = s.getsockname()[0]
        except Exception:
            myip = "192.168.1.1"
        finally:
            s.close()
        subnet = ".".join(myip.split(".")[:3]) + ".0/24"
    net = ipaddress.ip_network(subnet, strict=False)
    hosts = [str(h) for h in net.hosts()]
    candidates = [(h, p) for h in hosts for p in ports]
    found = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_probe, h, p, timeout): (h, p) for h, p in candidates}
        for f in concurrent.futures.as_completed(futs):
            r = f.result()
            if r:
                found.append(r)
    # enrich open ports with model lists (few hosts; sequential fine):
    out = [_tags(ip, port) for (ip, port) in sorted(found)]
    return out
