from voice.agent import PendingAction
from voice.fallbacks import ConfirmationGate


def _gate_with_pending() -> ConfirmationGate:
    gate = ConfirmationGate()
    gate.arm(PendingAction(kind="cancel_order", order_id="CP-1001", description="cancel order CP-1001"))
    return gate


class TestConfirmationGate:
    def test_no_pending_returns_none(self):
        assert ConfirmationGate().respond("yes").status == "none"

    def test_yes_executes_and_clears(self):
        gate = _gate_with_pending()
        result = gate.respond("Yes, go ahead.")
        assert result.status == "executed"
        assert result.action.order_id == "CP-1001"
        assert gate.pending is None

    def test_no_rejects_and_clears(self):
        gate = _gate_with_pending()
        result = gate.respond("No, don't cancel it.")
        assert result.status == "rejected"
        assert gate.pending is None

    def test_ambiguous_reprompts_and_stays_armed(self):
        gate = _gate_with_pending()
        result = gate.respond("Hmm, maybe?")
        assert result.status == "reprompt"
        assert gate.pending is not None

    def test_yes_after_reprompt_executes(self):
        gate = _gate_with_pending()
        gate.respond("Hmm, maybe?")
        assert gate.respond("yes").status == "executed"

    def test_repeated_ambiguity_rejects_never_executes(self):
        gate = _gate_with_pending()
        gate.respond("Hmm, maybe?")
        result = gate.respond("Whatever you think is best.")
        assert result.status == "rejected"
        assert gate.pending is None

    def test_plain_yes_and_no_variants(self):
        assert _gate_with_pending().respond("yeah").status == "executed"
        assert _gate_with_pending().respond("nope").status == "rejected"
        assert _gate_with_pending().respond("Yes please.").status == "executed"
