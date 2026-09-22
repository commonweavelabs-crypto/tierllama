# The model that's always sure of itself

*A plain-language findings note from building Tierllama. Technical version: see the
comfyui-video-ui repo, `docs/SPECS/jevllama-j2-findings.md`.*

## The setup

We're building a router: a tiny, fast model reads every incoming message and decides
which AI model should handle it — the free local one, a cheap cloud one, or the expensive
flagship. Every message it routes correctly is money saved; every misroute is money
wasted. For this to work, the router has to know what it doesn't know.

## What we tested

We built a test set of 120 real user messages and asked a small (4-billion-parameter)
local model to route each one, and to say how confident it was. Two questions:

1. Is it right? (accuracy)
2. When it says "I'm 95% sure," is it actually right 95% of the time? (calibration)

## What we found

**It's right 94% of the time.** For a 4B model running free on a gaming GPU, that's
excellent. The router works.

**But its confidence is fake.** Every single message — all 120 — came back with the
same answer to "how sure are you?": 95% or higher. Right answers: 95% sure. Wrong
answers: 95% sure. Ambiguous questions even a human would hesitate on: 95% sure.
The model isn't lying on purpose; that's just how chat models are built. Asking a chat
model "how confident are you?" is like asking it to grade its own homework.

## The turn

Here's the good news, and it's the important part. Language models don't just produce
words — underneath, every possible next word has a probability. We found we can read
those raw probabilities directly: instead of asking the model "are you sure?" (useless),
we look at the actual math it used to pick its answer (very useful).

Concretely: we pre-write the start of its answer, force the next word to be the role
name, and read the probability distribution across all five roles in one pass. This is
the same trick the open-source Jev-classifier projects use, and it worked immediately:
accuracy went UP (91.7% → 94.2%), each decision costs ~80 milliseconds, and every
routing decision now comes with a real probability attached.

## The catch (and it's an interesting one)

Even the raw probabilities have a limit: when this model gets it wrong, it gets it wrong
confidently. The probability says 100% even on the mistakes. So no amount of threshold
tuning will catch the ambiguous cases. The fix isn't a better number — it's a better
architecture: when a message looks borderline, don't decide, escalate — send it to a
bigger model, or ask again with rephrasing and check for agreement. We knew this might
be true when we designed the system; now it's measured.

## Why this matters if you're building with small local models

- Never trust a chat model's self-reported confidence. It's decoration.
- Token logprobs are cheap, honest, and available in most local runtimes (Ollama
  included, via its OpenAI-compatible API). Use them.
- Even logprob confidence saturates on ambiguous inputs. Design a fallback path for the
  cases where "the model is sure" and "the model is right" come apart.
- Bigger ≠ better for routing: an 8B model scored WORSE than 4B with the same prompt,
  and adding worked examples (few-shot) beat every amount of rule-writing we tried.

*Measured numbers: 94.2% accuracy, ~80ms per decision, on free local hardware. Full
technical detail in the project repos. Part of an open build log — we publish our
findings as we build.*
