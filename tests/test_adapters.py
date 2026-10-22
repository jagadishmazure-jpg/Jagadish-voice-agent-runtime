from voice.clock import SimClock
from voice.stt import FakeSTT
from voice.tts import FakeTTS, chunk_text


class TestFakeSTT:
    def test_partials_are_progressive_prefixes(self):
        stt = FakeSTT(SimClock())
        assert stt.partials_for("where is my order") == [
            "where",
            "where is",
            "where is my",
            "where is my order",
        ]

    def test_stream_advances_clock_between_partials(self):
        clock = SimClock()
        stt = FakeSTT(clock, partial_gap_ms=100)
        stt.stream("one two three four")
        assert clock.now_ms() == 300  # 3 gaps between 4 partials

    def test_finalize_latency_and_confidence(self):
        clock = SimClock()
        stt = FakeSTT(clock, finalize_ms=160)
        transcript = stt.finalize("hello", 0.42)
        assert transcript.latency_ms == 160
        assert transcript.confidence == 0.42
        assert transcript.finalized_at_ms == 160


class TestChunkText:
    def test_sentences_kept_whole_when_they_fit(self):
        assert chunk_text("One sentence. Another one here.") == [
            "One sentence.",
            "Another one here.",
        ]

    def test_short_text_single_segment(self):
        assert chunk_text("Hello there.") == ["Hello there."]

    def test_long_sentence_wrapped_at_word_boundaries(self):
        text = "word " * 30 + "end."
        segments = chunk_text(text.strip(), max_chars=60)
        assert len(segments) > 1
        assert all(len(s) <= 60 for s in segments)

    def test_empty_text_no_segments(self):
        assert chunk_text("") == []


class TestFakeTTS:
    def test_durations_scale_with_words(self):
        tts = FakeTTS(SimClock(), word_ms=60)
        assert tts.durations(["one two three", "four"]) == [180, 60]

    def test_total_duration(self):
        tts = FakeTTS(SimClock(), word_ms=50)
        assert tts.total_duration(["one two", "three four five"]) == 250
