# Jev: the original, our implementation, and the naming story

## The original: Jev by TypeSafe AI
- **Creator:** Diogo Almeida — ex-OpenAI researcher, co-creator of RLHF
  (the training method behind ChatGPT) and InstructGPT
- **Company:** TypeSafe AI (San Francisco, founded 2024)
- **Release:** Sept 15, 2026, $40M seed (led by DCVC)
- **What it is:** a "System One" model — it CANNOT generate text. It returns
  typed decisions: a `choice`, a `score`, or a `noul` (probability) — each with
  **calibrated confidence**, in 70–500ms. Zero hallucinations by construction.
- **Pricing:** $0.042/Mtok input, **output tokens free** ≈ $0.00002/decision
- **API:** `POST https://api.typesafe.ai/v1/systemone`, Bearer `TYPESAFE_API_KEY`,
  model `jev-latest` (early access — keys rolling out in waves)

## Our implementation: a Jev-style brain, open source
Tierllama's router brain is our own open-source implementation of the same
idea: a tiny model returning **typed routing decisions** (role / difficulty /
timing + confidence) instead of generating prose.
- **Model:** qwen3:4b (Alibaba's Qwen 3 family, via the Ollama registry)
- **Method:** assistant-prefill + logprob read = a TRUE probability
  distribution over roles — measured 94.2% @ ~80ms warm
- **Analogy:** like generic vs brand-name medication — same active principle,
  our formulation runs on YOUR hardware at $0/call
- **License note:** Qwen 3 is Apache-2.0. We credit both: TypeSafe for the
  System One concept our product is named after, the Qwen team for the weights.

## Naming timeline
1. "Jev" was chosen as our classifier persona during the J1 milestone
   (routing rubric voice) — before we connected it to the real Jev model
2. 9/22: Gui connected the dots — the real Jev (TypeSafe) matches what we
   built. The name turned out prescient, not derivative.
3. Decision: keep the name, credit both lineages (this file), and ship the
   REAL Jev Cloud as the official cloud fallback for users without hardware.

## Relationship to the real Jev
- Jev Cloud = one provider in our grid (featured card) + classifier fallback
- We are a consumer of their API, and an open-source complement: they route
  decisions in THEIR cloud; we route them on YOUR hardware
