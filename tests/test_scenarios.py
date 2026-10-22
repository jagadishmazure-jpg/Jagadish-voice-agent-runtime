from evaluation.metrics import (
    fallback_appropriateness,
    interruption_success,
    suite_summary,
    task_completion,
    ttfa_p95,
)
from evaluation.scenarios import SCENARIOS
from voice.session import run_suite


class TestScenarioSuite:
    def test_eight_scenarios(self):
        assert len(SCENARIOS) == 8

    def test_all_scenarios_complete_their_task(self):
        reports = run_suite(SCENARIOS)
        done, total, rate = task_completion(reports, SCENARIOS)
        assert (done, total) == (8, 8)
        assert rate == 1.0

    def test_suite_is_deterministic(self):
        first = run_suite(SCENARIOS)
        second = run_suite(SCENARIOS)
        for a, b in zip(first, second):
            assert [t.reply_text for t in a.turns] == [t.reply_text for t in b.turns]
            assert [(e.stage, e.actual_ms) for e in a.ledger.entries] == [
                (e.stage, e.actual_ms) for e in b.ledger.entries
            ]
            assert a.facts == b.facts

    def test_exactly_one_budget_breach_across_suite(self):
        reports = run_suite(SCENARIOS)
        assert sum(len(r.breaches()) for r in reports) == 1

    def test_ttfa_p95_within_budget(self):
        reports = run_suite(SCENARIOS)
        assert ttfa_p95(reports) == 430
        assert ttfa_p95(reports) <= reports[0].ledger.budgets.time_to_first_audio_ms

    def test_interruption_success_rate(self):
        reports = run_suite(SCENARIOS)
        ok, attempted, rate = interruption_success(reports)
        assert attempted == 1
        assert ok == 1
        assert rate == 1.0

    def test_fallback_appropriateness(self):
        reports = run_suite(SCENARIOS)
        ok, total, rate = fallback_appropriateness(reports)
        assert rate == 1.0
        assert total == 10  # user turns across the suite, superseded excluded

    def test_suite_summary_headline_numbers(self):
        summary = suite_summary()
        assert summary["task_completion"] == "8/8"
        assert summary["ttfa_p95_ms"] == 430
        assert summary["interruption_success"] == "1/1"
        assert summary["fallback_appropriateness"] == "10/10"
        assert summary["total_budget_breaches"] == 1
