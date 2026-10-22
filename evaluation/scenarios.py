"""Scripted call scenarios.

Each scenario is a list of scripted user turns plus the outcome fact the
call must produce. Scenarios are deterministic: same script, same simulated
timeline, same report, every run.
"""
from __future__ import annotations

from dataclasses import dataclass

from voice.pipeline import UserTurn


@dataclass
class Scenario:
    name: str
    description: str
    turns: list[UserTurn]
    expected_fact: str


SCENARIOS: list[Scenario] = [
    Scenario(
        name="clean_order_status",
        description="A clean order-status call: one question, one answer, no drama.",
        turns=[UserTurn(text="Where is my order CP-1001?", confidence=0.96)],
        expected_fact="status_delivered",
    ),
    Scenario(
        name="barge_in_mid_reply",
        description="The caller interrupts the status reply halfway with a follow-up.",
        turns=[
            UserTurn(text="Where is my order CP-1002?", confidence=0.95),
            UserTurn(
                text="When exactly will it arrive?",
                confidence=0.94,
                interrupts="speaking",
                after_ms=300,
            ),
        ],
        expected_fact="status_delivered",
    ),
    Scenario(
        name="noisy_low_confidence",
        description="A bad line: two garbled turns in a row end in a human handoff offer.",
        turns=[
            UserTurn(text="Whrr is my ordr CP one zero zero one", confidence=0.42),
            UserTurn(text="Can you hear me at all now", confidence=0.35),
        ],
        expected_fact="handoff",
    ),
    Scenario(
        name="cancel_with_confirmation",
        description="Cancel an order: the gate asks, the caller says yes, it executes.",
        turns=[
            UserTurn(text="Please cancel my order CP-1001.", confidence=0.95),
            UserTurn(text="Yes, go ahead.", confidence=0.93),
        ],
        expected_fact="cancelled:CP-1001",
    ),
    Scenario(
        name="cancel_rejected_at_confirmation",
        description="Cancel an order, then change of heart at the confirmation: nothing executes.",
        turns=[
            UserTurn(text="Please cancel my order CP-1003.", confidence=0.95),
            UserTurn(text="No, don't cancel it.", confidence=0.94),
        ],
        expected_fact="not_cancelled:CP-1003",
    ),
    Scenario(
        name="barge_in_during_thinking",
        description="The caller corrects themselves while the agent is still thinking.",
        turns=[
            UserTurn(text="Where is my order CP-1001?", confidence=0.95),
            UserTurn(
                text="Sorry, I meant CP-1002.",
                confidence=0.95,
                interrupts="thinking",
                after_ms=60,
            ),
        ],
        expected_fact="status_delivered",
    ),
    Scenario(
        name="handoff_request",
        description="The caller simply asks for a human.",
        turns=[UserTurn(text="I'd like to speak to a real person please.", confidence=0.96)],
        expected_fact="handoff",
    ),
    Scenario(
        name="long_reply_budget_breach",
        description="A request for the full returns policy: the long spoken reply "
        "breaches the end-to-end budget and the ledger flags it.",
        turns=[UserTurn(text="Explain your returns policy in full detail please.", confidence=0.95)],
        expected_fact="policy_delivered",
    ),
]

SCENARIOS_BY_NAME = {s.name: s for s in SCENARIOS}
