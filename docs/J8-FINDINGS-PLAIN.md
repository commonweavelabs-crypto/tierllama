# J8 in plain language: the button that tunes itself

You should never have to think about which model handles which job. That's the
machine's job. J8 gives Tierllama its "Optimize" button.

## What happens when you press it

Tierllama tests every local model on your actual hardware. Each model gets one
combined sweep: first we measure how long it takes to load from cold (the model
completely out of memory), then we ask it an easy question, a medium one, and a
hard one - timing every answer and grading whether it's right. From that:

- **Speed** decides whether a model can serve NOW tasks (real-time) or is
  LATER-only (queued jobs)
- **Capability** decides the hardest tier it can handle: EASY, MEDIUM, or HARD

Then the decision tree fills itself in, and every entry is tagged with where it
came from: **measured** (tested on your machine) or **seed** (our general
knowledge, used only until real measurements exist). Measured always wins.

## What we learned building it

- **Grading is harder than timing.** Asking "is this code correct?" made us
  actually execute the model's code in a sandbox - and it caught a real bug in
  qwen3:8b's palindrome (its case-insensitivity was broken). Timing lies less
  than vibes.
- **qwen3:4b thinks forever.** Its reasoning doesn't stop within token budgets,
  so we learned to look for code in BOTH the answer and the thinking channel.
- **The 35B model takes 163 seconds to cold-load** - measured, not guessed.
  That number is why it will never serve a real-time task.
- **Single-shot grading is noisy.** One flaky probe now retries once before
  concluding a model failed.

## Consent, in plain words

Results stay on your machine by default - a checkbox confirms it before the
first scan. Sharing anonymous performance data (model names, hardware class,
speeds - never your prompts or messages) is a separate box you choose to tick,
you can untick any time, and the dashboard shows what was shared.
