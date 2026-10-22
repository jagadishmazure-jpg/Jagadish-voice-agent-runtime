# 02 — Latency budgets

In voice, latency is not a performance nicety — it is the user interface.
Pauses read as confusion. So each stage gets a budget, every turn is
measured against it, and breaches name the stage that blew it.

## The budgets (defaults in `voice/latency.py`)

| Stage | Measured from → to | Budget |
|---|---|---|
| STT final | end-of-turn → final transcript | 300 ms |
| Time-to-first-audio | end-of-turn → first reply audio | 800 ms |
| End-to-end turn | end-of-turn → reply fully spoken | 1500 ms |
| Barge-in stop | user starts speaking → playback halted | 150 ms |

## Why time-to-first-audio is the headline number

Callers judge responsiveness by when sound starts, not when it ends.
Streaming TTS exists precisely to decouple the two: synthesise segment one,
start playing, prepare the rest in parallel. In the scenario suite,
time-to-first-audio is 430 ms (160 STT finalise + 140 agent think + 130 TTS
synthesis) against the 800 ms budget — while a long reply's *total* speaking
time legitimately runs to seconds.

## End-to-end breaches are information, not just failures

The suite's one breach is deliberate: a caller asks for the full returns
policy and the spoken answer takes 5,470 simulated ms. No pipeline trick
fixes that — the content is long. The production answers are conversational,
not technical: summarise and offer the full text by message, or ask "short
version or full detail?" The ledger's job is to make the cost visible per
stage so the fix lands in the right place.

## Percentiles, not averages

Averages hide the tail callers remember. The ledger reports p50/p95/max per
stage across turns and sessions, nearest-rank. A p95 inside budget with a
breaching max is a very different system from a p50 already over budget.
