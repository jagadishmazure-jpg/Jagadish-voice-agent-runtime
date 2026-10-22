# Implementation guide

For engineers adopting this runtime shape in a real voice product.

## Run it

```bash
python demos/demo_run.py     # the 8-call scenario suite with headline metrics
python -m pytest tests/      # 91 deterministic tests
python scripts/count_tests.py
```

No dependencies beyond the Python standard library (3.10+).

## Swap in real adapters

The fakes are interfaces, not shortcuts:

- **STT.** Replace `FakeSTT` with a streaming recogniser (Whisper-style
  batch or a streaming service). Keep the contract: partials as the user
  speaks, then a final transcript **with a confidence score** — the fallback
  layer depends on the score existing. If your provider only returns a
  transcript, derive a proxy confidence (word-level scores averaged) and
  calibrate the 0.65 threshold against labelled calls before launch.
- **Agent.** Any object with `respond(text) -> AgentReply` and
  `execute(action)` works. An LLM responder slots in unchanged; return
  `PendingAction` for anything with side effects and let the runtime gate
  it — do not let the model self-confirm.
- **TTS.** Replace `FakeTTS` with a streaming synthesiser. Keep segment
  chunking (sentence-sized, length-capped): it is what makes
  time-to-first-audio small and barge-in discard accounting possible.
- **Clock.** Inject a wall clock in production; keep `SimClock` in tests.

## Tune the budgets

Defaults (300 / 800 / 1500 / 150 ms) are starting points for a support
call, not laws. Measure your real p95s per stage, then set budgets slightly
above them so a breach means "something changed", not "Tuesday". Track
breaches per stage: STT breaches point at the provider or the audio path;
end-to-end breaches with a healthy time-to-first-audio point at reply
*length* — a conversation-design problem, not an infrastructure one.

## Tune the fallbacks

- Clarify once, then hand off. A third attempt at the same garbled line
  helps no one; the tracker escalates after two consecutive low-confidence
  turns.
- Log every fallback with the confidence that triggered it. A rising
  clarify rate is your earliest signal of audio-quality or accent-coverage
  problems.
- Confirmation turns are turns: they get STT, latencies and records like
  any other, and an ambiguous answer re-asks once and then rejects.
  Ambiguity is never consent.

## What to add for production

- Real audio path (telephony/WebRTC), VAD-driven (not heuristic) end-of-turn.
- Per-call recording/consent handling and PII redaction before transcripts
  hit logs or eval stores.
- The discarded-speech log feeding conversation design: segments users
  habitually interrupt are segments to delete.
- Load behaviour: concurrent sessions, provider rate limits, and graceful
  degradation (shorter replies, faster voice) under latency pressure.
