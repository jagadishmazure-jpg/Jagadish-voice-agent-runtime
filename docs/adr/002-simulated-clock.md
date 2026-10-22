# ADR 002 — An injectable simulated clock

**Status:** accepted (2026-10-22)

**Context.** Latency budgets and barge-in timing must be testable without
audio hardware and without flaky wall-clock tests.

**Decision.** All stages advance a simulated clock; adapters declare their
timing. Reports come from that timeline.

**Consequences.** Every latency figure in this repo is simulated and is
labelled as such. Real provider latency must be measured after a real
adapter is integrated.
