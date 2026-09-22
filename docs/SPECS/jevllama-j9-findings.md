# J9 findings - installers + PWA app-shell

## Verified (live)
1. PWA: manifest.json + sw.js + generated llama icons (192/512) served at :8848
   - all endpoints 200 on fresh clone; manifest fields complete (Chrome
     installability: name/short_name/start_url/icons/display=standalone)
2. install.bat: 5-step zero-to-working (Python check, pip deps, Ollama
   detection w/ plain-language fallback, auto-start setup, service start + open)
3. update.bat: git pull + kill/restart both services
4. Fresh-machine simulation: clean clone on :8850/:8851 - dashboard, manifest,
   sw, icon, fleet-api, proxy /v1/models ALL 200; live chat "2+3?" -> "2 + 3 = 5."
   routed; /api/optimize/status live; doctor 7/7 PASS (OVERALL: HEALTHY)

## Design notes
- Path-independent .bat scripts (%~dp0) - works from any clone location
- SW never caches /api/* (fleet/config always fresh); shell-only offline
- Icons generated programmatically (Pillow llama glyph) - no binary assets in git
- Known limitation: PWA requires the local dashboard server running (auto-start
  covers it); a service worker update flow = version-bump cache name (future)

## Not done / deferred
- Bundled-Python runtime installer (needs product decision per stop-when -
  default: system Python + clear error, revisited if user feedback demands)
- macOS/Linux installers (Windows-first per Gui's machine)


## Consolidated final verification (goal contract, fresh clone 9/22)
| # | Condition | Result |
|---|-----------|--------|
| 1 | Python deps install | OK (pip exit 0) |
| 2 | Ollama detection | OK (7 models; clear message path in install.bat) |
| 3 | Proxy+dashboard from clone | both serve on :8852/:8853 |
| 4 | PWA installability | manifest complete, sw 200, icon 200, standalone |
| 5 | route | live chat answered via clone's proxy |
| 6 | discover | 4 peers found |
| 7 | optimize status | endpoint live |
| 8 | doctor | 7/7 PASS, OVERALL: HEALTHY |

No stop-conditions hit. Bundled-Python runtime deferred by documented default
(system Python + clear errors) - flagged for product revisit only if user
feedback demands.
