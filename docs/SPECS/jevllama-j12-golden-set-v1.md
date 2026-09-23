# J12 kick-off: golden set v1 results (62 prompts, 2026-09-22 night)

Method: 62 prompts (real video-workspace use cases + Gui's real messages +
edge cases), ground truth rated by Claude (reasoned), run through the LIVE
qwen3:4b classifier, miss patterns grouped into hypotheses.

## Scorecard (honest)
| dimension | accuracy |
|---|---|
| timing | 77.4% (48/62) |
| role | 69.4% (43/62) |
| difficulty | 54.8% (34/62) |
| full match | 35.5% (22/62) |

## Structural finding #1: EXPERT is unreachable
The difficulty enum in _classify_dims is [EASY, MEDIUM, HARD] - the
classifier can NEVER output EXPERT (J7 added the tier to the tree but not
to the classifier). All 3 EXPERT truth cases auto-fail. FIX: add EXPERT to
the enum + rubric definition.

## Hypotheses (data -> rules to tweak)
H1 (timing, 30x NOW->LATER): the dims classifier uses the OLD timing rule
line; the _dims path sends the same RUBRIC but "big work" still biases
LATER. Next: add explicit examples of HARD+NOW to the rubric examples list.
H2 (difficulty drift to MEDIUM, 30x): no difficulty anchor examples in the
enum prompt; model regresses to the middle. Fix: add per-level anchor
examples + sharpen definitions (EASY = one click/one line; HARD = multi-scene
or multi-system; EXPERT = frontier/research-grade).
H3 (role TEACHER/NAVIGATOR/SCREENWRITER -> DIRECTOR, 23x): "vague commands"
pulling everything to DIRECTOR. Fix: add counter-examples ("make it better"
on a known artifact = SCREENWRITER if text, NAVIGATOR if UI).
H4 (my truth ratings may be wrong on ~3 cases - e.g. "submit the render job
now" as EASY vs MEDIUM is genuinely debatable). Adjudication step needed:
don't tune the rubric to my errors.

## What ships next (J12 continues)
1. Fix the EXPERT enum gap (structural bug, not tuning)
2. Add anchor examples to the rubric, re-run the 62, measure delta
3. Grow the set toward 100+ and make it a standing test file
