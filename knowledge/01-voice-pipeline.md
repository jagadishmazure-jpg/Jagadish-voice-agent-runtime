# 01 — The voice pipeline

A text agent gets a finished message and returns a finished message. A voice
agent lives in a stream: words arrive one at a time, the user can talk over
the reply, and every stage spends from a latency budget the user *feels*.

## The stages

1. **Listening.** The STT service streams partial transcripts ("where",
   "where is", "where is my order..."). Nothing is final yet — acting on a
   partial is how agents answer questions nobody asked.
2. **End-of-turn detection.** Silence plus linguistic completeness decide
   the user has finished (see 03). Only then is the transcript finalised,
   with a confidence score.
3. **Thinking.** The responder (an LLM in production; a deterministic
   rule-based agent in this repo) produces a reply — or a pending action
   that needs spoken confirmation first.
4. **Speaking.** The reply is chunked into speakable segments and streamed.
   The first segment starts after a short synthesis delay; that gap is the
   time-to-first-audio the caller actually notices.

## The state machine

`IDLE → LISTENING → THINKING → SPEAKING → LISTENING … → ENDED`

The machine is explicit and refuses illegal transitions. That sounds
bureaucratic until a bug tries to speak while already speaking, or finalise
a transcript for a turn that was barged in and cancelled — the machine makes
those states unrepresentable instead of debugging them from call recordings.

Every transition is timestamped on the (simulated) clock, so a call report
reconstructs the whole call: where time went, what was heard, what was
thrown away.

## Why a simulation?

Real audio, real STT and real TTS make tests slow, flaky and non-repeatable.
Here the clock is injectable and the adapters are fakes with the same
contracts as the real services (streaming partials in, segmented audio out),
so the *engineering* — budgets, interruptions, fallbacks, confirmation — is
tested deterministically. The adapters are the seam where production
services plug in.
