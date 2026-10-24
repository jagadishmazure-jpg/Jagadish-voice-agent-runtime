"""Handoff packet, the simulated human agent, handback and warm transfer.

The packet carries everything the caller has already told the AI so the
human never asks again: verified identity, intent, entities, actions already
taken, the open question, the sentiment trend and a PII-masked transcript
summary. ``HumanAgent`` stands in for the person picking up: it asks only for
slots it still needs, and every question about something the caller already
said counts as a repeat question.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .pii import mask, mask_obj

PACKET_FIELDS = ("call_id", "escalation_reason", "identity", "intent", "entities", "actions_taken",
                 "open_question", "sentiment_trend", "transcript_summary")


@dataclass
class CallContext:
    """What the conversation has established so far (owned by the runtime)."""

    call_id: str
    identity_verified: bool = False
    identity_method: str | None = None
    customer_id: str | None = None
    intent: str | None = None
    entities: dict[str, str] = field(default_factory=dict)
    actions_taken: list[dict[str, Any]] = field(default_factory=list)
    open_question: str | None = None
    sentiment: list[float] = field(default_factory=list)
    transcript: list[tuple[str, str]] = field(default_factory=list)
    caller_said: set[str] = field(default_factory=set)  # slots the caller has already provided

    def say(self, speaker: str, text: str) -> None:
        self.transcript.append((speaker, text))

    def provide(self, slot: str, value: str) -> None:
        self.entities[slot] = value
        self.caller_said.add(slot)


@dataclass
class HandoffPacket:
    call_id: str
    escalation_reason: str
    identity: dict[str, Any]
    intent: str | None
    entities: dict[str, str]
    actions_taken: list[dict[str, Any]]
    open_question: str | None
    sentiment_trend: list[float]
    transcript_summary: str

    def to_dict(self) -> dict[str, Any]:
        return mask_obj(asdict(self))


def summarise(transcript: list[tuple[str, str]], max_turns: int = 6) -> str:
    """Short, masked summary: the last few caller/AI turns, one line each."""
    lines = [f"{who}: {mask(text)}" for who, text in transcript[-max_turns:]]
    return " | ".join(lines)


def build_packet(ctx: CallContext, reason: str) -> HandoffPacket:
    entities = {k: mask(v) for k, v in ctx.entities.items()}
    return HandoffPacket(
        call_id=ctx.call_id,
        escalation_reason=reason,
        identity={"verified": ctx.identity_verified, "method": ctx.identity_method, "customer_id": ctx.customer_id},
        intent=ctx.intent,
        entities=entities,
        actions_taken=mask_obj([dict(a) for a in ctx.actions_taken]),
        open_question=mask(ctx.open_question) if ctx.open_question else None,
        sentiment_trend=list(ctx.sentiment),
        transcript_summary=summarise(ctx.transcript),
    )


QUESTION_FOR = {
    "identity": "Before we start, can I verify your account?",
    "intent": "How can I help you today?",
    "order_id": "What is the order number?",
    "new_date": "Which date would you like instead?",
    "email": "What email is on the account?",
    "actions_taken": "Has anything been changed on the order so far?",
    "issue": "Can you tell me what happened?",
}


@dataclass
class HumanAgent:
    """Simulated human specialist. Asks only for what it does not know."""

    questions: list[str] = field(default_factory=list)
    repeats: int = 0

    @staticmethod
    def needs(ctx: CallContext) -> list[str]:
        need = ["identity", "intent"]
        need += [s for s in ("order_id", "new_date", "email", "issue") if s in ctx.caller_said]
        if ctx.actions_taken:
            need.append("actions_taken")
        return need

    def take_call(self, ctx: CallContext, packet: HandoffPacket | None) -> CallContext:
        known: set[str] = set()
        if packet is not None:
            if packet.identity.get("verified"):
                known.add("identity")
            if packet.intent:
                known.add("intent")
            known |= set(packet.entities)
            if packet.actions_taken:
                known.add("actions_taken")
        for slot in self.needs(ctx):
            if slot in known:
                continue
            self.questions.append(QUESTION_FOR[slot])
            already_said = slot in ctx.caller_said or (slot == "identity" and ctx.identity_verified) \
                or (slot == "intent" and ctx.intent is not None) or (slot == "actions_taken" and ctx.actions_taken)
            if already_said:
                self.repeats += 1
        return ctx


def handback(ctx: CallContext, human_note: str, resolved_slots: dict[str, str]) -> HandoffPacket:
    """Human returns the call to the AI. The AI resumes from the same context."""
    for k, v in resolved_slots.items():
        ctx.provide(k, v)
    ctx.actions_taken.append({"actor": "human", "action": "note", "detail": mask(human_note)})
    ctx.open_question = None
    return build_packet(ctx, "handback")


def ai_next_questions(ctx: CallContext, goal_slots: list[str]) -> list[str]:
    """What the AI would still ask after a handback: only genuinely missing slots."""
    asks = []
    for slot in goal_slots:
        if slot == "identity" and ctx.identity_verified:
            continue
        if slot in ctx.entities or (slot == "intent" and ctx.intent):
            continue
        asks.append(QUESTION_FOR[slot])
    return asks


@dataclass
class Call:
    """Call legs and an event timeline. ``caller_connected`` must never go False mid-transfer."""

    legs: set[str] = field(default_factory=lambda: {"caller", "ai"})
    timeline: list[str] = field(default_factory=list)
    dropped: bool = False

    @property
    def caller_connected(self) -> bool:
        return "caller" in self.legs and not self.dropped


def warm_transfer(call: Call, packet: HandoffPacket, human_answers: bool) -> str:
    """Conference the human in before the AI leaves. Returns 'human', or 'ai' if nobody answered."""
    call.timeline.append("caller_on_hold_with_message")
    call.timeline.append("dial_human")
    if not human_answers:
        call.timeline.append("no_answer_return_to_ai")
        call.timeline.append("offer_callback")
        return "ai"
    call.legs.add("human")
    call.timeline.append("conference_3_way")
    call.timeline.append(f"packet_delivered:{packet.call_id}")
    call.timeline.append("ai_introduces_human")
    call.legs.discard("ai")
    call.timeline.append("ai_leg_left")
    return "human"


def blind_transfer(call: Call, human_answers: bool) -> str:
    """Baseline for comparison: AI leg released before anyone answers."""
    call.legs.discard("ai")
    call.timeline.append("ai_leg_left")
    if not human_answers:
        call.dropped = True
        call.timeline.append("call_dropped")
        return "dropped"
    call.legs.add("human")
    return "human"


__all__ = ["PACKET_FIELDS", "CallContext", "HandoffPacket", "build_packet", "HumanAgent", "handback",
           "ai_next_questions", "Call", "warm_transfer", "blind_transfer", "summarise"]
