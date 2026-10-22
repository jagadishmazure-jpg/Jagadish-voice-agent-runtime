"""Injectable deterministic clock.

Every stage of the voice pipeline reads time from a SimClock instead of the
wall clock, so a simulated call runs in microseconds of real time while its
*simulated* timeline (partials, silences, playback) is exact and repeatable.
"""
from __future__ import annotations


class SimClock:
    """A manually advanced clock, in milliseconds."""

    def __init__(self, start_ms: int = 0) -> None:
        if start_ms < 0:
            raise ValueError("start_ms must be >= 0")
        self._now = start_ms

    def now_ms(self) -> int:
        return self._now

    def advance(self, ms: int) -> int:
        if ms < 0:
            raise ValueError("cannot advance the clock by a negative amount")
        self._now += ms
        return self._now
