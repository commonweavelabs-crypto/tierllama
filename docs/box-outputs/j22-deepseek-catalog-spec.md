# J22: deepseek-v4.1-flash catalog entry + liveness re-validation policy

## 1. Failure-Mode Recap

The Tierllama routing engine relies on a static, hardcoded cloud catalog to populate the candidate pool for Brain 2. This design assumes that model availability is stable and that the local Ollama instance accurately reflects the state of the remote cloud registry. Both assumptions are false.

**The 410 Incident**
In the previous release cycle, the model `deepseek-v4-flash:cloud` was included in the seed table. At deployment time, the model was active. However, the upstream provider retired the model, returning HTTP 410 Gone for all inference requests. Because the catalog was static and lacked a liveness check, Tierllama continued to present `deepseek-v4-flash:cloud` as a valid routing option. Users attempting to use this model received hard failures. This incident demonstrated that hardcoded catalogs rot; they do not self-heal.

**The Tags-Lag Problem**
Ollamaâ€™s local API (`/api/tags`) does not list cloud models until they have been used at least once on that specific node. This creates a visibility gap:
1. A model is live on the cloud.
2. The local Ollama instance has not yet pulled or executed a request for that model.
3. `/api/tags` does not return the model.
4. Tierllamaâ€™s local discovery mechanism fails to see the model.
5. Brain 2 cannot rate or suggest the model.

Consequently, even if a model is live, it may be invisible to the router until a user manually triggers a first-use request. This breaks the "local-first" promise of automatic discovery.

**Conclusion**
We must decouple catalog presence from local visibility. We must introduce a proactive liveness validation layer that queries the upstream registry directly, independent of local Ollama state.

## 2. Catalog Entry Schema

Each model in the cloud catalog must conform to the following schema. This schema is stored in the `cloud_catalog.json` file and is the single source of truth for Brain 2â€™s initial candidate pool.

| Field | Type | Description |
| :--- | :--- | :--- |
| `model` | string | Unique identifier (e.g., `deepseek-v4.1-flash:cloud`). |
| `family` | string | Model family (e.g., `deepseek`). Used for grouping in UI. |
| `live_status` | enum | `LIVE`, `DEAD`, `UNKNOWN`. Initial state is `UNKNOWN`. |
| `price_in_mtok` | float | Input price per million tokens (USD). |
| `price_out_mtok` | float | Output price per million tokens (USD). |
| `context_length` | int | Maximum context window size. `null` if unknown. |
| `capability_estimate` | enum | `LOW`, `MEDIUM`, `HIGH`, `UNKNOWN`. Initial state is `UNKNOWN`. |
| `last_verified_at` | ISO8601 | Timestamp of the last successful liveness probe. |
| `source_url` | string | URL to the upstream registry page or API endpoint. |
| `evidence` | object | Structured log of the last probe result (status code, latency, error message). |

**Note on `live_status`:**
- `LIVE`: Model responded successfully to a probe within the TTL.
- `DEAD`: Model returned 404 or 410, or failed to respond.
- `UNKNOWN`: Model has not been probed yet, or the probe is pending.

## 3. Liveness Procedure

To prevent the 410 incident and the tags-lag issue, every model in the catalog must pass a liveness check before it can be included in Brain 2â€™s suggestion pool.

### 3.1 Probe Mechanism

The liveness check consists of two steps:

1. **Registry Page Check:**
   - Perform an HTTP `GET` request to the `source_url`.
   - Verify that the response status is `200 OK`.
   - Parse the response to confirm the model name is present in the registry listing.
   - *Purpose:* Confirms the model is still offered by the provider.

2. **1-Token Completion Probe:**
   - Perform a minimal inference request to the model endpoint.
   - Prompt: `"Hello"`
   - Max Tokens: `1`
   - Temperature: `0`
   - *Purpose:* Confirms the model is actually executable and not just listed. This catches cases where a model is listed but broken or rate-limited.

### 3.2 Live Cache and TTL

- **Cache Key:** `model` name.
- **TTL (Time-To-Live):** 24 hours.
- **Behavior:**
  - If `last_verified_at` is within 24 hours and `live_status` is `LIVE`, the model is considered live without a new probe.
  - If `last_verified_at` is older than 24 hours, or `live_status` is `UNKNOWN`, a new probe is triggered.
  - Probes are executed asynchronously in the background to avoid blocking the UI.

### 3.3 Failure Handling

- **HTTP 404 (Not Found):**
  - Set `live_status` to `DEAD`.
  - Add model to the `blacklist`.
  - Log error: `Model not found in registry.`

- **HTTP 410 (Gone):**
  - Set `live_status` to `DEAD`.
  - Add model to the `blacklist`.
  - Log error: `Model retired by provider.`

- **Timeout / 5xx Errors:**
  - Set `live_status` to `UNKNOWN`.
  - Do not add to blacklist immediately.
  - Retry probe after 5 minutes.
  - If 3 consecutive failures occur, set `live_status` to `DEAD` and add to blacklist.

### 3.4 Blacklist Policy

- **Persistence:** The blacklist is stored in `blacklist.json` and persists across restarts.
- **Re-Addition:** A blacklisted model **cannot** be automatically re-added to the catalog.
- **Human Confirmation Required:** To re-add a blacklisted model, an operator must manually edit the `cloud_catalog.json` file and set `live_status` to `UNKNOWN`. The system will then re-run the liveness probe. If the probe passes, the model is removed from the blacklist.
- **Rationale:** Prevents "zombie" models from re-entering the pool due to transient network errors or provider API glitches.

## 4. deepseek-v4.1-flash Known Facts

The following data is known for `deepseek-v4.1-flash:cloud` as of September 30.

### 4.1 Verified Facts

| Field | Value | Source |
| :--- | :--- | :--- |
| `model` | `deepseek-v4.1-flash:cloud` | Ollama Cloud Registry |
| `family` | `deepseek` | Naming convention |
| `live_status` | `LIVE` | Probe successful on Sep 30 |
| `price_in_mtok` | `0.30` | Provider pricing page |
| `price_out_mtok` | `1.20` | Provider pricing page (off-peak half-price applied) |
| `last_verified_at` | `2023-09-30T12:00:00Z` | Probe log |
| `source_url` | `https://ollama.com/library/deepseek-v4.1-flash` | Registry |

### 4.2 Assumed/Unknown Facts

| Field | Value | Status | Action Required |
| :--- | :--- | :--- | :--- |
| `context_length` | `UNKNOWN` | **MUST SCRAPE** | Scrape provider documentation or API response headers for `max_tokens`. |
| `capability_estimate` | `UNKNOWN` | **MUST BENCH** | Run a standardized benchmark suite (e.g., MMLU subset) on first use to estimate capability tier. |

**Note on Pricing:**
The price of $0.30/Mtok in and $1.20/Mtok out is based on off-peak pricing. Peak pricing may be higher. The catalog should store the off-peak price as the default, but the UI should display a warning if the current time is within peak hours.

**Note on Context Length:**
The context length is not explicitly stated in the registry. It must be determined by:
1. Checking the `max_tokens` field in the API response.
2. If not present, attempting a completion with a large context and observing the error message.
3. If still unknown, default to `4096` with a warning.

**Note on Capability:**
The capability estimate is unknown. It must be determined by:
1. Running a standard benchmark (e.g., 100 questions from MMLU).
2. Calculating the accuracy score.
3. Mapping the score to a tier:
   - `< 50%`: `LOW`
   - `50-70%`: `MEDIUM`
   - `> 70%`: `HIGH`

## 5. Acceptance Tests

The following tests must pass before this spec is considered implemented.

### Test 1: Live Model Appears in Rated Pool

**Setup:**
- Add `deepseek-v4.1-flash:cloud` to `cloud_catalog.json` with `live_status: UNKNOWN`.
- Ensure the model is live on the cloud.

**Action:**
- Start Tierllama.
- Wait for the liveness probe to complete.

**Expected Result:**
- `live_status` updates to `LIVE`.
- `last_verified_at` is updated to the current time.
- Brain 2 includes `deepseek-v4.1-flash:cloud` in the candidate pool.
- The model is visible in the UI as a selectable option.

### Test 2: Dead Model Excluded from Suggestion Pool

**Setup:**
- Add a fake model `fake-model:cloud` to `cloud_catalog.json` with `live_status: UNKNOWN`.
- Configure the probe to return HTTP 410.

**Action:**
- Start Tierllama.
- Wait for the liveness probe to complete.

**Expected Result:**
- `live_status` updates to `DEAD`.
- The model is added to `blacklist.json`.
- Brain 2 **does not** include `fake-model:cloud` in the candidate pool.
- A warning is displayed in the UI: `Model fake-model:cloud is dead (HTTP 410).`

### Test 3: Blacklist Survives Restarts

**Setup:**
- Ensure `fake-model:cloud` is in the blacklist.
- Stop Tierllama.
- Restart Tierllama.

**Expected Result:**
- `fake-model:cloud` remains in the blacklist.
- Brain 2 does not include `fake-model:cloud` in the candidate pool.
- No new probe is triggered for `fake-model:cloud` (unless manually re-added).

### Test 4: Tags-Lag Independence

**Setup:**
- Ensure `deepseek-v4.1-flash:cloud` is live on the cloud.
- Ensure the local Ollama instance has **not** used this model yet (i.e., it is not in `/api/tags`).

**Action:**
- Start Tierllama.
- Wait for the liveness probe to complete.

**Expected Result:**
- The liveness probe succeeds (registry check + 1-token completion).
- `deepseek-v4.1-flash:cloud` appears in Brain 2â€™s candidate pool.
- The model is visible in the UI, even though it is not in the local `/api/tags` list.

### Test 5: TTL Expiry Triggers Re-Probe

**Setup:**
- Ensure `deepseek-v4.1-flash:cloud` is `LIVE` with `last_verified_at` set to 25 hours ago.

**Action:**
- Start Tierllama.

**Expected Result:**
- A new liveness probe is triggered.
- If the model is still live, `last_verified_at` is updated.
- If the model is dead, `live_status` is updated to `DEAD` and the model is blacklisted.

## 6. Implementation Notes

1. **Asynchronous Probes:** Liveness probes must be executed in a background thread to avoid blocking the main UI thread.
2. **Error Logging:** All probe failures must be logged with the model name, status code, and timestamp.
3. **UI Warning:** When a model is dead, the UI must display a clear warning. The model should be grayed out or hidden, depending on user preference settings.
4. **Manual Override:** Operators must have a way to manually override the blacklist for debugging purposes. This should be logged and require a confirmation dialog.

## 7. Rollout Plan

1. **Phase 1:** Implement the liveness probe mechanism and update the catalog schema.
2. **Phase 2:** Migrate existing catalog entries to the new schema. Set `live_status` to `UNKNOWN` for all models.
3. **Phase 3:** Run liveness probes for all models. Update `live_status` based on results.
4. **Phase 4:** Enable the blacklist policy.
5. **Phase 5:** Deploy to production.

## 8. Risks

- **False Negatives:** A transient network error may cause a live model to be marked as `DEAD`. Mitigation: Retry logic and human confirmation for re-addition.
- **Performance:** Probing many models simultaneously may cause rate limiting. Mitigation: Stagger probes and limit concurrency.
- **Stale Data:** If the provider changes pricing or context length, the catalog may become outdated. Mitigation: Regularly re-scrape pricing and context length (separate from liveness probes).

## 9. Conclusion

This spec addresses the critical failure modes of hardcoded catalogs and local visibility gaps. By introducing a proactive liveness validation layer, we ensure that only live models are presented to users. The blacklist policy prevents zombie models from re-entering the pool, and the asynchronous probe mechanism ensures that the UI remains responsive. This approach aligns with the local-first philosophy by making the router robust against upstream changes.
