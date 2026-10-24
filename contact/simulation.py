"""Seeded simulated calls that exercise tools, escalation, handoff and the scorecard.

Nothing here is a real call. Callers are scripted per cohort, randomness comes
from a fixed seed, and handle times and costs use the simulated constants
below. The point is to measure the *mechanisms* (repeat questions with and
without the packet, escalation routing, scorecard maths) reproducibly.
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field

from voice.agent import PendingAction
from voice.fallbacks import ConfirmationGate

from .escalation import EscalationPolicy
from .events import Publisher, QueueSink
from .handoff import Call, CallContext, HumanAgent, ai_next_questions, build_packet, handback, warm_transfer
from .scorecard import CallRecord
from .tools import ToolError, ToolServer

# Simulated constants (assumptions, not measurements).
AI_TURN_S, TRANSFER_S, HUMAN_Q_S, HUMAN_WORK_S = 15, 40, 25, 120
AI_COST_PER_MIN, HUMAN_COST_PER_MIN = 0.02, 1.00
HUMAN_ANSWER_P = 0.9

COHORTS = ("order_status", "reschedule", "angry_customer", "sensitive_topic", "noisy_line", "asks_for_human")
CUSTOMERS = {"C-100": "ana.lindqvist@example.com", "C-101": "rafi.okoro@example.com",
             "C-102": "mei.tanaka@example.com", "C-103": "lev.moreau@example.com"}
ORDER_OF = {"C-100": "CP-1001", "C-101": "CP-1002", "C-102": "CP-1003", "C-103": "CP-1004"}


@dataclass
class CallResult:
    cohort: str
    record: CallRecord
    escalated: str | None
    repeats_with_packet: int
    repeats_without_packet: int
    handback_ai_repeats: int | None
    caller_dropped: bool
    events: list[dict] = field(default_factory=list)


def _caller_turns(cohort: str, rng: random.Random, order_id: str, email: str) -> list[tuple[str, float, dict]]:
    """(utterance, stt confidence, slots provided) scripted per cohort."""
    hi = lambda: round(rng.uniform(0.8, 0.98), 2)  # noqa: E731
    if cohort == "order_status":
        return [(f"Hi, where is my order {order_id}?", hi(), {"order_id": order_id}),
                (f"Sure, it's {email}", hi(), {"email": email}), ("Great, thanks", hi(), {})]
    if cohort == "reschedule":
        d = f"2026-11-{rng.randint(10, 20)}"
        return [(f"I need to move the delivery for {order_id}", hi(), {"order_id": order_id}),
                (f"My email is {email}", hi(), {"email": email}),
                (f"Can it come on {d} instead?", hi(), {"new_date": d}), ("Perfect, thank you", hi(), {})]
    if cohort == "angry_customer":
        return [(f"My order {order_id} is late again", hi(), {"order_id": order_id}),
                (f"It's {email}, this is frustrated waste of time", hi(), {"email": email}),
                ("This is ridiculous and unacceptable, worst service ever!", hi(), {})]
    if cohort == "sensitive_topic":
        return [(f"I see a charge for {order_id} I didn't make", hi(), {"order_id": order_id}),
                (f"{email}, and call me at 415-555-0142", hi(), {"email": email}),
                ("I think it's fraud, someone used my card 4111 1111 1111 1111", hi(), {"issue": "possible fraud"})]
    if cohort == "noisy_line":
        return [(f"uh order {order_id} ...", round(rng.uniform(0.3, 0.6), 2), {"order_id": order_id}),
                ("... the ... delivery ...", round(rng.uniform(0.3, 0.6), 2), {})]
    return [(f"Order {order_id}, I want to change the address", hi(), {"order_id": order_id}),
            (f"{email}", hi(), {"email": email}), ("Just let me talk to a real person", hi(), {"issue": "address change"})]


INTENT = {"order_status": "order_status", "reschedule": "reschedule_delivery", "angry_customer": "late_delivery",
          "sensitive_topic": "disputed_charge", "noisy_line": "order_status", "asks_for_human": "change_address"}


def simulate_call(i: int, cohort: str, seed: int = 7) -> CallResult:
    rng = random.Random(f"{seed}-{cohort}-{i}")
    cust = rng.choice(sorted(CUSTOMERS))
    order_id, email = ORDER_OF[cust], CUSTOMERS[cust]
    tools, policy, gate = ToolServer(), EscalationPolicy(), ConfirmationGate()
    sink = QueueSink()
    pub = Publisher(call_id=f"{cohort}-{i:03d}", sinks=[sink])
    ctx = CallContext(call_id=pub.call_id, intent=None)
    ts, ai_turns, ai_actions, human_actions = 0, 0, 0, 0
    reason = None
    refused = False
    for text, conf, slots in _caller_turns(cohort, rng, order_id, email):
        ts += AI_TURN_S * 1000
        ctx.say("caller", text)
        pub.publish("transcript", {"speaker": "caller", "text": text, "confidence": conf}, ts)
        reason = policy.check(text, conf)
        ctx.sentiment = list(policy.trend)
        pub.publish("sentiment", {"score": policy.trend[-1]}, ts)
        if conf >= policy.confidence_floor:
            for k, v in slots.items():
                ctx.provide(k, v)
            if ctx.intent is None:
                ctx.intent = INTENT[cohort]
                pub.publish("intent", {"intent": ctx.intent}, ts)
        if "email" in slots and conf >= policy.confidence_floor and email == CUSTOMERS[cust]:
            ctx.identity_verified, ctx.identity_method, ctx.customer_id = True, "email_on_file", cust
        ai_turns += 1
        if reason:
            break
        if ctx.identity_verified and "order_id" in ctx.entities and not any(
                a["action"] == "lookup_order" for a in ctx.actions_taken):
            res = tools.call_tool("lookup_order", {"order_id": ctx.entities["order_id"]})
            ctx.actions_taken.append({"actor": "ai", "action": "lookup_order", "result": res["status"]})
            ai_actions += 1
            reply = f"Order {res['order_id']} is {res['status']}, due {res['delivery']}."
        elif not ctx.identity_verified:
            reply = "Can you confirm the email on the account?"
        else:
            reply = "Anything else?"
        if "new_date" in slots:
            gate.arm(PendingAction("reschedule", order_id, f"move delivery to {slots['new_date']}"))
            ans = "yes, wait, no" if rng.random() < 0.2 else "yes"
            g = gate.respond(ans, 0.95)
            if g.status != "executed":  # rejected or re-ask: confirm again, cleanly
                gate.arm(PendingAction("reschedule", order_id, f"move delivery to {slots['new_date']}"))
                g = gate.respond("yes", 0.95)
            if g.status == "executed":
                try:
                    res = tools.call_tool("reschedule_delivery", {"order_id": order_id,
                                                                  "new_date": slots["new_date"],
                                                                  "consent_token": tools.mint_consent()})
                except ToolError as exc:
                    refused = True
                    reply = f"I can't move that one: {exc}."
                else:
                    ctx.actions_taken.append({"actor": "ai", "action": "reschedule_delivery",
                                              "result": res["new_date"]})
                    ai_actions += 1
                    reply = f"Done, it will arrive {res['new_date']}."
        ctx.say("ai", reply)
        pub.publish("transcript", {"speaker": "ai", "text": reply, "confidence": 1.0}, ts)

    handle = ai_turns * AI_TURN_S
    cost = handle / 60 * AI_COST_PER_MIN
    rep_with = rep_without = 0
    handback_rep = None
    dropped = False
    if reason is None:
        # A refused side effect (e.g. order already out for delivery) is an honest non-resolution.
        rec = CallRecord(not refused, not refused, handle, 0, round(cost, 4), ai_actions, 0)
        return CallResult(cohort, rec, None, 0, 0, None, False, sink.drain())
    ctx.open_question = {"low_confidence": "Caller could not be understood; intent unconfirmed.",
                         "angry": "Caller upset about a late delivery; wants it fixed.",
                         "sensitive": "Caller reports a charge they did not make.",
                         "requested": "Caller asked for a person."}[reason]
    packet = build_packet(ctx, reason)
    call = Call()
    answered = rng.random() < HUMAN_ANSWER_P
    who = warm_transfer(call, packet, answered)
    dropped = not call.caller_connected
    pub.publish("handoff", {"reason": reason, "to": who}, ts + TRANSFER_S * 1000)
    if who != "human":
        rec = CallRecord(False, False, handle + TRANSFER_S, 1, round(cost, 4), ai_actions, 0)
        return CallResult(cohort, rec, reason, 0, 0, None, dropped, sink.drain())
    human, cold = HumanAgent(), HumanAgent()
    human.take_call(ctx, packet)
    cold.take_call(copy.deepcopy(ctx), None)
    rep_with, rep_without = human.repeats, cold.repeats
    human_actions = 1
    if reason == "sensitive":
        hb = handback(ctx, "Card blocked, dispute opened. Please confirm delivery status.", {"case": "D-77"})
        handback_rep = len(ai_next_questions(ctx, ["identity", "intent", "order_id"]))
        assert hb.escalation_reason == "handback"
        ai_actions += 1  # AI resumes and reads back the status
    handle += TRANSFER_S + len(human.questions) * HUMAN_Q_S + HUMAN_WORK_S
    cost += (len(human.questions) * HUMAN_Q_S + HUMAN_WORK_S) / 60 * HUMAN_COST_PER_MIN
    rec = CallRecord(True, False, handle, 1, round(cost, 4), ai_actions, human_actions)
    return CallResult(cohort, rec, reason, rep_with, rep_without, handback_rep, dropped, sink.drain())


def without_packet_record(r: CallResult) -> CallRecord:
    """Same call, but the human asks the cold-transfer questions (extra time and cost)."""
    extra = r.repeats_without_packet - r.repeats_with_packet
    rec = r.record
    return CallRecord(rec.resolved, rec.contained, rec.handle_time_s + extra * HUMAN_Q_S, rec.transfers,
                      round(rec.cost + extra * HUMAN_Q_S / 60 * HUMAN_COST_PER_MIN, 4),
                      rec.ai_actions, rec.human_actions)


def run(n_per_cohort: int = 50, seed: int = 7) -> list[CallResult]:
    return [simulate_call(i, c, seed) for c in COHORTS for i in range(n_per_cohort)]
