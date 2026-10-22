"""Latency budgets and the ledger that holds the pipeline to them.

Voice feels broken long before it *is* broken: a two-second pause reads as
"the machine didn't hear me". So each stage of a turn gets an explicit
budget, every turn is measured against it, and breaches are flagged with the
stage that blew the budget.

Stage definitions (all measured on the simulated clock):
- ``stt_final``: end-of-turn -> final transcript available.
- ``time_to_first_audio``: end-of-turn -> first TTS audio segment starts.
- ``end_to_end``: end-of-turn -> reply fully spoken.
- ``barge_in_stop``: user starts speaking over the agent -> playback stopped.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


def percentile(values: list[int], p: float) -> int | None:
    """Nearest-rank percentile. Returns None for an empty sample."""
    if not values:
        return None
    if not 0 < p <= 100:
        raise ValueError("p must be in (0, 100]")
    ordered = sorted(values)
    rank = math.ceil(p / 100.0 * len(ordered))
    return ordered[max(0, rank - 1)]


@dataclass(frozen=True)
class LatencyBudgets:
    stt_final_ms: int = 300
    time_to_first_audio_ms: int = 800
    end_to_end_turn_ms: int = 1500
    barge_in_stop_ms: int = 150

    def budget_for(self, stage: str) -> int:
        return {
            "stt_final": self.stt_final_ms,
            "time_to_first_audio": self.time_to_first_audio_ms,
            "end_to_end": self.end_to_end_turn_ms,
            "barge_in_stop": self.barge_in_stop_ms,
        }[stage]


@dataclass
class StageMeasurement:
    turn_index: int
    stage: str
    actual_ms: int
    budget_ms: int

    @property
    def breached(self) -> bool:
        return self.actual_ms > self.budget_ms


@dataclass
class LatencyLedger:
    budgets: LatencyBudgets = field(default_factory=LatencyBudgets)
    entries: list[StageMeasurement] = field(default_factory=list)

    def record(self, turn_index: int, stage: str, actual_ms: int) -> StageMeasurement:
        entry = StageMeasurement(
            turn_index=turn_index,
            stage=stage,
            actual_ms=actual_ms,
            budget_ms=self.budgets.budget_for(stage),
        )
        self.entries.append(entry)
        return entry

    def breaches(self) -> list[StageMeasurement]:
        return [e for e in self.entries if e.breached]

    def values(self, stage: str) -> list[int]:
        return [e.actual_ms for e in self.entries if e.stage == stage]

    def percentile(self, stage: str, p: float) -> int | None:
        return percentile(self.values(stage), p)

    def summary(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for stage in ("stt_final", "time_to_first_audio", "end_to_end", "barge_in_stop"):
            vals = self.values(stage)
            if not vals:
                continue
            out[stage] = {
                "count": len(vals),
                "p50": percentile(vals, 50),
                "p95": percentile(vals, 95),
                "max": max(vals),
                "budget_ms": self.budgets.budget_for(stage),
                "breaches": sum(1 for e in self.entries if e.stage == stage and e.breached),
            }
        return out
