"""Confidence fallbacks and the spoken confirmation gate.

Speech recognition is sometimes just bad — a noisy line, a strong accent, a
kid shouting in the background. A voice agent that guesses anyway will, sooner
or later, confidently do the wrong thing. The fallbacks here follow a simple
escalation: clarify once, then stop guessing and offer a human (or a
keypad/text channel) instead.

The confirmation gate applies the portfolio's confirmation pattern to voice:
side-effecting actions require a named, explicit "yes" in a separate turn.
Anything ambiguous is a re-ask, never a yes.
"""
from __future__ import annotations

from dataclasses import dataclass

from .agent import PendingAction

CLARIFY_TEXT = "Sorry, I did not catch that clearly. Could you say that again for me?"
HANDOFF_OFFER_TEXT = (
    "I am having trouble hearing you clearly. Let me connect you to a human "
    "specialist who can help."
)

_YES = {"yes", "yeah", "yep", "confirm", "correct", "go ahead", "please do", "yes please"}
_NO = {"no", "nope", "don't", "do not", "stop", "never mind", "cancel that"}


class ConfidencePolicy:
    def __init__(self, threshold: float = 0.65) -> None:
        self.threshold = threshold

    def is_low(self, confidence: float) -> bool:
        return confidence < self.threshold


class FallbackTracker:
    """Counts consecutive low-confidence turns and decides the fallback."""

    def __init__(self, handoff_after: int = 2) -> None:
        self.handoff_after = handoff_after
        self.consecutive_low = 0

    def note_low(self) -> str:
        """Record a low-confidence turn; returns 'clarify' or 'offer_handoff'."""
        self.consecutive_low += 1
        if self.consecutive_low >= self.handoff_after:
            return "offer_handoff"
        return "clarify"

    def note_ok(self) -> None:
        self.consecutive_low = 0


@dataclass
class GateResult:
    status: str  # "executed" | "rejected" | "reprompt" | "none"
    action: PendingAction | None = None


class ConfirmationGate:
    """Holds at most one pending side-effecting action awaiting a spoken yes."""

    def __init__(self, max_reprompts: int = 1) -> None:
        self.pending: PendingAction | None = None
        self.max_reprompts = max_reprompts
        self._reprompts = 0

    def arm(self, action: PendingAction) -> None:
        self.pending = action
        self._reprompts = 0

    @staticmethod
    def _classify(text: str) -> str:
        t = " ".join(text.lower().strip(" .!?").split())
        if t in _YES or t.startswith("yes"):
            return "yes"
        if t in _NO or t.startswith("no") or t.startswith("don't") or t.startswith("do not"):
            return "no"
        return "ambiguous"

    def respond(self, text: str) -> GateResult:
        if self.pending is None:
            return GateResult(status="none")
        verdict = self._classify(text)
        if verdict == "yes":
            action, self.pending = self.pending, None
            return GateResult(status="executed", action=action)
        if verdict == "no":
            self.pending = None
            return GateResult(status="rejected")
        # Ambiguous: re-ask once, then reject. Ambiguity is never consent.
        self._reprompts += 1
        if self._reprompts > self.max_reprompts:
            self.pending = None
            return GateResult(status="rejected")
        return GateResult(status="reprompt")
