"""Suite-level metrics for scripted voice calls.

Four questions, answered from the call reports:

1. Task completion — did each call produce the outcome it was scripted for?
2. Time-to-first-audio p95 — does the reply start fast enough, against budget?
3. Interruption success — when a caller barged in over speech, did playback
   stop within the stop budget, with the unheard remainder discarded?
4. Fallback appropriateness — did the runtime clarify (or hand off) exactly
   when recognition confidence was low, and never when it was fine?
"""
from __future__ import annotations

from voice.latency import percentile
from voice.pipeline import CallReport
from voice.session import run_suite

from .scenarios import SCENARIOS, Scenario


def task_completion(reports: list[CallReport], scenarios: list[Scenario]) -> tuple[int, int, float]:
    done = sum(1 for r, s in zip(reports, scenarios) if s.expected_fact in r.facts)
    total = len(scenarios)
    return done, total, (done / total if total else 0.0)


def ttfa_p95(reports: list[CallReport]) -> int | None:
    values: list[int] = []
    for report in reports:
        values.extend(report.ledger.values("time_to_first_audio"))
    return percentile(values, 95)


def interruption_success(reports: list[CallReport]) -> tuple[int, int, float]:
    """(succeeded, attempted, rate) over barge-ins during SPEAKING."""
    attempted = 0
    succeeded = 0
    for report in reports:
        stops = {
            e.turn_index: e.actual_ms for e in report.ledger.entries if e.stage == "barge_in_stop"
        }
        for turn in report.turns:
            if not turn.interrupted_speaking:
                continue
            attempted += 1
            stop = stops.get(turn.index)
            if stop is not None and stop <= report.ledger.budgets.barge_in_stop_ms:
                succeeded += 1
    return succeeded, attempted, (succeeded / attempted if attempted else 1.0)


def fallback_appropriateness(reports: list[CallReport], threshold: float = 0.65) -> tuple[int, int, float]:
    """Per user turn: low confidence must meet a fallback; normal must not."""
    appropriate = 0
    total = 0
    for report in reports:
        for turn in report.turns:
            if turn.kind != "user" or turn.superseded:
                continue
            total += 1
            fell_back = any(e in turn.events for e in ("clarify", "offer_handoff"))
            if (turn.confidence < threshold) == fell_back:
                appropriate += 1
    return appropriate, total, (appropriate / total if total else 0.0)


def suite_summary() -> dict:
    reports = run_suite(SCENARIOS)
    done, total, rate = task_completion(reports, SCENARIOS)
    i_ok, i_total, i_rate = interruption_success(reports)
    f_ok, f_total, f_rate = fallback_appropriateness(reports)
    total_breaches = sum(len(r.breaches()) for r in reports)
    return {
        "scenarios": total,
        "task_completion": f"{done}/{total}",
        "task_completion_rate": rate,
        "ttfa_p95_ms": ttfa_p95(reports),
        "ttfa_budget_ms": reports[0].ledger.budgets.time_to_first_audio_ms if reports else None,
        "interruption_success": f"{i_ok}/{i_total}",
        "interruption_rate": i_rate,
        "fallback_appropriateness": f"{f_ok}/{f_total}",
        "fallback_rate": f_rate,
        "total_budget_breaches": total_breaches,
        "reports": reports,
    }
