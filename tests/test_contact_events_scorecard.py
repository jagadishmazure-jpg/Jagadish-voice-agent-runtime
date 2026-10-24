import math

import pytest

from contact import scorecard
from contact.events import FileSink, Publisher, QueueSink, SchemaError, validate
from contact.pii import has_pii
from contact.scorecard import CallRecord
from contact.simulation import COHORTS, run, simulate_call, without_packet_record


def test_publish_to_queue_and_file_masked(tmp_path):
    q, f = QueueSink(), FileSink(tmp_path / "events.jsonl")
    p = Publisher("c-1", [q, f])
    p.publish("transcript", {"speaker": "caller", "text": "card 4111111111111111 a@b.co", "confidence": 0.9}, 10)
    p.publish("sentiment", {"score": -0.4}, 11)
    p.publish("intent", {"intent": "order_status"}, 12)
    got = q.drain()
    assert [e["seq"] for e in got] == [0, 1, 2] and f.read() == got
    assert not has_pii((tmp_path / "events.jsonl").read_text())


@pytest.mark.parametrize("etype,payload", [
    ("unknown", {"x": 1}),
    ("sentiment", {}),
    ("sentiment", {"score": 0.1, "extra": 1}),
    ("sentiment", {"score": "bad"}),
    ("sentiment", {"score": math.nan}),
    ("sentiment", {"score": True}),
])
def test_schema_rejects_bad_events(etype, payload):
    p = Publisher("c", [QueueSink()])
    with pytest.raises(SchemaError):
        p.publish(etype, payload, 0)
    assert p.rejected == 1 and p.seq == 0


def test_envelope_must_be_exact():
    good = {"schema_version": 1, "event_type": "intent", "call_id": "c", "seq": 0, "ts_ms": 0,
            "payload": {"intent": "x"}}
    validate(good)
    with pytest.raises(SchemaError):
        validate({**good, "debug": True})
    with pytest.raises(SchemaError):
        validate({**good, "schema_version": 2})


def _r(**kw):
    base = dict(resolved=True, contained=True, handle_time_s=60, transfers=0, cost=0.1, ai_actions=1,
                human_actions=0)
    base.update(kw)
    return CallRecord(**base)


@pytest.mark.parametrize("kw", [{"cost": -0.01}, {"handle_time_s": -1}, {"cost": math.nan}, {"transfers": -1},
                                {"contained": True, "transfers": 1}])
def test_record_rejects_invalid(kw):
    with pytest.raises(ValueError):
        _r(**kw)


def test_scorecard_maths():
    recs = [_r(), _r(resolved=False, contained=False, transfers=1, cost=1.0, ai_actions=0, human_actions=1),
            _r(contained=False, transfers=1, cost=2.0, handle_time_s=240, human_actions=1)]
    s = scorecard.build(recs)
    assert s.resolution_rate == pytest.approx(2 / 3) and s.containment_rate == pytest.approx(1 / 3)
    assert s.avg_handle_time_s == 120 and s.transfers_per_call == pytest.approx(2 / 3)
    assert s.cost_per_resolved == pytest.approx(3.1 / 2) and s.automation_rate == pytest.approx(2 / 4)
    assert 0 <= s.index <= 100


def test_scorecard_perfect_and_unresolved():
    assert scorecard.build([_r(cost=0.0, handle_time_s=0)]).index == 100.0
    s = scorecard.build([_r(resolved=False, contained=False)])
    assert s.cost_per_resolved is None


@pytest.mark.parametrize("w", [{"outcome": 1.0}, {"outcome": 0.5, "efficiency": 0.5, "cost": 0.5, "automation": -0.5},
                               {"outcome": 0.3, "efficiency": 0.3, "cost": 0.3, "automation": 0.3}])
def test_bad_weights_rejected(w):
    with pytest.raises(ValueError):
        scorecard.build([_r()], weights=w)


def test_empty_scorecard_rejected():
    with pytest.raises(ValueError):
        scorecard.build([])


@pytest.fixture(scope="module")
def sim():
    return run(50)


def test_simulation_is_deterministic():
    a, b = simulate_call(3, "reschedule"), simulate_call(3, "reschedule")
    assert a.record == b.record and a.events == b.events


def test_zero_repeats_with_packet_over_all_simulated_calls(sim):
    taken = [r for r in sim if r.escalated and r.record.resolved]
    assert taken and sum(r.repeats_with_packet for r in taken) == 0
    assert sum(r.repeats_without_packet for r in taken) > len(taken)


def test_no_call_dropped_and_no_pii_in_any_event(sim):
    assert not any(r.caller_dropped for r in sim)
    assert not any(has_pii(str(e["payload"])) for r in sim for e in r.events)


def test_every_cohort_routes_to_its_escalation_reason(sim):
    want = {"angry_customer": "angry", "sensitive_topic": "sensitive", "noisy_line": "low_confidence",
            "asks_for_human": "requested", "order_status": None, "reschedule": None}
    for c in COHORTS:
        assert {r.escalated for r in sim if r.cohort == c} == {want[c]}


def test_handbacks_cause_no_ai_reasks(sim):
    hb = [r.handback_ai_repeats for r in sim if r.handback_ai_repeats is not None]
    assert hb and sum(hb) == 0


def test_packet_cuts_handle_time_and_cost(sim):
    with_p = scorecard.build([r.record for r in sim])
    without = scorecard.build([without_packet_record(r) for r in sim])
    assert with_p.avg_handle_time_s < without.avg_handle_time_s
    assert with_p.cost_per_resolved < without.cost_per_resolved and with_p.index > without.index
