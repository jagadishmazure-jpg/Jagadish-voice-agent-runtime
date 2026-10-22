"""Fake text-to-speech adapter.

Reply text is chunked into speakable segments (sentence-sized, length
capped) and "played" on the simulated clock. Streaming matters for latency:
the first segment can start playing after a short synthesis delay while the
rest is still being prepared, which is what makes time-to-first-audio much
smaller than the full reply duration.
"""
from __future__ import annotations

import re

from .clock import SimClock

_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")
STOP_LATENCY_MS = 120  # simulated time for playback to halt after a barge-in


def chunk_text(text: str, max_chars: int = 60) -> list[str]:
    """Split reply text into speakable segments.

    Sentences are kept whole when they fit; longer sentences are wrapped at
    word boundaries so no segment exceeds ``max_chars``.
    """
    segments: list[str] = []
    for raw in _SENTENCE_RE.findall(text):
        sentence = raw.strip()
        if not sentence:
            continue
        if len(sentence) <= max_chars:
            segments.append(sentence)
            continue
        current = ""
        for word in sentence.split():
            candidate = f"{current} {word}".strip()
            if len(candidate) > max_chars and current:
                segments.append(current)
                current = word
            else:
                current = candidate
        if current:
            segments.append(current)
    return segments


class FakeTTS:
    def __init__(self, clock: SimClock, synth_ms: int = 130, word_ms: int = 60) -> None:
        self.clock = clock
        self.synth_ms = synth_ms  # time until the first audio segment starts
        self.word_ms = word_ms  # simulated speaking rate

    def durations(self, segments: list[str]) -> list[int]:
        return [max(1, len(seg.split())) * self.word_ms for seg in segments]

    def total_duration(self, segments: list[str]) -> int:
        return sum(self.durations(segments))
