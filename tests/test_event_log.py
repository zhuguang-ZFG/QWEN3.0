from context_pipeline.event_log import (
    EventLog,
    EventType,
    get_request_log,
    new_request_log,
)


def test_emit_records_event():
    log = EventLog()
    event = log.emit(EventType.REQUEST_RECEIVED, path="/v1/chat/completions")
    assert event.type == EventType.REQUEST_RECEIVED
    assert event.data["path"] == "/v1/chat/completions"
    assert event.timestamp > 0


def test_events_property():
    log = EventLog()
    log.emit(EventType.IDE_DETECTED, ide="opencode")
    log.emit(EventType.SCENARIO_CLASSIFIED, scenario="coding")
    assert len(log.events) == 2


def test_filter_by_type():
    log = EventLog()
    log.emit(EventType.REQUEST_RECEIVED)
    log.emit(EventType.RESPONSE_ERROR, error="timeout")
    log.emit(EventType.RESPONSE_ERROR, error="502")
    errors = log.filter_by_type(EventType.RESPONSE_ERROR)
    assert len(errors) == 2


def test_last_n():
    log = EventLog()
    for i in range(10):
        log.emit(EventType.REQUEST_RECEIVED, idx=i)
    last3 = log.last(3)
    assert len(last3) == 3
    assert last3[0].data["idx"] == 7


def test_summary():
    log = EventLog()
    log.emit(EventType.REQUEST_RECEIVED)
    log.emit(EventType.IDE_DETECTED, ide="opencode")
    log.emit(EventType.BACKEND_SELECTED, backend="scnet_qwen72b")
    log.emit(EventType.RESPONSE_ERROR, error="timeout")
    log.emit(EventType.FALLBACK_TRIGGERED, new_backend="groq_llama70b")

    s = log.summary()
    assert s["total_events"] == 5
    assert s["error_count"] == 1
    assert s["fallback_count"] == 1
    assert s["last_event"] == "fallback_triggered"


def test_max_events_cap():
    log = EventLog(max_events=5)
    for i in range(10):
        log.emit(EventType.REQUEST_RECEIVED, idx=i)
    assert len(log.events) == 5
    assert log.events[0].data["idx"] == 5


def test_clear():
    log = EventLog()
    log.emit(EventType.REQUEST_RECEIVED)
    log.clear()
    assert len(log.events) == 0


def test_new_request_log_creates_fresh():
    log1 = new_request_log()
    log1.emit(EventType.REQUEST_RECEIVED)
    log2 = new_request_log()
    assert len(log2.events) == 0
    assert get_request_log() is log2
