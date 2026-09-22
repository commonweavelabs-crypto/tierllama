# J7 in plain language: the dashboard where you decide

Tierllama now has a face. One command - `tierllama serve` - and your browser
becomes the control room: your machines, your models, your decision tree.

## What you can do now

**See your fleet.** Every machine on your network running Ollama shows up with
its models - discovered automatically, no accounts, no setup.

**Edit the decision tree.** Four tiers (EASY, MEDIUM, HARD, EXPERT) times two
timings (NOW, LATER) = eight dropdowns. Each one maps to a model AND a thinking
level. Don't want the cloud model for hard jobs? Pick your local 8B. Want the
same model to think harder for expert work? Set thinking to max.

**Changes apply instantly.** No restart. The router re-reads your tree on every
single message. We proved it live: changed the HARD tier to the local 8B model
from the browser, and the next message was served by that model in 14 seconds.

**See your savings.** The dashboard compares what you spent against the
always-use-the-best-model baseline, from your real decision log.

## The interesting bug we hit

Our first test failed in a sneaky way: we changed the HARD tier's model, but the
message still went to the old one. The routing wasn't broken - the message had
been classified HARD/**LATER** (a "queue it" task), and we had only changed
HARD/**NOW**. The decision tree maps difficulty AND timing, because the same
difficulty can go to different places depending on when you need the answer.
A good reminder that a router is only as correct as your mental model of it.

## Why no Electron?

The dashboard is one Python process serving both the API and a clean dark UI.
`tierllama serve` and you're done - nothing else to install, no node, no build
step. The app ships with the router; the router is the app.
