"""Turn detection and barge-in (interruption) handling.

End-of-turn detection decides the user has finished speaking. Real systems
combine silence with linguistic completeness: a long pause after "I want to
cancel my..." is not a finished turn, while a short pause after "...order
CP-1001." usually is. Waiting too long feels sluggish; cutting in feels
rude — and acting on a half-heard request is worse than either.

Barge-in is the other half: when the user starts talking over the agent, the
agent must stop speaking fast, throw away the unheard remainder of its reply,
and treat the interruption as the next input.
"""
from __future__ import annotations

from dataclasses import dataclass

# Words that signal the speaker is mid-thought, not done.
INCOMPLETE_ENDINGS = {
    "and", "or", "but", "the", "a", "an", "to", "of", "for", "with",
    "my", "your", "um", "uh", "so", "because",
}


class EndOfTurnDetector:
    def __init__(self, silence_ms: int = 700, long_silence_ms: int = 1200) -> None:
        self.silence_ms = silence_ms
        self.long_silence_ms = long_silence_ms

    def is_complete_text(self, text: str) -> bool:
        """Does the transcript *look* like a finished utterance?"""
        t = text.strip()
        if not t:
            return False
        if t[-1] in ".?!":
            return True
        last = t.split()[-1].strip(".,!?;:").lower()
        return last not in INCOMPLETE_ENDINGS

    def decide(self, text: str, silence_after_ms: int) -> bool:
        """True when the turn should be treated as finished."""
        if silence_after_ms >= self.long_silence_ms:
            return True  # a very long pause ends the turn regardless
        if silence_after_ms >= self.silence_ms and self.is_complete_text(text):
            return True
        return False


@dataclass
class PlaybackInterruption:
    stopped_within_ms: int
    spoken_text: str
    discarded_text: str
    discarded_segments: int


def interrupt_playback(
    segments: list[str],
    durations: list[int],
    played_ms: int,
    stop_latency_ms: int,
) -> PlaybackInterruption:
    """Work out what was heard and what is thrown away on a barge-in.

    ``played_ms`` is how long playback had been running when the user
    started speaking; playback actually halts ``stop_latency_ms`` later, so
    the segment in progress at that point counts as heard and every later
    segment is discarded.
    """
    heard_until = played_ms + stop_latency_ms
    elapsed = 0
    spoken: list[str] = []
    discarded: list[str] = []
    for seg, dur in zip(segments, durations):
        if elapsed < heard_until:
            spoken.append(seg)
        else:
            discarded.append(seg)
        elapsed += dur
    return PlaybackInterruption(
        stopped_within_ms=stop_latency_ms,
        spoken_text=" ".join(spoken),
        discarded_text=" ".join(discarded),
        discarded_segments=len(discarded),
    )
