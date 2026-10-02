**Review: Tierllama Router (discover.py, rater.py)**

**HIGH** | `rater.py:rate_all` | SyntaxError: unterminated string literal in `b.get("max_fit") if b e` | Complete the conditional expression and close the dictionary literal | The module fails to import, causing a 500 error on every request to the router.

**HIGH** | `rater.py:_ensure_prices` | Race condition: multiple background threads read-modify-write `PRICES_PATH` without locking | Use a file lock or atomic write (write to temp file, then rename) | Concurrent writes can corrupt `model_prices.json`, leading to `json.JSONDecodeError` on subsequent reads and 500 errors.

**HIGH** | `rater.py:_ensure_liveness` | Race condition: multiple background threads read-modify-write `LIVENESS_PATH` without locking | Use a file lock or atomic write | Concurrent writes can corrupt `model_liveness.json`, leading to `json.JSONDecodeError` and 500 errors.

**MED** | `rater.py:gather_pool` | Blocking HTTP call to `127.0.0.1:11434/api/tags` in the request path | Cache local tags or serve from disk if Ollama is down | If Ollama is slow or down, this blocks the request thread, causing hangs or timeouts for the user.

**MED** | `rater.py:_probe_live` | Silent exception handling: network errors are treated the same as 410 Gone | Distinguish `URLError`/`TimeoutError` from `HTTPError` and only cache `False` on 410 | Network flakes will incorrectly mark models as dead, removing them from recommendations until manual cache clear.

**MED** | `rater.py:_fetch_model_prices` | Fragile regex parsing of HTML | Use a proper HTML parser or API endpoint if available | Ollama website changes will break price fetching, leaving prices stale or missing.

**MED** | `rater.py:rate_all` | `tok_s` can be `None`, causing `max(tok_s or 1, 1)` to default to 1 | Handle `None` explicitly and skip timing estimation if no data | Models without bench data get artificially low speed estimates, potentially excluding them incorrectly.

**LOW** | `discover.py:_tags` | Silent exception handling in both Ollama and OpenAI-compat probes | Log exceptions for debugging | Hard to diagnose why a host is marked "unknown" if the API response is malformed.

**LOW** | `rater.py:_load_liveness` | Silent exception handling on file read | Log exceptions | Hard to diagnose why liveness cache is empty if file is corrupted.
