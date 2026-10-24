"""When the AI should hand a call to a human, and a tiny sentiment scorer.

Four triggers, checked every caller turn:
- ``requested``: the caller asks for a person.
- ``sensitive``: fraud, bereavement, legal threats, medical or safety topics.
- ``angry``: sentiment below a floor, or falling for three turns in a row
  and already negative.
- ``low_confidence``: two consecutive turns below the STT confidence floor.
The scorer is a small lexicon on purpose; a real deployment swaps in a model
behind the same ``score`` function.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

NEG = {"angry": 2, "furious": 3, "ridiculous": 2, "terrible": 2, "useless": 2, "worst": 3, "unacceptable": 3,
       "frustrated": 2, "annoyed": 1, "late": 1, "again": 1, "never": 1, "wrong": 1, "waste": 2, "sick": 1}
POS = {"thanks": 2, "thank": 2, "great": 2, "perfect": 2, "good": 1, "fine": 1, "appreciate": 2, "helpful": 2}
REQUEST_PATTERNS = (r"\b(speak|talk|transfer|connect)\b.*\b(human|person|agent|someone|representative)\b",
                    r"\b(real|live) (person|human|agent)\b", r"^(agent|representative|operator)[.!]?$")
SENSITIVE_PATTERNS = (r"\bfraud\w*\b", r"\bstolen\b", r"\bunauthori[sz]ed\b", r"\bpassed away\b", r"\bdied\b",
                      r"\blawyer\b", r"\blawsuit\b", r"\bsue\b", r"\bhospital\b", r"\binjur\w+\b")


def score(text: str) -> float:
    """Sentiment in [-1, 1] from a word lexicon (0 when no signal)."""
    words = re.findall(r"[a-z']+", text.lower())
    neg = sum(NEG.get(w, 0) for w in words) + 2 * text.count("!") * any(w in NEG for w in words)
    pos = sum(POS.get(w, 0) for w in words)
    if neg == pos == 0:
        return 0.0
    return round((pos - neg) / max(4, pos + neg), 2)


@dataclass
class EscalationPolicy:
    confidence_floor: float = 0.65
    low_conf_turns: int = 2
    anger_floor: float = -0.6
    trend: list[float] = field(default_factory=list)
    _low: int = 0

    def check(self, text: str, confidence: float = 1.0) -> str | None:
        t = text.lower().strip()
        self.trend.append(score(text))
        if any(re.search(p, t) for p in REQUEST_PATTERNS):
            return "requested"
        if any(re.search(p, t) for p in SENSITIVE_PATTERNS):
            return "sensitive"
        if self.trend[-1] <= self.anger_floor:
            return "angry"
        last3 = self.trend[-3:]
        if len(last3) == 3 and last3[0] > last3[1] > last3[2] and last3[2] < 0:
            return "angry"
        self._low = self._low + 1 if confidence < self.confidence_floor else 0
        if self._low >= self.low_conf_turns:
            return "low_confidence"
        return None
