# ADR 003: The handoff packet is a schema, and repeats are measured

**Status:** accepted (2026-10-23)

**Context.** The usual failure of AI-to-human escalation is that the human
starts over: "can I verify your account?", "what's the order number?".
That is invisible unless it is counted.

**Decision.** The handoff packet has a fixed field list (`PACKET_FIELDS`)
and is masked as a whole. The simulated human asks only for slots the packet
lacks, and any question about something the caller already said is counted
as a repeat. The same call is replayed without the packet as the baseline.
Transfers are warm: the AI leaves only after the human is on the line.

**Consequences.** "Zero repeats" is a CI-checked number, not a promise.
The simulated human is a model of good behaviour; real agents may still
re-ask, so production should log repeat questions from real transcripts.
