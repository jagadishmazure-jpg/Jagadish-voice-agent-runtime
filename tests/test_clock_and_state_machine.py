import pytest

from voice.clock import SimClock
from voice.pipeline import IllegalTransitionError, State, StateMachine


class TestSimClock:
    def test_starts_at_zero(self):
        assert SimClock().now_ms() == 0

    def test_advance_accumulates(self):
        clock = SimClock()
        clock.advance(150)
        clock.advance(50)
        assert clock.now_ms() == 200

    def test_advance_returns_now(self):
        assert SimClock().advance(75) == 75

    def test_negative_advance_rejected(self):
        with pytest.raises(ValueError):
            SimClock().advance(-1)

    def test_negative_start_rejected(self):
        with pytest.raises(ValueError):
            SimClock(start_ms=-5)


class TestStateMachine:
    def _machine(self):
        return StateMachine(SimClock())

    def test_starts_idle(self):
        assert self._machine().state == State.IDLE

    def test_happy_path_transitions(self):
        sm = self._machine()
        for target in (State.LISTENING, State.THINKING, State.SPEAKING, State.LISTENING, State.ENDED):
            sm.transition(target)
        assert sm.state == State.ENDED
        assert len(sm.history) == 5

    def test_illegal_idle_to_speaking(self):
        with pytest.raises(IllegalTransitionError):
            self._machine().transition(State.SPEAKING)

    def test_illegal_idle_to_thinking(self):
        with pytest.raises(IllegalTransitionError):
            self._machine().transition(State.THINKING)

    def test_ended_is_terminal(self):
        sm = self._machine()
        sm.transition(State.ENDED)
        with pytest.raises(IllegalTransitionError):
            sm.transition(State.LISTENING)

    def test_thinking_to_listening_is_legal_barge_in_cancel(self):
        sm = self._machine()
        sm.transition(State.LISTENING)
        sm.transition(State.THINKING)
        sm.transition(State.LISTENING, "barge_in_cancel")
        assert sm.state == State.LISTENING

    def test_transitions_are_timestamped(self):
        clock = SimClock()
        sm = StateMachine(clock)
        sm.transition(State.LISTENING)
        clock.advance(250)
        sm.transition(State.THINKING)
        assert sm.history[0].at_ms == 0
        assert sm.history[1].at_ms == 250
        assert sm.history[1].from_state == "LISTENING"
        assert sm.history[1].to_state == "THINKING"
