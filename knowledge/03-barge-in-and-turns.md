# 03 — Barge-in and turn detection

## End-of-turn: when has the user actually finished?

Two signals, combined in `voice/turns.py`:

- **Silence.** A pause of at least 700 ms is a candidate ending; a pause of
  1200 ms ends the turn regardless.
- **Completeness.** Terminal punctuation ends a turn. A trailing
  conjunction, article or filler ("...cancel my order and", "I was thinking
  um") does not — the speaker is mid-thought, and cutting in to act on half
  a request is the rudest failure a voice agent has.

The trade-off is real: wait longer and the agent feels slow; wait less and
it interrupts. The heuristics here are deliberately simple and legible —
production systems learn this boundary from call data, but the *shape*
(silence × completeness, long-silence override) is the same.

## Barge-in during SPEAKING

The user starts talking over the reply. The runtime:

1. Stops playback within the stop budget (120 ms simulated, budget 150 ms).
2. Computes what was actually heard: segments fully or partly played count
   as spoken; every later segment is **discarded and logged** — the agent
   must never believe the user heard something they didn't.
3. Treats the interrupting utterance as the next turn.

In the suite's barge-in call, the caller hears the first status segment,
interrupts, and the tail of the reply ("delivery and should arrive today.")
is discarded and accounted for — `discarded_segments == 1` in the report.

## Barge-in during THINKING

The user corrects themselves before the agent has spoken ("Where is my
order CP-1001?" — "Sorry, I meant CP-1002."). Waiting for the first answer
and then processing the correction wastes a full turn and feels deaf. The
in-flight turn is cancelled and marked **superseded**; the correction
becomes the turn. No audio latencies are recorded for the superseded turn,
because no audio ever existed.
