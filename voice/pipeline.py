"""The voice pipeline: a call as an explicit state machine.

States: IDLE -> LISTENING -> THINKING -> SPEAKING -> LISTENING ... -> ENDED.
Every transition is timestamped on the simulated clock, so a call report can
show exactly where time went and where a barge-in cut in:

- LISTENING: partial transcripts stream in; end-of-turn detection fires.
- THINKING: the responder works. A barge-in here cancels the in-flight turn
  (marked superseded) — the user correcting themselves should not have to
  wait for an answer to a question they no longer mean.
- SPEAKING: the reply streams out segment by segment. A barge-in here stops
  playback within the stop-latency budget and discards the unheard rest.

Scripted user turns declare interruptions declaratively: a turn with
``interrupts="speaking"`` arrives ``after_ms`` into the previous reply's
playback; ``interrupts="thinking"`` arrives ``after_ms`` into the previous
turn's thinking phase.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field

from .agent import AgentReply, SupportAgent
from .clock import SimClock
from .fallbacks import (
    CLARIFY_TEXT,
    HANDOFF_OFFER_TEXT,
    ConfidencePolicy,
    ConfirmationGate,
    FallbackTracker,
)
from .latency import LatencyBudgets, LatencyLedger
from .stt import FakeSTT
from .tts import STOP_LATENCY_MS, FakeTTS, chunk_text
from .turns import EndOfTurnDetector, interrupt_playback


class State(enum.Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    ENDED = "ENDED"


_ALLOWED: dict[State, set[State]] = {
    State.IDLE: {State.LISTENING, State.ENDED},
    State.LISTENING: {State.THINKING, State.ENDED},
    State.THINKING: {State.SPEAKING, State.LISTENING, State.ENDED},
    State.SPEAKING: {State.LISTENING, State.ENDED},
    State.ENDED: set(),
}


class IllegalTransitionError(Exception):
    """Raised when the pipeline attempts a transition the machine forbids."""


@dataclass
class Transition:
    from_state: str
    to_state: str
    at_ms: int
    reason: str = ""


class StateMachine:
    def __init__(self, clock: SimClock) -> None:
        self.clock = clock
        self.state = State.IDLE
        self.history: list[Transition] = []

    def transition(self, to: State, reason: str = "") -> None:
        if to not in _ALLOWED[self.state]:
            raise IllegalTransitionError(f"{self.state.value} -> {to.value} is not allowed")
        self.history.append(Transition(self.state.value, to.value, self.clock.now_ms(), reason))
        self.state = to


@dataclass
class UserTurn:
    """One scripted user utterance.

    ``interrupts`` marks this utterance as a barge-in over the previous
    agent activity: "speaking" (over playback) or "thinking" (over the
    in-flight turn), starting ``after_ms`` into that activity.
    """

    text: str
    confidence: float = 0.95
    silence_after_ms: int = 800
    interrupts: str | None = None
    after_ms: int = 0


@dataclass
class TurnRecord:
    index: int
    kind: str  # "user" | "confirmation"
    transcript: str
    confidence: float
    reply_text: str = ""
    spoken_text: str = ""
    discarded_text: str = ""
    discarded_segments: int = 0
    superseded: bool = False
    interrupted_speaking: bool = False
    events: list[str] = field(default_factory=list)


@dataclass
class CallReport:
    scenario: str
    turns: list[TurnRecord]
    transitions: list[Transition]
    ledger: LatencyLedger
    facts: set[str]
    events: list[str] = field(default_factory=list)

    def breaches(self):
        return self.ledger.breaches()


class VoicePipeline:
    def __init__(
        self,
        agent: SupportAgent | None = None,
        budgets: LatencyBudgets | None = None,
        think_ms: int = 140,
        clarify_think_ms: int = 60,
    ) -> None:
        self.clock = SimClock()
        self.sm = StateMachine(self.clock)
        self.stt = FakeSTT(self.clock)
        self.tts = FakeTTS(self.clock)
        self.agent = agent if agent is not None else SupportAgent()
        self.detector = EndOfTurnDetector()
        self.policy = ConfidencePolicy()
        self.tracker = FallbackTracker()
        self.gate = ConfirmationGate()
        self.ledger = LatencyLedger(budgets if budgets is not None else LatencyBudgets())
        self.think_ms = think_ms
        self.clarify_think_ms = clarify_think_ms
        self._pending_facts: set[str] = set()

    def _enter_listening(self, reason: str) -> None:
        """Move to LISTENING unless a reply/barge-in already left us there."""
        if self.sm.state != State.LISTENING:
            self.sm.transition(State.LISTENING, reason)

    # -- listening ---------------------------------------------------------
    def _listen(self, ut: UserTurn) -> tuple[str, float, int]:
        """Stream partials, detect end-of-turn, finalise the transcript.

        Returns (text, confidence, end_of_turn_at_ms).
        """
        self.stt.stream(ut.text)
        if not self.detector.decide(ut.text, ut.silence_after_ms):
            # The scripted pause was not enough for this wording (e.g. the
            # utterance trails off mid-phrase): the user eventually stops,
            # and the long-silence rule ends the turn.
            self.clock.advance(self.detector.long_silence_ms - ut.silence_after_ms)
        else:
            self.clock.advance(ut.silence_after_ms)
        end_of_turn_at = self.clock.now_ms()
        transcript = self.stt.finalize(ut.text, ut.confidence)
        return transcript.text, transcript.confidence, end_of_turn_at

    # -- speaking ------------------------------------------------------------
    def _speak(
        self,
        record: TurnRecord,
        text: str,
        end_of_turn_at: int,
        next_ut: UserTurn | None,
    ) -> bool:
        """Speak a reply. Returns True if the next turn was consumed as a barge-in."""
        self.sm.transition(State.SPEAKING, "reply")
        segments = chunk_text(text)
        durations = self.tts.durations(segments)
        self.clock.advance(self.tts.synth_ms)
        ttfa = self.clock.now_ms() - end_of_turn_at
        self.ledger.record(record.index, "time_to_first_audio", ttfa)
        record.reply_text = text

        if next_ut is not None and next_ut.interrupts == "speaking":
            result = interrupt_playback(segments, durations, next_ut.after_ms, STOP_LATENCY_MS)
            self.clock.advance(next_ut.after_ms + STOP_LATENCY_MS)
            self.ledger.record(record.index, "barge_in_stop", result.stopped_within_ms)
            record.spoken_text = result.spoken_text
            record.discarded_text = result.discarded_text
            record.discarded_segments = result.discarded_segments
            record.interrupted_speaking = True
            record.events.append("barge_in_speaking")
            self.sm.transition(State.LISTENING, "barge_in")
            return True

        self.clock.advance(sum(durations))
        record.spoken_text = text
        e2e = self.clock.now_ms() - end_of_turn_at
        self.ledger.record(record.index, "end_to_end", e2e)
        self.sm.transition(State.LISTENING, "reply_complete")
        return False

    # -- one user turn ---------------------------------------------------------
    def _run_turn(self, ut: UserTurn, next_ut: UserTurn | None, index: int) -> tuple[TurnRecord, bool]:
        record = TurnRecord(index=index, kind="user", transcript=ut.text, confidence=ut.confidence)
        self._enter_listening("user_turn")
        text, confidence, end_of_turn_at = self._listen(ut)
        self.ledger.record(index, "stt_final", self.stt.finalize_ms)

        if self.policy.is_low(confidence):
            event = self.tracker.note_low()
            record.events.append(event)
            self.sm.transition(State.THINKING, "fallback")
            self.clock.advance(self.clarify_think_ms)
            reply = HANDOFF_OFFER_TEXT if event == "offer_handoff" else CLARIFY_TEXT
            if event == "offer_handoff":
                # The offer itself is the outcome of this call.
                self._pending_facts = {"handoff"}
            consumed = self._speak(record, reply, end_of_turn_at, next_ut)
            return record, consumed

        self.tracker.note_ok()
        self.sm.transition(State.THINKING, "agent")

        if next_ut is not None and next_ut.interrupts == "thinking":
            self.clock.advance(min(next_ut.after_ms, self.think_ms))
            record.superseded = True
            record.events.append("superseded_by_barge_in")
            self.sm.transition(State.LISTENING, "barge_in_cancel")
            return record, True

        self.clock.advance(self.think_ms)
        reply = self.agent.respond(text)
        return self._deliver(record, reply, end_of_turn_at, next_ut)

    def _deliver(
        self,
        record: TurnRecord,
        reply: AgentReply,
        end_of_turn_at: int,
        next_ut: UserTurn | None,
    ) -> tuple[TurnRecord, bool]:
        consumed = self._speak(record, reply.text, end_of_turn_at, next_ut)
        if reply.pending_action is not None:
            self.gate.arm(reply.pending_action)
            record.events.append("confirmation_requested")
        if reply.fact and record.spoken_text:
            self._pending_facts = {reply.fact}
        return record, consumed

    # -- one confirmation turn -------------------------------------------------
    def _run_confirmation_turn(
        self, ut: UserTurn, next_ut: UserTurn | None, index: int
    ) -> tuple[TurnRecord, bool]:
        record = TurnRecord(index=index, kind="confirmation", transcript=ut.text, confidence=ut.confidence)
        self._enter_listening("confirmation_turn")
        text, confidence, end_of_turn_at = self._listen(ut)
        self.ledger.record(index, "stt_final", self.stt.finalize_ms)
        self.sm.transition(State.THINKING, "gate")
        self.clock.advance(self.clarify_think_ms)

        pending = self.gate.pending
        result = self.gate.respond(text)
        record.events.append(f"confirmation_{result.status}")
        if result.status == "executed" and result.action is not None:
            message = self.agent.execute(result.action)
            self._pending_facts = {f"cancelled:{result.action.order_id}"}
        elif result.status == "rejected":
            message = "No problem, I will leave everything as it is."
            if pending is not None:
                self._pending_facts = {f"not_cancelled:{pending.order_id}"}
        else:  # reprompt
            message = "Sorry, was that a yes or a no?"
        consumed = self._speak(record, message, end_of_turn_at, next_ut)
        return record, consumed

    # -- whole call --------------------------------------------------------------
    def run_call(self, turns: list[UserTurn], scenario: str = "") -> CallReport:
        facts: set[str] = set()
        records: list[TurnRecord] = []
        events: list[str] = []
        idx = 0
        carry: UserTurn | None = None
        turn_index = 0
        while idx < len(turns) or carry is not None:
            if carry is not None:
                ut, carry = carry, None
            else:
                ut = turns[idx]
                idx += 1
            next_ut = turns[idx] if idx < len(turns) else None
            self._pending_facts = set()
            if self.gate.pending is not None:
                record, consumed = self._run_confirmation_turn(ut, next_ut, turn_index)
            else:
                record, consumed = self._run_turn(ut, next_ut, turn_index)
            facts |= self._pending_facts
            records.append(record)
            turn_index += 1
            if consumed and next_ut is not None:
                carry = next_ut
                idx += 1
        if self.sm.state == State.LISTENING:
            self.sm.transition(State.ENDED, "call_complete")
        if self.gate.pending is not None:
            events.append("confirmation_left_pending")
        return CallReport(
            scenario=scenario,
            turns=records,
            transitions=list(self.sm.history),
            ledger=self.ledger,
            facts=facts,
            events=events,
        )
