# J1 acceptance (live, 2026-09-21)
Router core skeleton at C:/Users/Guilherme/tierllama (git repo initialized).
Few-shot rubric (v6) was the lever: role 75->95->100% across v5/v6/final runs.
FINAL: 20 msgs, avg 0.46s incl classifier; role 100%, difficulty 85%, timing 95%, lane 80%.
Decision log fields: ts, message, role(+conf), difficulty(+conf), timing(+conf), lane, latency.
Difficulty calibration remains the weak dim (MEDIUM-hedging) -> J2 (logprobs + anchors).
Misses are all ONE-lane slips (MEDIUM vs EASY = $0 vs $0.15/Mtok) - cheap errors.
