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

## AI + human collaboration additions (contact/)

| Threat | Control | Test |
|---|---|---|
| PII leaks into the handoff packet, analytics events or logs (Information disclosure) | `mask`/`mask_obj` on every packet field, every event payload, and `MaskingFormatter` for logs | `test_packet_is_pii_masked_everywhere`, `test_publish_to_queue_and_file_masked`, `test_no_call_dropped_and_no_pii_in_any_event` |
| Model calls a side-effecting tool without consent (Excessive agency, LLM06) | single-use consent token minted only after the confirmation gate | `test_reschedule_needs_minted_single_use_consent`, `test_consent_before_reschedule` |
| Malformed or injected tool arguments (Tampering) | schema validation: no extra keys, required fields, types | `test_tool_input_rejected` |
| Poisoned analytics stream (Tampering) | strict event envelope and payload schema, NaN and bool-as-number rejected | `test_schema_rejects_bad_events` |
| Caller dropped during transfer (Denial of service) | warm transfer with no-answer return to AI | `test_warm_transfer_no_answer_returns_to_ai_not_dropped` |
| Scorecard gamed by negative costs (Repudiation / integrity) | `CallRecord` rejects negative / NaN values | `test_record_rejects_invalid` |
