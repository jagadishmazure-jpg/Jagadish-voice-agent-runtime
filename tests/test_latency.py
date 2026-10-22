import pytest

from voice.latency import LatencyBudgets, LatencyLedger, percentile


class TestPercentile:
    def test_empty_returns_none(self):
        assert percentile([], 95) is None

    def test_single_value(self):
        assert percentile([420], 50) == 420
        assert percentile([420], 95) == 420

    def test_nearest_rank_p50(self):
        assert percentile([10, 20, 30, 40], 50) == 20

    def test_nearest_rank_p95(self):
        assert percentile(list(range(1, 101)), 95) == 95

    def test_p100_is_max(self):
        assert percentile([5, 9, 1], 100) == 9

    def test_unsorted_input(self):
        assert percentile([40, 10, 30, 20], 50) == 20

    def test_invalid_p_rejected(self):
        with pytest.raises(ValueError):
            percentile([1], 0)
        with pytest.raises(ValueError):
            percentile([1], 101)


class TestLatencyLedger:
    def test_record_uses_budget_for_stage(self):
        ledger = LatencyLedger()
        entry = ledger.record(0, "stt_final", 160)
        assert entry.budget_ms == 300
        assert not entry.breached

    def test_breach_flagged_over_budget(self):
        ledger = LatencyLedger()
        entry = ledger.record(0, "end_to_end", 1501)
        assert entry.breached
        assert ledger.breaches() == [entry]

    def test_exactly_at_budget_is_not_a_breach(self):
        ledger = LatencyLedger()
        assert not ledger.record(0, "time_to_first_audio", 800).breached

    def test_custom_budgets(self):
        ledger = LatencyLedger(LatencyBudgets(time_to_first_audio_ms=400))
        assert ledger.record(0, "time_to_first_audio", 430).breached

    def test_values_filtered_by_stage(self):
        ledger = LatencyLedger()
        ledger.record(0, "stt_final", 160)
        ledger.record(0, "time_to_first_audio", 430)
        ledger.record(1, "stt_final", 160)
        assert ledger.values("stt_final") == [160, 160]
        assert ledger.values("end_to_end") == []

    def test_summary_reports_percentiles_and_breaches(self):
        ledger = LatencyLedger()
        for i, ms in enumerate([400, 430, 430, 900]):
            ledger.record(i, "time_to_first_audio", ms)
        summary = ledger.summary()
        stage = summary["time_to_first_audio"]
        assert stage["count"] == 4
        assert stage["p50"] == 430
        assert stage["max"] == 900
        assert stage["breaches"] == 1
        assert "end_to_end" not in summary  # no measurements, no row
