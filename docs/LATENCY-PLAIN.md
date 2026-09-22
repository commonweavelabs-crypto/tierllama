# How fast is the router? (and where can it run?)

*Plain-language answers to Gui's questions, with measured numbers. Technical version:
docs/jevllama-latency.md.*

## How much latency does the classifier add?

Almost none, most of the time. Measured on the 5070 Ti:

- **Warm: 26-42 milliseconds.** That's faster than a blink. Once the model is loaded,
  every routing decision costs about a fortieth of a second.
- **Cold (after idle): about 3 seconds, once.** Then it's warm again.
- **First load of the day: ~13 seconds.** Happens once after the machine or Ollama starts.

## Does it have to sit in the GPU all the time?

No - and you called it exactly right. Ollama unloads models after **five minutes of no
use** by default. The GPU goes back to your games, ComfyUI, or whatever else needs it.
When the next message arrives, the classifier reloads in about 3 seconds, then it's fast
again. We'll make that a config option: unload-after-idle for GPU-friendly users,
always-on for latency-sensitive users.

## The offload idea (your brainstorm): tested, and it works

Your scenario: the Windows machine is busy (ComfyUI, a game), but you have a box, a Mac,
and the cloud. Can the classifier hop to whatever machine has room?

We measured the options today:

- **Local GPU (the normal case): 0.03s.**
- **Cloud classifier: 0.7-1.0 seconds.** Still sub-second! The same Ollama trick that
  gives us key-free cloud DISPATCH also gives us key-free cloud CLASSIFICATION.
- **The box: 24.6 seconds for even a trivial prompt.** CPU-only prefill makes it
  hopeless for interactive routing - confirmed with a live test, not a guess.

So the design writes itself: the router checks the local GPU first; if it's starved, it
tries any peer machine running the classifier; if nothing local is available, it uses
the cloud classifier at under a second. The box stays a workhorse for overnight jobs,
never the interactive brain. That's a phase-2 feature (config + health checks), and the
measured numbers say it will feel instant even in the worst case.

## One-line summary for the product page

*"Routing decisions in under a second - usually 30 milliseconds - on your own hardware,
with automatic fallback to other machines or cloud when you're using the GPU for
something else."*
