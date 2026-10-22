from voice.turns import EndOfTurnDetector, interrupt_playback


class TestEndOfTurn:
    def setup_method(self):
        self.detector = EndOfTurnDetector()  # 700ms silence / 1200ms long silence

    def test_punctuated_sentence_ends_at_normal_silence(self):
        assert self.detector.decide("Where is my order?", 750)

    def test_short_silence_does_not_end_turn(self):
        assert not self.detector.decide("Where is my order?", 300)

    def test_trailing_conjunction_waits(self):
        assert not self.detector.decide("I want to cancel my order and", 750)

    def test_trailing_filler_waits(self):
        assert not self.detector.decide("I was thinking um", 800)

    def test_long_silence_overrides_incomplete_text(self):
        assert self.detector.decide("I want to cancel my order and", 1300)

    def test_complete_text_without_punctuation(self):
        assert self.detector.is_complete_text("cancel my order please")
        assert self.detector.decide("cancel my order please", 750)

    def test_empty_text_is_not_complete(self):
        assert not self.detector.is_complete_text("   ")


class TestInterruptPlayback:
    def test_no_interruption_needed_when_all_played(self):
        result = interrupt_playback(["a b", "c"], [120, 60], played_ms=500, stop_latency_ms=120)
        assert result.discarded_segments == 0
        assert result.spoken_text == "a b c"

    def test_later_segments_discarded(self):
        result = interrupt_playback(
            ["first part", "second part", "third part"],
            [600, 600, 600],
            played_ms=300,
            stop_latency_ms=120,
        )
        assert result.spoken_text == "first part"
        assert result.discarded_text == "second part third part"
        assert result.discarded_segments == 2

    def test_segment_in_progress_counts_as_heard(self):
        result = interrupt_playback(["only"], [900], played_ms=100, stop_latency_ms=120)
        assert result.spoken_text == "only"
        assert result.discarded_segments == 0

    def test_stop_latency_extends_what_is_heard(self):
        # Heard until 550 + 120 = 670ms: first segment (600ms) done, second in progress.
        result = interrupt_playback(["one", "two", "three"], [600, 600, 600], 550, 120)
        assert result.spoken_text == "one two"
        assert result.discarded_text == "three"

    def test_stopped_within_reports_latency(self):
        result = interrupt_playback(["a"], [100], played_ms=0, stop_latency_ms=120)
        assert result.stopped_within_ms == 120
