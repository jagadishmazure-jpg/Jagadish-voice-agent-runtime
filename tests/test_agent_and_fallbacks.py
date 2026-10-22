from voice.agent import SupportAgent
from voice.fallbacks import ConfidencePolicy, FallbackTracker


class TestSupportAgent:
    def test_status_intent(self):
        reply = SupportAgent().respond("Where is my order CP-1001?")
        assert "CP-1001" in reply.text
        assert "shipped" in reply.text
        assert reply.fact == "status_delivered"

    def test_unknown_order_id(self):
        reply = SupportAgent().respond("Where is my order CP-9999?")
        assert "could not find" in reply.text

    def test_cancel_returns_pending_action_not_execution(self):
        agent = SupportAgent()
        reply = agent.respond("Please cancel my order CP-1001.")
        assert reply.pending_action is not None
        assert reply.pending_action.order_id == "CP-1001"
        assert agent.cancelled == set()  # nothing executed yet

    def test_execute_cancels_and_status_reflects_it(self):
        agent = SupportAgent()
        action = agent.respond("Cancel order CP-1003.").pending_action
        message = agent.execute(action)
        assert "cancelled" in message
        assert "cancelled" in agent.respond("Where is my order CP-1003?").text

    def test_double_cancel_reported(self):
        agent = SupportAgent()
        agent.execute(agent.respond("Cancel order CP-1001.").pending_action)
        reply = agent.respond("Cancel order CP-1001.")
        assert reply.pending_action is None
        assert "already cancelled" in reply.text

    def test_handoff_intent(self):
        reply = SupportAgent().respond("I'd like to speak to a real person please.")
        assert reply.fact == "handoff"

    def test_bare_order_reference_is_a_status_request(self):
        reply = SupportAgent().respond("Sorry, I meant CP-1002.")
        assert "CP-1002" in reply.text
        assert reply.fact == "status_delivered"

    def test_short_policy_by_default_detailed_on_request(self):
        agent = SupportAgent()
        short = agent.respond("What is your returns policy?")
        detailed = agent.respond("Explain your returns policy in full detail please.")
        assert len(detailed.text) > len(short.text)
        assert detailed.fact == "policy_delivered"

    def test_eta_follow_up_uses_context(self):
        agent = SupportAgent()
        agent.respond("Where is my order CP-1002?")
        reply = agent.respond("When exactly will it arrive?")
        assert "today" in reply.text

    def test_unknown_request_gets_help_text(self):
        reply = SupportAgent().respond("What is the weather like?")
        assert "order status" in reply.text


class TestConfidencePolicy:
    def test_below_threshold_is_low(self):
        assert ConfidencePolicy(0.65).is_low(0.64)

    def test_at_threshold_is_not_low(self):
        assert not ConfidencePolicy(0.65).is_low(0.65)

    def test_high_confidence_is_not_low(self):
        assert not ConfidencePolicy().is_low(0.95)


class TestFallbackTracker:
    def test_first_low_clarifies_second_low_offers_handoff(self):
        tracker = FallbackTracker()
        assert tracker.note_low() == "clarify"
        assert tracker.note_low() == "offer_handoff"

    def test_good_turn_resets_the_streak(self):
        tracker = FallbackTracker()
        tracker.note_low()
        tracker.note_ok()
        assert tracker.note_low() == "clarify"

    def test_custom_handoff_threshold(self):
        tracker = FallbackTracker(handoff_after=3)
        assert tracker.note_low() == "clarify"
        assert tracker.note_low() == "clarify"
        assert tracker.note_low() == "offer_handoff"
