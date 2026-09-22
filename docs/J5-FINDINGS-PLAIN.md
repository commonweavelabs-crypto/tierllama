# The router that introduces itself to your network

*Plain-language findings note from building Tierllama (J5: doctor + discovery).
Technical version: docs/jevllama-j5-findings.md.*

## What J5 was

The "does it actually work on a fresh machine?" milestone. Three pieces: a **doctor**
command that checks the config against reality, a **network discovery** scan that finds
every Ollama on your LAN, and proof that a **fresh clone** routes messages from the
README instructions alone.

## The doctor

Four checks, ~3 seconds for the fast ones: is the classifier model alive? Does every
lane's configured model actually exist? Does the box queue work (proven by dropping a
tiny canary job and watching the box consume it in 75 seconds)? Did the network scan
find anything? All PASS on our machines. The canary is the star: file-copying to a
shared folder can "work" while the worker is dead - only watching the job get consumed
proves the pipeline end-to-end.

## The discovery: we found machines we didn't know about

The scan found FOUR hosts on Gui's home network in under ten seconds. Two of them run
Ollama - and Tierllama had never been installed on either. That's the whole product
wedge in one test: people who already run Ollama on multiple machines get fleet routing
by installing ONE app. Their existing installs become lanes automatically.

## The fresh-install test

We cloned the repo to a brand-new directory and followed only the README: route a
message (worked, exit 0, dispatched to the right lane), tail the log (worked), run the
discovery (found all 4 hosts). Fresh install to working router: about a minute,
dominated by the network scan. No accounts. No configuration.

## Takeaway

Two kinds of confidence come out of this milestone: the doctor turns "I think it's set
up right" into a PASS/FAIL report, and the canary turns "the queue is reachable" into
"the queue actually works." Every distributed system deserves both.

*J5 live: doctor all-PASS, canary consumed in 75s, LAN scan 4 hosts in 10s, fresh clone
routes on first try. Open build log; repos are public.*
