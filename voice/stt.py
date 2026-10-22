"""Fake streaming speech-to-text adapter.

A real streaming STT service emits partial transcripts as the user speaks,
then a final transcript (with a confidence score) shortly after the user
stops. This fake reproduces that contract deterministically: partials are
progressive word prefixes of the scripted final text, and finalisation costs
a fixed, configurable simulated latency.
"""
from __future__ import annotations

from dataclasses import dataclass

from .clock import SimClock


@dataclass
class Transcript:
    text: str
    confidence: float
    finalized_at_ms: int
    latency_ms: int  # end-of-turn -> final transcript


class FakeSTT:
    def __init__(self, clock: SimClock, finalize_ms: int = 160, partial_gap_ms: int = 100) -> None:
        self.clock = clock
        self.finalize_ms = finalize_ms
        self.partial_gap_ms = partial_gap_ms

    def partials_for(self, text: str) -> list[str]:
        """Progressive word-prefix partials for a scripted utterance."""
        words = text.split()
        return [" ".join(words[: i + 1]) for i in range(len(words))]

    def stream(self, text: str) -> list[str]:
        """Play the partials, advancing the clock between them."""
        partials = self.partials_for(text)
        for _ in partials[1:]:
            self.clock.advance(self.partial_gap_ms)
        return partials

    def finalize(self, text: str, confidence: float) -> Transcript:
        self.clock.advance(self.finalize_ms)
        return Transcript(
            text=text,
            confidence=confidence,
            finalized_at_ms=self.clock.now_ms(),
            latency_ms=self.finalize_ms,
        )
