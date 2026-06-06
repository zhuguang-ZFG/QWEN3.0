"""Tests for M9: Streaming event protocol — SSE format, event types, serialization."""
import json

from streaming_events import (
    StreamEvent,
    StreamEventType,
    audit_ref_event,
    done_event,
    error_event,
    format_sse_done,
    is_valid_event_name,
    token_event,
    tool_delta_event,
    tool_end_event,
    tool_start_event,
    warning_event,
)

# ── StreamEventType enum ─────────────────────────────────────────────────────

def test_all_event_types_defined():
    assert StreamEventType.TOKEN == "token"
    assert StreamEventType.TOOL_START == "tool_start"
    assert StreamEventType.TOOL_DELTA == "tool_delta"
    assert StreamEventType.TOOL_END == "tool_end"
    assert StreamEventType.WARNING == "warning"
    assert StreamEventType.ERROR == "error"
    assert StreamEventType.DONE == "done"
    assert StreamEventType.AUDIT_REF == "audit_ref"
    assert len(StreamEventType) == 8  # exactly 8 types, no drift


def test_is_valid_event_name():
    assert is_valid_event_name("token") is True
    assert is_valid_event_name("done") is True
    assert is_valid_event_name("bogus") is False


# ── token_event ──────────────────────────────────────────────────────────────

def test_token_event_sse():
    e = token_event("hello world")
    sse = e.to_sse()
    assert "data: " in sse
    parsed = json.loads(sse[6:].strip())
    assert parsed["event"] == "token"
    assert parsed["data"]["text"] == "hello world"


def test_token_event_openai_format():
    e = token_event("hi there")
    chunk = e.to_openai_chunk(model="lima-1.3")
    assert "data: " in chunk
    parsed = json.loads(chunk[6:].strip())
    assert parsed["choices"][0]["delta"]["content"] == "hi there"
    assert parsed["model"] == "lima-1.3"


# ── tool events ──────────────────────────────────────────────────────────────

def test_tool_start_event():
    e = tool_start_event("read_file", tool_id="t1", input_schema={"path": "str"})
    assert e.event == StreamEventType.TOOL_START
    assert e.data["tool_name"] == "read_file"
    assert e.data["tool_id"] == "t1"


def test_tool_delta_event():
    e = tool_delta_event("t1", '{"line":')
    assert e.data["delta"] == '{"line":'


def test_tool_end_event():
    e = tool_end_event("t1", output='{"line": "hello"}', ok=True)
    assert e.data["ok"] is True
    assert e.data["output"] == '{"line": "hello"}'


def test_tool_end_event_redacts_secret_output():
    e = tool_end_event(
        "t1", output="token = Bearer abcdefghijklmnopqrstuvwxyz123456", ok=False
    )
    sse = e.to_sse()
    assert "Bearer abcdefghijklmnopqrstuvwxyz123456" not in sse
    assert "[REDACTED]" in sse


def test_tool_start_event_redacts_sensitive_input_keys():
    e = tool_start_event(
        "call_api",
        tool_id="t1",
        input_schema={"api_key": "sk-abcdefghijklmnopqrstuvwxyz123456", "path": "x"},
    )
    sse = e.to_sse()
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in sse
    assert '"api_key": "[REDACTED]"' in sse


def test_tool_lifecycle_sse_format():
    """Full tool call lifecycle should produce valid SSE."""
    events = [
        tool_start_event("search", tool_id="abc"),
        tool_delta_event("abc", "found 3"),
        tool_delta_event("abc", " results"),
        tool_end_event("abc", output="found 3 results", ok=True),
    ]
    for e in events:
        sse = e.to_sse()
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")
        parsed = json.loads(sse[6:].strip())
        assert "event" in parsed


# ── warning / error ─────────────────────────────────────────────────────────

def test_warning_event():
    e = warning_event("backend slow", code="latency_high")
    assert e.event == StreamEventType.WARNING
    assert "backend slow" in e.data["message"]
    sse = e.to_sse()
    assert "warning" in sse


def test_error_event():
    e = error_event("connection refused", code="network_error", recoverable=True)
    assert e.data["recoverable"] is True
    sse = e.to_sse()
    assert "error" in sse
    assert "connection refused" in sse


def test_error_event_non_recoverable():
    e = error_event("auth failed", code="auth_expired", recoverable=False)
    assert e.data["recoverable"] is False


def test_error_event_redacts_secret_message():
    e = error_event(
        "failed with sk-abcdefghijklmnopqrstuvwxyz123456",
        code="auth_expired",
        recoverable=False,
    )
    sse = e.to_sse()
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in sse
    assert "[REDACTED]" in sse


# ── done / audit_ref ────────────────────────────────────────────────────────

def test_done_event():
    e = done_event(reason="stop")
    assert e.event == StreamEventType.DONE
    assert e.data["reason"] == "stop"


def test_done_event_openai_format():
    e = done_event()
    chunk = e.to_openai_chunk(model="lima")
    parsed = json.loads(chunk[6:].strip())
    assert parsed["choices"][0]["finish_reason"] == "stop"


def test_audit_ref_event():
    e = audit_ref_event("audit-abc-123")
    assert e.event == StreamEventType.AUDIT_REF
    assert e.data["audit_id"] == "audit-abc-123"


def test_format_sse_done():
    assert format_sse_done() == "data: [DONE]\n\n"


# ── StreamEvent defaults ────────────────────────────────────────────────────

def test_stream_event_defaults():
    e = StreamEvent(event=StreamEventType.TOKEN)
    assert len(e.id) == 12
    assert e.timestamp > 0
    assert e.data == {}


def test_stream_event_accepts_string_event_name():
    e = StreamEvent(event="token", data={"text": "hello"})
    assert e.event == StreamEventType.TOKEN
    assert json.loads(e.to_sse()[6:].strip())["event"] == "token"


def test_token_event_preserves_text_payload():
    e = token_event("example token text with sk-demo-placeholder")
    assert e.data["text"] == "example token text with sk-demo-placeholder"


def test_stream_event_id_unique():
    e1 = token_event("a")
    e2 = token_event("b")
    assert e1.id != e2.id


# ── No sensitive fields in events ────────────────────────────────────────────

def test_stream_event_no_sensitive_fields():
    e = token_event("test")
    d = e.to_sse()
    assert "api_key" not in d
    assert "token_value" not in d
    assert "cookie" not in d


# ── Chunk sequence produces valid SSE stream ─────────────────────────────────

def test_full_chunk_sequence():
    """A complete interaction produces a well-formed SSE sequence."""
    chunks = [
        token_event("Hello"),
        token_event(" world"),
        token_event("!"),
        done_event(),
    ]
    output = "".join(c.to_sse() for c in chunks) + format_sse_done()
    lines = output.strip().split("\n")
    assert all(line.startswith("data: ") for line in lines if line)
    # Last non-empty line should be [DONE]
    assert "[DONE]" in lines[-1]
