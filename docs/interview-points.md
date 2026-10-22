# Interview talking points

## 30-second story

"Text agents get finished messages; voice agents live in a stream — and
that changes the engineering. I built a voice-agent runtime that treats a
call as an explicit state machine with per-stage latency budgets, barge-in
handling, confidence fallbacks, and a spoken confirmation gate for
side-effecting actions. It runs on simulated streams with an injectable
clock, so every behaviour — including the numbers — is deterministic and
testable offline: 91 tests, and an 8-call scenario suite that completes
8/8 tasks with time-to-first-audio p95 of 430 ms against an 800 ms budget."

## Points to land

- **Latency is the interface.** Budget per stage (STT final 300 ms, first
  audio 800 ms, end-to-end 1500 ms, barge-in stop 150 ms), measured per
  turn, reported as percentiles. Streaming TTS exists to decouple "reply
  started" from "reply finished".
- **Barge-in is a correctness problem, not a UX garnish.** If the user
  interrupts, the unheard remainder must be discarded *and logged* —
  otherwise the agent believes it said things the user never heard. Same
  for thinking-time: a self-correction supersedes the in-flight turn.
- **Confidence is a routing signal.** Low STT confidence → clarify once →
  human handoff. Guessing on a garbled "cancel my order" is how voice
  agents do real damage.
- **Confirmation gates apply to voice too.** Side effects need an explicit
  spoken yes in a separate turn; ambiguous answers re-ask once, then
  reject. In the suite, a cancellation executes only after "yes" and is
  left untouched after "no" — both paths tested.
- **Deterministic simulation beats flaky realism in CI.** Injectable clock
  + scripted streams: the same suite produces the same numbers on every
  run, so a regression is a regression, not weather.

## Likely follow-ups

- *"How would end-of-turn work with real audio?"* — VAD energy + the same
  completeness heuristics on partials; the long-silence override stays as
  the safety net. The detector's contract doesn't change.
- *"Where does an LLM fit?"* — behind `respond()`. The runtime doesn't
  care; the gate, budgets and fallbacks wrap any responder.
- *"What's missing for production?"* — real audio path, PII redaction on
  transcripts, consent/recording rules, concurrency and provider limits.
  The repo's README lists these as planned, not built.
