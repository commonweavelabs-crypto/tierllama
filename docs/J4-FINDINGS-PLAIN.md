# The ladder that catches its own mistakes

*Plain-language findings note from building Tierllama (J4: the escalation ladder).
Technical version: docs/jevllama-j4-findings.md.*

## What J4 was

J1-J3 gave the router a brain (classification), honesty (real probabilities), and hands
(lane dispatch). J4 gives it judgment under failure: when a dispatch fails, don't give
up and don't dump the error on the user - climb the ladder. Retry the same lane, ask
the classifier to look again, move up to a stronger model, and log every step.

## The test that proves it

We broke the router on purpose: pointed the local lane at a model name that doesn't
exist. Then we sent a message.

What happened, in order, from the decision log:
1. Tried the local lane - failed fast, in 20 milliseconds (that's the ladder reading
   the error as data, not crashing)
2. Asked the classifier to re-read the message - "still a TEACHER question, I'm certain"
3. Tried the local lane once more - same error
4. Escalated to the cloud lane - and it worked, 2.1 seconds, correct answer

Total cost of the failure: about 50 milliseconds of wasted probes. The user saw a
working answer 2.9 seconds after sending. No error message, no retry button, no
"something went wrong."

## The insight worth keeping

A router with an escalation ladder doesn't need to be perfect - it needs to be
**recoverable**. The classifier at 94% accuracy plus a ladder that climbs on failure
beats a mythical 100% classifier with no safety net. The cheap mistakes (J1's finding)
stay cheap; the expensive mistakes get caught by structure instead of luck.

## The surprise: ambiguity mostly disappeared

The messages we designed as "ambiguous, will need fallback" - like "review my project
end to end and fix what's wrong" - now route correctly on the first try with the
few-shot rubric. The escalation ladder's most important job today is catching real
failures, not fixing confusion. Confidence-gating remains wired for the tail.

## Takeaway for anyone building multi-model systems

- Make failures data: adapters that return status instead of raising are what make an
  escalation ladder possible.
- Retry cheap, escalate expensive: two fast probes on the cheap lane before paying for
  the strong model - and re-ask the classifier between attempts.
- Log every step: you can't improve what you don't record.
- Measure the ladder separately from the lanes: our escalation overhead is
  milliseconds; the lanes' cold starts are seconds. Don't confuse the two.

*J4 live result: forced failure → auto-recovery to a working lane in 2.9 seconds, every
step on the record. Open build log; repos are public.*
