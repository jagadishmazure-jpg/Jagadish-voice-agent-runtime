"""AI + human collaboration: repeat questions with vs without the handoff packet, and the scorecard."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


from contact import scorecard  # noqa: E402
from contact.pii import has_pii  # noqa: E402
from contact.simulation import COHORTS, run, without_packet_record  # noqa: E402

N = 50
results = run(N)
print(f"Simulated calls: {len(results)} ({N} per cohort x {len(COHORTS)} cohorts, seed 7)")
esc = [r for r in results if r.escalated]
taken = [r for r in esc if r.record.resolved or r.repeats_without_packet]
print(f"Escalated: {len(esc)}  (reasons: " + ", ".join(
    f"{k}={sum(r.escalated == k for r in esc)}" for k in ("low_confidence", "angry", "sensitive", "requested")) + ")")
print(f"Human did not answer, caller kept with AI: {sum(not r.record.resolved for r in esc)}")
print(f"Calls dropped during transfer: {sum(r.caller_dropped for r in results)}")
print("-" * 72)
print("Repeat questions asked by the human (questions about things the caller already said)")
w = sum(r.repeats_with_packet for r in taken)
wo = sum(r.repeats_without_packet for r in taken)
print(f"  with handoff packet:    {w} across {len(taken)} answered transfers")
print(f"  without packet (cold):  {wo} across {len(taken)} answered transfers ({wo / len(taken):.2f} per call)")
hb = [r.handback_ai_repeats for r in results if r.handback_ai_repeats is not None]
print(f"  AI re-asks after human handback: {sum(hb)} across {len(hb)} handbacks")
events = [e for r in results for e in r.events]
leaks = sum(has_pii(str(e["payload"])) for e in events)
print(f"Events published: {len(events)}, raw PII found in sink payloads: {leaks}")
print("-" * 72)
hdr = f"{'cohort':<16}{'resol':>6}{'contain':>8}{'AHT s':>7}{'xfer':>6}{'$/resolved':>11}{'auto':>6}{'index':>7}"
print(hdr)


def row(name: str, recs: list) -> None:
    s = scorecard.build(recs)
    cpr = f"{s.cost_per_resolved:.3f}" if s.cost_per_resolved is not None else "n/a"
    print(f"{name:<16}{s.resolution_rate:>6.0%}{s.containment_rate:>8.0%}{s.avg_handle_time_s:>7.0f}"
          f"{s.transfers_per_call:>6.2f}{cpr:>11}{s.automation_rate:>6.0%}{s.index:>7.1f}")


for c in COHORTS:
    row(c, [r.record for r in results if r.cohort == c])
row("ALL (packet)", [r.record for r in results])
row("ALL (no packet)", [without_packet_record(r) for r in results])
