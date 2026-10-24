import copy

import pytest

from contact.escalation import EscalationPolicy, score
from contact.handoff import (
    PACKET_FIELDS,
    Call,
    CallContext,
    HumanAgent,
    ai_next_questions,
    blind_transfer,
    build_packet,
    handback,
    warm_transfer,
)
from contact.pii import has_pii
from voice.agent import PendingAction
from voice.fallbacks import ConfirmationGate


@pytest.mark.parametrize("text,reason", [
    ("Can I talk to a real person please", "requested"),
    ("agent", "requested"),
    ("I think this is fraud", "sensitive"),
    ("My father passed away and the order is in his name", "sensitive"),
    ("I will call my lawyer", "sensitive"),
    ("This is the worst, unacceptable!", "angry"),
])
def test_escalation_triggers(text, reason):
    assert EscalationPolicy().check(text) == reason


def test_low_confidence_needs_two_turns():
    p = EscalationPolicy()
    assert p.check("uh", 0.4) is None
    assert p.check("mm", 0.4) == "low_confidence"


def test_one_good_turn_resets_low_confidence():
    p = EscalationPolicy()
    p.check("uh", 0.4)
    p.check("order CP-1001", 0.9)
    assert p.check("mm", 0.4) is None


def test_falling_sentiment_trend_escalates():
    p = EscalationPolicy()
    assert p.check("thanks, that is great") is None
    assert p.check("hmm ok fine") is None
    assert p.check("it's late again") == "angry"


def test_calm_caller_not_escalated():
    p = EscalationPolicy()
    assert [p.check(t) for t in ("where is order CP-1001", "ok", "thanks")] == [None, None, None]
    assert score("thank you, great") > 0 > score("useless and late")


def _ctx():
    c = CallContext("t-1", identity_verified=True, identity_method="email_on_file", customer_id="C-100",
                    intent="reschedule_delivery")
    c.provide("order_id", "CP-1001")
    c.provide("email", "ana.lindqvist@example.com")
    c.provide("new_date", "2026-11-14")
    c.actions_taken.append({"actor": "ai", "action": "lookup_order", "result": "shipped"})
    c.say("caller", "my card 4111 1111 1111 1111 and phone 415-555-0142, ssn 123-45-6789")
    c.say("ai", "Thanks ana.lindqvist@example.com")
    c.open_question = "Caller wants a refund to ana.lindqvist@example.com"
    c.sentiment = [0.0, -0.3, -0.6]
    return c


def test_packet_has_every_field():
    d = build_packet(_ctx(), "angry").to_dict()
    assert tuple(d) == PACKET_FIELDS
    assert d["identity"]["verified"] is True and d["intent"] == "reschedule_delivery"
    assert d["actions_taken"][0]["action"] == "lookup_order" and d["sentiment_trend"] == [0.0, -0.3, -0.6]


def test_packet_is_pii_masked_everywhere():
    d = build_packet(_ctx(), "angry").to_dict()
    assert not has_pii(str(d))
    assert "[CARD]" in d["transcript_summary"] and "[PHONE]" in d["transcript_summary"]
    assert "[SSN]" in d["transcript_summary"] and d["entities"]["email"] == "[EMAIL]"
    assert d["entities"]["order_id"] == "CP-1001"  # business IDs survive


def test_zero_repeat_with_packet():
    ctx = _ctx()
    h = HumanAgent()
    h.take_call(ctx, build_packet(ctx, "angry"))
    assert h.repeats == 0 and h.questions == []


def test_cold_transfer_repeats_everything():
    ctx = _ctx()
    h = HumanAgent()
    h.take_call(ctx, None)
    assert h.repeats == 6  # identity, intent, order, date, email, actions


def test_human_still_asks_genuinely_missing_slots_without_counting_repeat():
    ctx = CallContext("t-2")
    ctx.say("caller", "help")
    h = HumanAgent()
    h.take_call(ctx, build_packet(ctx, "requested"))
    assert len(h.questions) == 2 and h.repeats == 0


def test_handback_preserves_context_and_ai_does_not_reask():
    ctx = _ctx()
    pkt = handback(ctx, "Refund approved for ana.lindqvist@example.com", {"case": "D-77"})
    assert pkt.escalation_reason == "handback" and pkt.entities["case"] == "D-77"
    assert pkt.actions_taken[-1]["actor"] == "human" and not has_pii(str(pkt.to_dict()))
    assert ai_next_questions(ctx, ["identity", "intent", "order_id", "new_date"]) == []
    assert pkt.open_question is None


def test_warm_transfer_keeps_caller_connected():
    call = Call()
    assert warm_transfer(call, build_packet(_ctx(), "angry"), human_answers=True) == "human"
    assert call.caller_connected and call.legs == {"caller", "human"}
    assert call.timeline.index("conference_3_way") < call.timeline.index("ai_leg_left")


def test_warm_transfer_no_answer_returns_to_ai_not_dropped():
    call = Call()
    assert warm_transfer(call, build_packet(_ctx(), "angry"), human_answers=False) == "ai"
    assert call.caller_connected and "ai" in call.legs and "offer_callback" in call.timeline


def test_blind_transfer_baseline_drops_on_no_answer():
    call = Call()
    assert blind_transfer(call, human_answers=False) == "dropped" and not call.caller_connected


@pytest.mark.parametrize("answer,conf,status", [
    ("yes", 0.95, "executed"),
    ("yes", 0.30, "reprompt"),
    ("yes, wait, no", 0.95, "reprompt"),
    ("no", 0.95, "rejected"),
])
def test_consent_before_reschedule(answer, conf, status):
    g = ConfirmationGate()
    g.arm(PendingAction("reschedule", "CP-1001", "move delivery"))
    assert g.respond(answer, conf).status == status


def test_packet_is_deep_independent():
    ctx = _ctx()
    pkt = build_packet(ctx, "angry")
    before = copy.deepcopy(pkt.to_dict())
    ctx.actions_taken.append({"actor": "ai", "action": "x"})
    assert pkt.to_dict() == before
