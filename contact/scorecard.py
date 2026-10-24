"""AI performance scorecard: outcome, efficiency, cost and automation.

- Outcome: resolution rate and containment rate (resolved without a human).
- Efficiency: average handle time and transfers per call.
- Cost: cost per resolved call. Negative costs are rejected, not averaged in.
- Automation: share of call actions (tool calls) completed by the AI.
A weighted index (0-100) folds the four into one number. Each pillar is
normalised to 0-1 against explicit targets so the index is reproducible.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

DEFAULT_WEIGHTS = {"outcome": 0.4, "efficiency": 0.25, "cost": 0.2, "automation": 0.15}


@dataclass(frozen=True)
class CallRecord:
    resolved: bool
    contained: bool
    handle_time_s: float
    transfers: int
    cost: float
    ai_actions: int
    human_actions: int

    def __post_init__(self) -> None:
        for name in ("handle_time_s", "cost"):
            v = getattr(self, name)
            if not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                raise ValueError(f"{name} must be a finite non-negative number")
        if self.transfers < 0 or self.ai_actions < 0 or self.human_actions < 0:
            raise ValueError("counts must be non-negative")
        if self.contained and self.transfers:
            raise ValueError("a contained call cannot have transfers")


@dataclass(frozen=True)
class Scorecard:
    calls: int
    resolution_rate: float
    containment_rate: float
    avg_handle_time_s: float
    transfers_per_call: float
    cost_per_resolved: float | None
    automation_rate: float
    index: float


def build(records: list[CallRecord], weights: dict[str, float] | None = None, aht_ceiling_s: float = 900.0,
          cost_ceiling: float = 10.0) -> Scorecard:
    if not records:
        raise ValueError("no calls to score")
    w = dict(DEFAULT_WEIGHTS if weights is None else weights)
    if set(w) != set(DEFAULT_WEIGHTS) or any(v < 0 for v in w.values()) or abs(sum(w.values()) - 1) > 1e-9:
        raise ValueError("weights must be the four pillars, non-negative, summing to 1")
    n = len(records)
    resolved = [r for r in records if r.resolved]
    res = len(resolved) / n
    cont = sum(r.contained and r.resolved for r in records) / n
    aht = sum(r.handle_time_s for r in records) / n
    tpc = sum(r.transfers for r in records) / n
    cpr = sum(r.cost for r in records) / len(resolved) if resolved else None
    acts = sum(r.ai_actions + r.human_actions for r in records)
    auto = sum(r.ai_actions for r in records) / acts if acts else 0.0
    outcome = (res + cont) / 2
    efficiency = (max(0.0, 1 - aht / aht_ceiling_s) + max(0.0, 1 - tpc)) / 2
    cost = 0.0 if cpr is None else max(0.0, 1 - cpr / cost_ceiling)
    index = 100 * (w["outcome"] * outcome + w["efficiency"] * efficiency + w["cost"] * cost
                   + w["automation"] * auto)
    return Scorecard(n, res, cont, aht, tpc, cpr, auto, round(index, 1))
