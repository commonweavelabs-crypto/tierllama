# Why we stopped writing rules and started writing examples

*A plain-language findings note from building Tierllama (J1: the router core). Technical
version: comfyui-video-ui repo, docs/SPECS/jevllama-j1-findings.md.*

## What J1 was

The first milestone of our router: a tiny local model reads each incoming message and
decides what kind of request it is (planning? writing? a how-to question? a bug? a UI
command?) and how urgent it is. That decision sends the message to the right lane —
the free local model, a cheap cloud model, the expensive flagship, or the overnight
batch queue. The whole thing runs in under half a second per message.

## The surprise: rules don't work. Examples do.

We spent five prompt versions trying to teach the 4B model the difference between roles
by writing better rules.

- Version 1: simple role definitions. 86.7% accuracy.
- Version 2: added a rule for vague commands ("vague → director"). Accuracy went DOWN
  to 82.5% — the new rule made the model think creative requests were "vague commands."
- Version 3: more careful rules. 85%. We fixed one confusion and created another.

Every time we added a rule, the model traded an old mistake for a new one. Rules fight
each other; the model can't hold ten subtle distinctions in one glance.

Then we tried something different: instead of describing the categories harder, we
showed thirteen worked examples — actual messages with the right answer next to them.
Same rules, plus examples. Accuracy jumped to 95%, then 100% on the live acceptance run.

That's the difference between telling someone how to do a job and showing them three
times. Small models learn from examples the way people do — and examples cost 13 lines
of prompt instead of a fine-tune.

## The second finding: some mistakes are cheap — and that's by design

The model's weakest spot is judging difficulty: it likes to say "medium" for everything.
But look at what that mistake costs: instead of routing a tiny task to the free local
model, it routes to the cheap cloud model. Cost of the mistake: about fifteen cents per
million tokens instead of zero. The expensive mistakes — routing something HARD to the
cheap lane — are much rarer. A router doesn't need to be perfect everywhere. It needs to
be perfect where mistakes cost money.

## The third finding: the failures are the features

The messages the classifier still gets wrong are ambiguous ones — "review my project
and fix what's wrong." Ask a human project manager: is that a bug report or a planning
request? They'd hesitate too. Our system doesn't ask the classifier to resolve that
ambiguity; it flags it and hands it to a bigger model. The failures told us the
architecture was right before we ran the full test suite.

## Takeaways for anyone building with small local models

- Prompt rules plateau fast (86.7% → 82.5% → 85% in three versions of "better rules").
- Few-shot examples are the lever: 13 examples beat every amount of rule-writing.
- Measure every prompt version against the same test set; keep the winner, kill the rest.
- Accept cheap mistakes on cheap lanes; concentrate accuracy where misroutes cost money.
- Bigger ≠ better: an 8B model did worse than the 4B with the same prompt (see bench).

*Final J1 numbers: 100% role accuracy on the live acceptance set, 0.46s average per
message, decision log with full confidence data — on free local hardware. Open build
log; repos are public.*
