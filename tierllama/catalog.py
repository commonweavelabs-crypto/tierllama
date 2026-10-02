"""Tierllama catalog oracle (J20): the full model universe, scraped from ollama.com.

WHY: local /api/tags shows ONLY models used on that machine; ollama.com/library
shows the entire public catalog (240+ families) and /cloud shows the cloud
sub-catalog. Brain 2 should suggest models the user never used — but only LIVE
ones (the deepseek-v4-flash:cloud 410 lesson: seed shipped a retired model).

Design (Gui laws encoded):
- Scrape-on-demand + disk cache, NO timers (no background refresh loops).
- Liveness gate: an entry reaches the rated pool only with live_status == 'live'.
- Sources logged (source_url + last_verified_at) — evidence, not vibes.
- Staged apply: catalog rows merge into rater's CLOUD_CATALOG candidates via
  apply_to_rater(); _user_edited tiers stay sacred (J10).
- Privacy: catalog data is public-web metadata only; nothing user-derived.

Pages used (verified Oct 1):
- /library          listing (240+/page, 'Next' paginates; tags: tev1:0.8b etc.)
- /cloud            cloud sub-catalog (16 families at launch, incl. deepseek-v4.1-flash)
- /library/<model>  detail: 'Context N tokens', 'Size N parameter', prices
                    ($X input ... $Y output per Mtok — same regex as rater.py)
"""
import json, re, html, datetime, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
CATALOG_PATH = ROOT / "logs" / "model_catalog.json"
CATALOG_STALE_S = 7 * 24 * 3600.0        # re-scrape after 7d (on demand, not timed)
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

LOCAL_ONLY_MARKERS = ("embed", "bge-", "nomic")   # skip embedding-only families in routing pool


def _fetch(url: str, timeout=30) -> str | None:
    try:
        req = urllib.request.Request(url, headers=_UA)
        return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _library_page(page: int = 1) -> list[str]:
    """Model family names from /library?page=N (dedup, ordered)."""
    h = _fetch(f"https://ollama.com/library?page={page}")
    if not h:
        return []
    out = []
    for n in re.findall(r'href="/library/([a-zA-Z0-9._-]+)"', h):
        if n not in out:
            out.append(n)
    return out


def _cloud_page() -> list[str]:
    """Cloud-catalog family names from /cloud (the J20 answer to tags-lag)."""
    h = _fetch("https://ollama.com/cloud")
    if not h:
        return []
    return sorted(set(re.findall(r'/library/([a-zA-Z0-9._-]+)', h)))


def _model_detail(name_base: str) -> dict:
    """Fields from a /library/<name> detail page. Prices via the same regex
    shape rater.py uses ('$X input ... $Y output'); ctx/params from the
    'Context N tokens / Size N parameter' block."""
    d = {"model": name_base, "source_url": f"https://ollama.com/library/{name_base}",
         "last_verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    h = _fetch(f"https://ollama.com/library/{name_base}")
    if h is None:
        d.update(live_status="unknown", note="detail page unreachable")
        return d
    if "page not found" in h.lower() or '"httpCode":404' in h:
        d.update(live_status="dead", note="404 on library page")
        return d
    d["live_status"] = "live"
    # markup: '<span ...>1M</span><span ...>tokens</span>' (value span precedes unit span)
    m = re.search(r'text-black">([0-9.]+)\s*([KMB]?)</span>\s*<span[^>]*>\s*tokens', h)
    if not m:
        m = re.search(r"Context\s+([0-9.]+)\s*([KMB])?\s*tokens", h)
    if m:
        mult = {"K": 1e3, "M": 1e6}.get(m.group(2) or "", 1)
        d["context_length"] = int(float(m.group(1)) * mult)
    # markup: pricing-rate divs -> '$X</div>...<div>input' / '$Y</div>...<div>output' / '$Z cached'
    pm = re.search(r"\$([0-9.]+)</div>\s*<div[^>]*>\s*input.{0,400}?\$([0-9.]+)</div>\s*<div[^>]*>\s*output", h, re.DOTALL)
    if pm:
        d.update(price_in_per_mtok=float(pm.group(1)), price_out_per_mtok=float(pm.group(2)))
    else:
        pi = re.search(r"\$([0-9.]+)</div>\s*<div[^>]*>\s*input", h, re.DOTALL)
        po = re.search(r"\$([0-9.]+)</div>\s*<div[^>]*>\s*output", h, re.DOTALL)
        if pi:
            d["price_in_per_mtok"] = float(pi.group(1))
        if po:
            d["price_out_per_mtok"] = float(po.group(1))
    pc = re.search(r"\$([0-9.]+)</div>\s*<div[^>]*>\s*cached", h)
    if pc:
        d["price_cached_per_mtok"] = float(pc.group(1))
    # params: '<span ...>763B</span><span ...>parameter'
    s = re.search(r'text-black">([0-9.]+)\s*([KMB])\s*</span>\s*<span[^>]*>\s*parameter', h)
    if not s:
        s = re.search(r"Size\s+([0-9.]+)\s*([KMB])\s*parameter", h)
    if s:
        mult = {"K": 1e3, "M": 1e6, "B": 1e9}.get(s.group(2), 1)
        d["param_count"] = int(float(s.group(1)) * mult)
    return d


def _load() -> dict:
    if CATALOG_PATH.exists():
        try:
            return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"models": {}, "generated": None}


def _save(cat: dict):
    CATALOG_PATH.parent.mkdir(exist_ok=True)
    CATALOG_PATH.write_text(json.dumps(cat, indent=1, ensure_ascii=False), encoding="utf-8")


def scrape_library(max_pages: int = 2, include_detail: bool = True, only_new: bool = True):
    """Full public catalog. Detail pages are the slow part (~1 req per family);
    only_new=True skips families already in cache with a fresh detail block."""
    cat = _load()
    now = datetime.datetime.now(datetime.timezone.utc)
    names: list[str] = []
    for pg in range(1, max_pages + 1):
        page_names = _library_page(pg)
        if not page_names:
            break
        names.extend(page_names)
        if len(set(page_names)) < 10:   # last page repeats/ends
            break
    fresh = 0
    for n in names:
        entry = cat["models"].get(n)
        needs = (entry is None or (include_detail and "context_length" not in entry))
        if entry and only_new and not needs:
            continue
        if include_detail:
            cat["models"][n] = {**(entry or {}), **_model_detail(n)}
        else:
            cat["models"].setdefault(n, {"model": n, "source_url": f"https://ollama.com/library/{n}",
                                         "live_status": "unknown"})
        fresh += 1
    cat["generated"] = now.isoformat(timespec="seconds")
    _save(cat)
    return {"families_seen": len(set(names)), "detail_fetched": fresh, "total": len(cat["models"])}


def scrape_cloud(include_detail: bool = True):
    """The cloud sub-catalog (all usable with an Ollama account regardless of
    local tags — the J20 answer to tags-lag)."""
    cat = _load()
    cloud = _cloud_page()
    fresh = 0
    for n in cloud:
        entry = cat["models"].get(n) or {}
        if include_detail and entry.get("live_status") in (None, "unknown", "dead"):
            d = _model_detail(n)
            # cloud models may 404 their /library page while alive server-side;
            # a 404 on a /cloud-listed family = live (account-level) not dead
            if d.get("live_status") == "dead" and entry.get("cloud"):
                d["live_status"] = "live"
                d["note"] = "listed on /cloud; detail page 404 (tags-lag class)"
            cat["models"][n] = {**entry, **d, "cloud": True}
            fresh += 1
        else:
            cat["models"].setdefault(n, {"model": n, "cloud": True, "live_status": "unknown"})
            cat["models"][n]["cloud"] = True
    cat["generated"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    _save(cat)
    return {"cloud_families": len(cloud), "detail_fetched": fresh, "total": len(cat["models"])}


def catalog_rows(include_dead: bool = False) -> list[dict]:
    """Routing-pool rows: LIVE entries only (liveness gate), embedding families
    excluded unless asked."""
    cat = _load()
    rows = []
    for n, e in cat["models"].items():
        if not include_dead and e.get("live_status") not in ("live",):
            continue
        if not include_dead and any(m in n.lower() for m in LOCAL_ONLY_MARKERS):
            continue
        rows.append(e)
    return rows


def apply_to_rater(rows: list[dict] | None = None, dry_run: bool = False) -> dict:
    """Staged apply: live catalog cloud families become rater pool candidates.
    NEVER touches _user_edited tiers or the local model entries — this only
    extends gather_pool()'s cloud candidates via the J20 catalog file."""
    import sys
    from pathlib import Path as _P
    sys.path.insert(0, str(_P(__file__).parent.parent))
    from tierllama.rater import CLOUD_CATALOG, gather_pool  # noqa
    if rows is None:
        rows = catalog_rows()
    cloud_live = sorted({r["model"] for r in rows if r.get("cloud") and r.get("live_status") == "live"})
    known = set(CLOUD_CATALOG)
    new = [m for m in cloud_live if m.split(":")[0] not in {k.split(":")[0] for k in known}]
    if dry_run:
        return {"would_add": new, "already_known": len(known), "cloud_live_total": len(cloud_live)}
    # extend the in-memory catalog AND persist the extension marker (J20 staged apply)
    staged = {"added": new, "applied_at": datetime.datetime.now().isoformat(timespec="seconds"),
              "source": "catalog-oracle"}
    STAGED = ROOT / "logs" / "catalog_applied.json"
    prev = json.loads(STAGED.read_text(encoding="utf-8")) if STAGED.exists() else {"added": []}
    merged = sorted(set(prev.get("added", [])) | set(new))
    STAGED.write_text(json.dumps({"added": merged, "applied_at": staged["applied_at"]}, indent=1), encoding="utf-8")
    prev["added"] = merged
    CATALOG_PATH.parent.mkdir(exist_ok=True)
    return {"added": new, "total_catalog_now": len(merged), "known_before": len(known)}


def validate_liveness(names: list[str] | None = None) -> dict:
    """Re-verify live_status for specific models (or all cloud entries) by
    probing the library page. Deepseek-v4-flash-class rot guard."""
    cat = _load()
    targets = names or [n for n, e in cat["models"].items() if e.get("cloud")]
    changed = {}
    for n in targets:
        e = cat["models"].get(n)
        if not e:
            continue
        h = _fetch(f"https://ollama.com/library/{n.split(':')[0]}")
        new_status = "live" if h and "page not found" not in h.lower() else "dead"
        if new_status != e.get("live_status"):
            changed[n] = (e.get("live_status"), new_status)
            e["live_status"] = new_status
            e["last_verified_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    if changed:
        _save(cat)
    return {"checked": len(targets), "changed": changed}


if __name__ == "__main__":
    print("scrape cloud:", scrape_cloud())
    print("rows live:", len(catalog_rows()))
    print("staged apply (dry):", apply_to_rater(dry_run=True))