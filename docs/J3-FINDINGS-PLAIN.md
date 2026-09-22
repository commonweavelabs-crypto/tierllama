# The day the router learned to actually do things

*A plain-language findings note from building Tierllama (J3: lane adapters). Technical
version: docs/jevllama-j3-findings.md.*

## What J3 was

J1 built the router's brain (classify every message), J2 made the brain honest (real
probabilities instead of fake confidence). J3 gave it hands: when the router decides a
message belongs to the free local model, the cheap cloud model, the expensive flagship,
or the overnight batch queue - it now ACTUALLY SENDS it there, and records what happened.

## The good surprise: cloud without keys

We expected the cloud lane to be the hard one - API keys, billing, provider accounts.
Then we realized something: our own AI stack already runs cloud models through local
Ollama. The model name just carries a `:cloud` suffix. So our router dispatches to the
cloud through the exact same server it uses for local models. No API key, no signup,
no configuration. For a user installing the MVP: local and cloud routing both work on
the first run. That's rare, and it's a real advantage.

## The dumb-but-real lesson: check your model names exist

First live run failed twice - not because the dispatch code was wrong, but because the
config listed models that weren't actually installed (a typo-level mistake: a model
name that exists elsewhere but not on this machine). The code couldn't have told us
loudly enough: it just said "404." Next milestone adds a `doctor` command that checks
every configured model exists before routing anything. Classic integration lesson:
validate your config against reality at startup, not at failure time.

## What latency taught us

When we routed five live messages end-to-end, the classifier took its usual 80-200
milliseconds. Everything else - 9 to 28 seconds - was the target models warming up.
The router is instant; the world it calls is not. Practical consequence: keep the
router permanently loaded, and be honest in the UI about what the lane's first call
costs. (A "model is waking up" indicator is now on the feature list.)

## The box question: when does "later" mean "overnight"?

One test message exposed a design question we hadn't pinned: "do everything needed to
finish the trailer by friday" is HARD (expensive model) but also LATER (not urgent).
We decided: HARD work goes to the strong model now, because the user asked and wants an
answer; the overnight queue is for explicitly batched work. And the refinement for the
next milestone: when the router sees HARD+LATER, it can offer the user a choice - answer
now for the expensive-call price, or queue it for the box overnight. That's a small UX
question that turns into real savings.

## Takeaways for anyone building multi-model dispatch

- Your local runtime may already route to cloud models - check before wiring API keys.
- Validate configured models exist at startup; config typos look like code bugs.
- Measure latency at every layer: classifier (~0.1s), local cold start (~3-10s),
  cloud cold start (up to ~30s). The router isn't the bottleneck.
- Make dispatch failures data, not exceptions - the next layer (escalation) needs to
  read them.

One more catch worth telling: our first box test sat untouched for an hour. The code
was right; the FORMAT was wrong - the box worker reads JSON job files, and we'd written
a markdown file. The worker didn't complain; it just silently ignored the file. One
line of format-fixing later, the box consumed the job in about a minute and answered
correctly. Silent contract mismatches are the sneakiest bug class in distributed
systems - the fix is a startup canary: send a tiny known job at startup and check it
comes back. That's going into the doctor command.

*J3 live results: all three lanes dispatched, confirmed, and ANSWERED - local ("OK" in
3s), cloud ("OK" in 2s), box (consumed and answered in ~60s). Decision log records
every dispatch with model + latency. Open build log; repos are public.*
