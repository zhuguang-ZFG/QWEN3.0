"""Tests for context_pipeline/event_log.py — event recording."""

import time

from context_pipeline.event_log import EventLog, EventType, Event


class TestEvent:
    def test_age_ms_increases(self):
        e = Event(type=EventType.REQUEST_RECEIVED, timestamp=time.time() - 1)
        assert e.age_ms >= 500


class TestEventLog:
    def test_emit_adds_event(self):
        log = EventLog()
        log.emit(EventType.REQUEST_RECEIVED, request_id="r1")
        assert len(log.events) == 1

    def test_emit_returns_event(self):
        log = EventLog()
        event = log.emit(EventType.BACKEND_SELECTED, backend="groq")
        assert isinstance(event, Event)
        assert event.type == EventType.BACKEND_SELECTED

    def test_filter_by_type(self):
        log = EventLog()
        log.emit(EventType.REQUEST_RECEIVED)
        log.emit(EventType.BACKEND_SELECTED)
        log.emit(EventType.RESPONSE_RECEIVED)
        assert len(log.filter_by_type(EventType.REQUEST_RECEIVED)) == 1

    def test_last_n_events(self):
        log = EventLog()
        for i in range(10):
            log.emit(EventType.REQUEST_RECEIVED)
        assert len(log.last(3)) == 3

    def test_summary(self):
        log = EventLog()
        log.emit(EventType.REQUEST_RECEIVED)
        log.emit(EventType.BACKEND_SELECTED)
        log.emit(EventType.RESPONSE_ERROR, error="timeout")
        s = log.summary()
        assert s["total_events"] == 3
        assert s["error_count"] == 1
        assert s["last_event"] == "response_error"

    def test_clear(self):
        log = EventLog()
        log.emit(EventType.REQUEST_RECEIVED)
        log.clear()
        assert len(log.events) == 0

    def test_max_events_respected(self):
        log = EventLog(max_events=3)
        for i in range(10):
            log.emit(EventType.REQUEST_RECEIVED)
        assert len(log.events) == 3

    def test_summary_empty_log(self):
        log = EventLog()
        s = log.summary()
        assert s["total_events"] == 0
        assert s["last_event"] is None
