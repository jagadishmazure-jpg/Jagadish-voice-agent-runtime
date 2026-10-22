# ADR 001 — The confirmation gate lives in the runtime, not the agent

**Status:** accepted (2026-10-22)

**Context.** A prompt instruction to "confirm first" can be skipped by the
model. Voice adds recognition errors and talk-over.

**Decision.** The agent can only propose a `PendingAction`. The runtime's
gate executes it after a separate confirmation turn whose transcript is a
clear yes (no negation or hesitation words) at or above the confidence
threshold. Anything else re-asks once, then rejects.

**Consequences.** One extra turn per side effect, and some genuine yeses
("yes, no problem") are re-asked. That cost is accepted: a false yes is
worse than a repeated question.
