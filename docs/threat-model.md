# Threat model — voice agent runtime

Scope: the call pipeline, confirmation gate, confidence fallbacks and the
demo support agent. Assets: the caller's orders (side effects), the
caller's trust that "Done" means done, and latency budgets.

## STRIDE

| Threat | Example | Control | Residual risk |
| --- | --- | --- | --- |
| Spoofing | A bystander or a TV in the room says "yes" | Confirmation is a separate turn naming the action; low-confidence yes is re-asked | No speaker verification (planned with a real audio path) |
| Tampering | Barge-in text rewrites a pending action | Pending action is fixed when armed; a new request supersedes, it does not edit | — |
| Repudiation | Caller disputes a cancellation | Every turn records events (`confirmation_executed`, `_rejected`) and facts | Transcripts are simulated here |
| Information disclosure | Order details read to the wrong caller | Out of scope in the demo (no auth); adopters must verify the caller before order lookups | Documented |
| Denial of service | Long replies blow the latency budget | Per-stage budgets with breach flagging; barge-in stops playback | Breach is flagged, not prevented |
| Elevation of privilege | The responder executes its own action | Responder returns a `PendingAction`; only the runtime gate can execute | — |

## OWASP LLM Top 10 (relevant items)

- **LLM06 Excessive agency** — side effects only through the gate, with an
  explicit, confident, un-negated yes.
- **LLM09 Misinformation** — the agent refuses to act on unknown orders
  instead of reporting a fictitious success.
