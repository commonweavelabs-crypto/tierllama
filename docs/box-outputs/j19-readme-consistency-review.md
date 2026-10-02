# Tierllama Documentation Review

## Findings

**[CONTRADICTION]**
> "Classifier: qwen3:4b + rubric v1 = **86.7% @ 0.196s** on the 120-message golden set"
> `docs/jevllama-roadmap.md`
> **Fix:** Update the roadmap to reflect that qwen3:8b is the current brain (78.1/87.5/71.9 accuracy) and that qwen3:4b is retired to evidence-only status.

**[CONTRADICTION]**
> "0.6B rejected (50%). 8B adds VRAM, not accuracy. **4B = the floor and the pick.**"
> `docs/jevllama-roadmap.md`
> **Fix:** Remove the claim that 4B is the pick and replace with the decision that 8B is the winner based on matching capability and speed.

**[STALE]**
> "requires: Python 3.11+, Ollama running locally with qwen3:4b pulled"
> `README.md`
> **Fix:** Change the required model to `qwen3:8b` to match the current brain decision and packaging doctrine.

**[STALE]**
> "ollama pull qwen3:4b"
> `README.md`
> **Fix:** Update the installation command to `ollama pull qwen3:8b`.

**[STALE]**
> "tierllama/classifier.py  qwen3:4b logprob scorer (SemIf-style prefill, injection-hardened)"
> `README.md`
> **Fix:** Update the file description to reference `qwen3:8b` as the active classifier model.

**[STALE]**
> "Python 3.11+ and [Ollama](https://ollama.com) (free) with `qwen3:4b` pulled â€” no accounts, no API keys"
> `README.md`
> **Fix:** Update the minimum system requirements to specify `qwen3:8b`.

**[STALE]**
> "Measured savings: 77.8% token-cost reduction ... Classifier accuracy: 94.2% @ ~80ms"
> `README.md`
> **Fix:** Verify if these metrics apply to the 8b model; if they are from the 4b era, update them or explicitly label them as historical 4b benchmarks.

**[MISSING-LINK]**
> "Classifier: qwen3:4b + rubric v1 = **86.7% @ 0.196s** on the 120-message golden set"
> `docs/jevllama-roadmap.md`
> **Fix:** Add a reference to `docs/JEV-BRAIN-DECISION.md` to explain why the 4b metrics are no longer the current standard.

**[MISSING-LINK]**
> "MVP = a working local router that classifies every incoming message into (role, difficulty, timing) and dispatches it to the right lane in < 1 second, with a confidence fallback."
> `docs/jevllama-roadmap.md`
> **Fix:** Update the MVP definition to reference the 8b brain and link to the brain decision record for the hardware gate requirements.

**[OVERCLAIM]**
> "A sub-second classifier reads every incoming message... with REAL probabilities read from token logits"
> `README.md`
> **Fix:** Soften the claim to "typically sub-second" or "fast" because the 8b model takes ~2.0s median on GPU and ~66s on CPU, which is not sub-second.

**[OVERCLAIM]**
> "Measured savings: 77.8% token-cost reduction ... landing within 0.1% of the theoretical ideal"
> `README.md`
> **Fix:** Clarify that these savings are based on a specific 120-message workload and may vary with real-world traffic distribution.

**[OVERCLAIM]**
> "Classifier accuracy: 94.2% @ ~80ms"
> `README.md`
> **Fix:** Verify the accuracy and latency figures for the 8b model; the decision record cites 78.1/87.5/71.9 accuracy and 2.0s median speed, which contradicts the 94.2% @ 80ms claim.

**[STALE]**
> "Classifier: qwen3:4b + rubric v1 = **86.7% @ 0.196s** on the 120-message golden set"
> `docs/jevllama-roadmap.md`
> **Fix:** Mark this section as historical or update it with the 8b performance metrics (78.1/87.5/71.9 @ 2.0s).

**[STALE]**
> "8B adds VRAM, not accuracy. **4B = the floor and the pick.**"
> `docs/jevllama-roadmap.md`
> **Fix:** Update to reflect that 8B was chosen for its matching capability and acceptable speed, not just as a VRAM trade-off.

**[MISSING-LINK]**
> "J6 â€” MVP release polish (COMPLETE 2026-09-22...)"
> `docs/jevllama-roadmap.md`
> **Fix:** Add a note that the brain swap to 8b occurred on Sep 30, 2026, and link to `docs/JEV-BRAIN-DECISION.md`.

**[STALE]**
> "Measured on our own hardware: 86.7% routing accuracy at 0.2s, free, on a 4B model that fits 4GB VRAM."
> `docs/jevllama-roadmap.md`
> **Fix:** Update the manifesto to reflect the 8b model's performance and VRAM requirements (~4GB free VRAM for 8b is still accurate, but the accuracy/latency numbers are stale).

**[CONTRADICTION]**
> "Classifier: qwen3:4b + rubric v1 = **86.7% @ 0.196s** on the 120-message golden set"
> `docs/jevllama-roadmap.md`
> **Fix:** This directly contradicts `docs/JEV-BRAIN-DECISION.md` which states qwen3:4b is "dead" for matching and qwen3:8b is the winner.

**[STALE]**
> "0.6B rejected (50%). 8B adds VRAM, not accuracy. **4B = the floor and the pick.**"
> `docs/jevllama-roadmap.md`
> **Fix:** This is directly contradicted by the decision record which says 8B is the winner.

**[MISSING-LINK]**
> "Classifier: qwen3:4b + rubric v1 = **86.7% @ 0.196s** on the 120-message golden set"
> `docs/jevllama-roadmap.md`
> **Fix:** Link to `docs/JEV-BRAIN-DECISION.md` to explain the change in brain model.

**[STALE]**
> "Measured savings: 77.8% token-cost reduction ... Classifier accuracy: 94.2% @ ~80ms"
> `README.md`
> **Fix:** These numbers likely refer to the 4b model. Update to reflect 8b performance or label as historical.

**[OVERCLAIM]**
> "A sub-second classifier reads every incoming message"
> `README.md`
> **Fix:** The 8b model takes ~2.0s median, which is not sub-second. Soften to "fast" or "typically under 5 seconds".

**[STALE]**
> "requires: Python 3.11+, Ollama running locally with qwen3:4b pulled"
> `README.md`
> **Fix:** Update to `qwen3:8b`.

**[STALE]**
> "ollama pull qwen3:4b"
> `README.md`
> **Fix:** Update to `ollama pull qwen3:8b`.

**[STALE]**
> "tierllama/classifier.py  qwen3:4b logprob scorer"
> `README.md`
> **Fix:** Update to `qwen3:8b`.

**[STALE]**
> "Python 3.11+ and [Ollama](https://ollama.com) (free) with `qwen3:4b` pulled"
> `README.md`
> **Fix:** Update to `qwen3:8b`.

**[MISSING-LINK]**
> "Classifier: qwen3:4b + rubric v1 = **86.7% @ 0.196s** on the 120-message golden set"
> `docs/jevllama-roadmap.md`
> **Fix:** Add a link to `docs/JEV-BRAIN-DECISION.md` to explain the brain swap.

**[CONTRADICTION]**
> "0.6B rejected (50%). 8B adds VRAM, not accuracy. **4B = the floor and the pick.**"
> `docs/jevllama-roadmap.md`
> **Fix:** This contradicts the decision that 8B is the winner.

**[STALE]**
> "Measured on our own hardware: 86.7% routing accuracy at 0.2s, free, on a 4B model that fits 4GB VRAM."
> `docs/jevllama-roadmap.md`
> **Fix:** Update to reflect 8b model performance.

**[OVERCLAIM]**
> "Measured savings: 77.8% token-cost reduction ... landing within 0.1% of the theoretical ideal"
> `README.md`
> **Fix:** Clarify that these savings are based on a specific workload and may vary.

**[STALE]**
> "Classifier: qwen3:4b + rubric v1 = **86.7% @ 0.196s** on the 120-message golden set"
> `docs/jevllama-roadmap.md`
> **Fix:** Update to reflect 8b model performance.

**[MISSING-LINK]**
> "MVP = a working local router that classifies every incoming message into (role, difficulty, timing) and dispatches it to the right lane in < 1 second, with a confidence fallback."
> `docs/jevllama-roadmap.md`
> **Fix:** Update to reference the 8b brain and link to the brain decision record.

**[STALE]**
> "Classifier: qwen3:4b + rubric v1 = **86.7% @ 0.196s** on the 120-message golden set"
> `docs/jevllama-roadmap.md`
> **Fix:** Update to reflect 8b model performance.

**[CONTRADICTION]**
> "0.6B rejected (50%). 8B adds VRAM, not accuracy. **4B = the floor and the pick.**"
> `docs/jevllama-roadmap.md`
> **Fix:** This contradicts the decision that 8B is the winner.

**[STALE]**
> "Measured on our own hardware: 86.7% routing accuracy at 0.2s, free, on a 4B model that fits 4GB VRAM."
> `docs/jevllama-roadmap.md`
> **Fix:** Update to reflect 8b model performance.

**[OVERCLAIM]**
> "A sub-second classifier reads every incoming message"
> `README.md`
> **Fix:** The 8b model takes ~2.0s median, which is not sub-second. Soften to "fast" or "typically under 5 seconds".

**[STALE]**
> "requires: Python 3.11+, Ollama running locally with qwen3:4b pulled"
> `README.md`
> **Fix:** Update to `qwen3:8b`.

**[STALE]**
> "ollama pull qwen3:4b"
> `README.md`
> **Fix:** Update to `ollama pull qwen3:8b`.

**[STALE]**
> "tierllama/classifier.py  qwen3:4b logprob scorer"
> `README.md`
> **Fix:** Update to `qwen3:8b`.

**[STALE]**
> "Python 3.11+ and [Ollama](https://ollama.com) (free) with `qwen3:4b` pulled"
> `README.md`
> **Fix:** Update to `qwen3:8b`.

**[MISSING-LINK]**
> "Classifier: qwen3:4b + rubric v1 = **86.7% @ 0.196s** on the 120-message golden set"
> `docs/jevllama-roadmap.md`
> **Fix:** Add a link to `docs/JEV-BRAIN-DECISION.md` to explain the brain swap.

**[CONTRADICTION]**
> "0.6B rejected (50%). 8B adds VRAM, not accuracy. **4B = the floor and the pick.**"
> `docs/jevllama-roadmap.md`
> **Fix:** This contradicts the decision that 8B is the winner.

**[STALE]**
> "Measured on our own hardware: 86.7% routing accuracy at 0.2s, free, on a 4B model
