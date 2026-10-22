from evaluation.scenarios import SCENARIOS_BY_NAME as S
from voice.pipeline import UserTurn, VoicePipeline
from voice.session import run_scenario


class TestCleanCall:
    def test_status_call_completes_within_budgets(self):
        report = run_scenario(S["clean_order_status"])
        assert "status_delivered" in report.facts
        assert report.breaches() == []
        ledger = report.ledger.summary()
        assert ledger["stt_final"]["max"] == 160
        assert ledger["time_to_first_audio"]["max"] == 430  # 160 STT + 140 think + 130 synth

    def test_transitions_walk_the_state_machine(self):
        report = run_scenario(S["clean_order_status"])
        path = [(t.from_state, t.to_state) for t in report.transitions]
        assert path[0] == ("IDLE", "LISTENING")
        assert ("LISTENING", "THINKING") in path
        assert ("THINKING", "SPEAKING") in path
        assert path[-1] == ("LISTENING", "ENDED")


class TestBargeInSpeaking:
    def test_remainder_of_reply_is_discarded(self):
        report = run_scenario(S["barge_in_mid_reply"])
        first = report.turns[0]
        assert first.interrupted_speaking
        assert first.discarded_segments == 1
        assert "delivery and should arrive today." in first.discarded_text
        assert first.spoken_text  # the first segment was heard

    def test_stop_latency_within_budget(self):
        report = run_scenario(S["barge_in_mid_reply"])
        stops = report.ledger.values("barge_in_stop")
        assert stops == [120]
        assert stops[0] <= report.ledger.budgets.barge_in_stop_ms

    def test_interrupting_utterance_becomes_next_turn(self):
        report = run_scenario(S["barge_in_mid_reply"])
        assert len(report.turns) == 2
        assert report.turns[1].transcript == "When exactly will it arrive?"
        assert "8 PM" in report.turns[1].reply_text
        assert "status_delivered" in report.facts


class TestBargeInThinking:
    def test_in_flight_turn_is_superseded(self):
        report = run_scenario(S["barge_in_during_thinking"])
        first, second = report.turns
        assert first.superseded
        assert first.reply_text == ""  # it never got to speak
        assert "CP-1002" in second.reply_text
        assert "status_delivered" in report.facts

    def test_superseded_turn_records_no_audio_latency(self):
        report = run_scenario(S["barge_in_during_thinking"])
        ttfa_turns = {
            e.turn_index for e in report.ledger.entries if e.stage == "time_to_first_audio"
        }
        assert 0 not in ttfa_turns  # turn 0 was cancelled before speaking
        assert 1 in ttfa_turns


class TestConfirmationFlow:
    def test_cancel_executes_only_after_yes(self):
        report = run_scenario(S["cancel_with_confirmation"])
        assert "cancelled:CP-1001" in report.facts
        assert report.turns[0].events == ["confirmation_requested"]
        assert report.turns[1].kind == "confirmation"
        assert report.turns[1].events == ["confirmation_executed"]

    def test_cancel_rejected_on_no(self):
        report = run_scenario(S["cancel_rejected_at_confirmation"])
        assert "not_cancelled:CP-1003" in report.facts
        assert "cancelled:CP-1003" not in report.facts

    def test_action_never_executes_without_confirmation_turn(self):
        pipeline = VoicePipeline()
        report = pipeline.run_call([UserTurn(text="Please cancel my order CP-1001.", confidence=0.95)])
        assert pipeline.agent.cancelled == set()
        assert "confirmation_left_pending" in report.events


class TestConfidenceFallbacksInPipeline:
    def test_first_low_confidence_clarifies(self):
        pipeline = VoicePipeline()
        report = pipeline.run_call([UserTurn(text="whrr is my ordr", confidence=0.4)])
        assert report.turns[0].events == ["clarify"]
        assert "did not catch" in report.turns[0].reply_text

    def test_two_low_confidence_turns_offer_handoff(self):
        report = run_scenario(S["noisy_low_confidence"])
        assert report.turns[0].events == ["clarify"]
        assert report.turns[1].events == ["offer_handoff"]
        assert "handoff" in report.facts

    def test_good_turn_after_clarify_recovers(self):
        pipeline = VoicePipeline()
        report = pipeline.run_call(
            [
                UserTurn(text="whrr is my ordr", confidence=0.4),
                UserTurn(text="Where is my order CP-1001?", confidence=0.95),
            ]
        )
        assert "status_delivered" in report.facts


class TestLongReplyBreach:
    def test_long_reply_breaches_only_end_to_end(self):
        report = run_scenario(S["long_reply_budget_breach"])
        breaches = report.breaches()
        assert len(breaches) == 1
        assert breaches[0].stage == "end_to_end"
        assert breaches[0].actual_ms > breaches[0].budget_ms
        assert "policy_delivered" in report.facts  # slow, but still completed
