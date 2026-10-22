"""Regression tests for bugs found in the portfolio-standard review."""
import pytest

from voice.agent import ORDERS, PendingAction, SupportAgent
from voice.fallbacks import ConfirmationGate


def _armed():
    gate = ConfirmationGate()
    gate.arm(PendingAction(kind="cancel_order", order_id="CP-1001", description="cancel"))
    return gate


@pytest.mark.parametrize("text", [
    "Yes, wait, no.", "yesterday I said no", "Yes, but don't cancel it", "yes, actually stop",
])
def test_yes_with_negation_never_executes(text):
    # startswith("yes") used to treat all of these as consent.
    assert _armed().respond(text).status != "executed"


def test_low_confidence_yes_is_not_consent():
    gate = _armed()
    assert gate.respond("yes", confidence=0.30).status == "reprompt"
    assert gate.pending is not None


def test_clear_yes_still_executes():
    assert _armed().respond("Yes please", confidence=0.93).status == "executed"


def test_unknown_order_is_never_cancelled():
    agent = SupportAgent()
    reply = agent.respond("Please cancel my order CP-9999.")
    assert reply.pending_action is None
    assert "CP-9999" not in ORDERS
    agent.execute(PendingAction(kind="cancel_order", order_id="CP-9999", description="x"))
    assert "CP-9999" not in agent.cancelled
