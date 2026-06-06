"""OpenCode streaming enhancement tests.

Validates the __LIMA_META__ usage extraction pipeline, reasoning_content
extraction, and OpenAI-compatible usage chunk generation.
"""

import json
import time

import pytest

# ─── Test 1: extract_sse_usage extracts usage from OpenAI SSE chunk ──────────

def test_extract_sse_usage_valid():
    """extract_sse_usage() extracts usage from OpenAI-format SSE chunk."""
    from http_response import extract_sse_usage
    
    # Standard OpenAI usage chunk
    chunk = json.dumps({
        "id": "chatcmpl-test123",
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
    })
    result = extract_sse_usage(chunk)
    assert result is not None
    assert result["prompt_tokens"] == 100
    assert result["completion_tokens"] == 50
    assert result["total_tokens"] == 150


def test_extract_sse_usage_missing():
    """extract_sse_usage() returns None when no usage field."""
    from http_response import extract_sse_usage
    
    # Regular content chunk without usage
    chunk = json.dumps({
        "id": "chatcmpl-test123",
        "choices": [{"index": 0, "delta": {"content": "hello"}, "finish_reason": None}]
    })
    result = extract_sse_usage(chunk)
    assert result is None


def test_extract_sse_usage_invalid_json():
    """extract_sse_usage() returns None on invalid JSON."""
    from http_response import extract_sse_usage
    
    result = extract_sse_usage("not valid json")
    assert result is None


def test_extract_sse_usage_no_prompt_tokens():
    """extract_sse_usage() returns None when usage lacks prompt_tokens."""
    from http_response import extract_sse_usage
    
    chunk = json.dumps({
        "usage": {"completion_tokens": 50}  # Missing prompt_tokens
    })
    result = extract_sse_usage(chunk)
    assert result is None


# ─── Test 2: extract_sse_reasoning extracts reasoning_content ────────────────

def test_extract_sse_reasoning_valid():
    """extract_sse_reasoning() extracts reasoning_content from delta."""
    from http_response import extract_sse_reasoning
    
    chunk = json.dumps({
        "choices": [{
            "index": 0,
            "delta": {
                "reasoning_content": "Let me think about this...",
                "content": ""
            }
        }]
    })
    result = extract_sse_reasoning(chunk, "openai")
    assert result == "Let me think about this..."


def test_extract_sse_reasoning_empty():
    """extract_sse_reasoning() returns empty string when no reasoning_content."""
    from http_response import extract_sse_reasoning
    
    chunk = json.dumps({
        "choices": [{
            "index": 0,
            "delta": {"content": "Hello world"}
        }]
    })
    result = extract_sse_reasoning(chunk, "openai")
    assert result == ""


def test_extract_sse_reasoning_non_openai():
    """extract_sse_reasoning() returns empty for non-openai format."""
    from http_response import extract_sse_reasoning
    
    chunk = json.dumps({
        "choices": [{
            "index": 0,
            "delta": {"reasoning_content": "thinking..."}
        }]
    })
    result = extract_sse_reasoning(chunk, "anthropic")
    assert result == ""


# ─── Test 3: build_usage_chunk generates OpenAI-compatible usage SSE ─────────

def test_build_usage_chunk_format():
    """build_usage_chunk() generates valid OpenAI-compatible SSE."""
    from streaming_events import build_usage_chunk
    
    usage = {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150
    }
    result = build_usage_chunk("test123", usage, model="lima-1.3")
    
    # Should be SSE format
    assert result.startswith("data: ")
    assert result.endswith("\n\n")
    
    # Parse JSON payload
    payload = json.loads(result[6:].strip())
    
    # Verify OpenAI chunk structure
    assert payload["id"] == "chatcmpl-test123"
    assert payload["object"] == "chat.completion.chunk"
    assert payload["model"] == "lima-1.3"
    assert payload["choices"][0]["index"] == 0
    assert payload["choices"][0]["delta"] == {}
    assert payload["choices"][0]["finish_reason"] is None
    assert payload["usage"] == usage


def test_build_usage_chunk_created_timestamp():
    """build_usage_chunk() includes valid timestamp."""
    from streaming_events import build_usage_chunk
    
    before = int(time.time())
    result = build_usage_chunk("test123", {"prompt_tokens": 10})
    after = int(time.time())
    
    payload = json.loads(result[6:].strip())
    assert before <= payload["created"] <= after


def test_build_usage_chunk_unicode():
    """build_usage_chunk() handles unicode in model name."""
    from streaming_events import build_usage_chunk
    
    result = build_usage_chunk("test123", {"prompt_tokens": 10}, model="测试模型")
    payload = json.loads(result[6:].strip())
    assert payload["model"] == "测试模型"


# ─── Test 4: _extract_meta parses __LIMA_META__ protocol ─────────────────────

def test_extract_meta_valid():
    """_extract_meta() parses valid __LIMA_META__ chunks."""
    from routes.chat_stream import _extract_meta
    
    meta = {"usage": {"prompt_tokens": 100}}
    chunk = f"__LIMA_META__:{json.dumps(meta)}"
    result = _extract_meta(chunk)
    assert result == meta


def test_extract_meta_non_meta():
    """_extract_meta() returns None for non-meta chunks."""
    from routes.chat_stream import _extract_meta
    
    result = _extract_meta("Hello world")
    assert result is None


def test_extract_meta_invalid_json():
    """_extract_meta() returns None for invalid JSON after prefix."""
    from routes.chat_stream import _extract_meta
    
    result = _extract_meta("__LIMA_META__:not json")
    assert result is None


def test_extract_meta_empty():
    """_extract_meta() returns None for empty string."""
    from routes.chat_stream import _extract_meta
    
    result = _extract_meta("")
    assert result is None


# ─── Test 5: Full usage pipeline simulation ──────────────────────────────────

def test_usage_pipeline_end_to_end():
    """Simulate full usage extraction pipeline: SSE -> meta -> usage chunk."""
    from http_response import extract_sse_usage
    from streaming_events import build_usage_chunk
    
    # Simulate backend SSE chunk with usage
    backend_chunk = json.dumps({
        "id": "chatcmpl-backend",
        "choices": [{"delta": {}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": 250,
            "completion_tokens": 100,
            "total_tokens": 350
        }
    })
    
    # Step 1: Extract usage from backend
    usage = extract_sse_usage(backend_chunk)
    assert usage is not None
    
    # Step 2: Build frontend usage chunk
    frontend_chunk = build_usage_chunk("frontend123", usage, model="lima-1.3")
    assert "data: " in frontend_chunk
    
    # Step 3: Verify usage preserved
    payload = json.loads(frontend_chunk[6:].strip())
    assert payload["usage"]["prompt_tokens"] == 250
    assert payload["usage"]["completion_tokens"] == 100


def test_meta_protocol_flow():
    """Simulate __LIMA_META__ protocol flow."""
    from routes.chat_stream import _extract_meta
    from streaming_events import build_usage_chunk
    
    # Simulate stream with meta and content chunks
    stream = [
        "Hello",
        "__LIMA_META__:{\"usage\":{\"prompt_tokens\":50,\"completion_tokens\":20}}",
        " world",
        "__LIMA_META__:{\"reasoning_content\":\"thinking...\"}",
        "!",
    ]
    
    usage = None
    reasoning = None
    content_parts = []
    
    for chunk in stream:
        meta = _extract_meta(chunk)
        if meta:
            if "usage" in meta:
                usage = meta["usage"]
            if "reasoning_content" in meta:
                reasoning = meta["reasoning_content"]
        else:
            content_parts.append(chunk)
    
    assert usage == {"prompt_tokens": 50, "completion_tokens": 20}
    assert reasoning == "thinking..."
    assert "".join(content_parts) == "Hello world!"


# ─── Test 6: Tool calls SSE format verification ──────────────────────────────

def test_tool_calls_sse_format():
    """Verify OpenAI tool_calls SSE delta format."""
    # OpenCode expects this format for streaming tool calls
    tool_call_start = {
        "choices": [{
            "index": 0,
            "delta": {
                "tool_calls": [{
                    "index": 0,
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": ""
                    }
                }]
            },
            "finish_reason": None
        }]
    }
    
    tool_call_delta = {
        "choices": [{
            "index": 0,
            "delta": {
                "tool_calls": [{
                    "index": 0,
                    "function": {
                        "arguments": "{\"file"
                    }
                }]
            },
            "finish_reason": None
        }]
    }
    
    tool_call_end = {
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": "tool_calls"
        }],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
    }
    
    # Verify structure
    assert tool_call_start["choices"][0]["delta"]["tool_calls"][0]["id"] == "call_abc123"
    assert tool_call_start["choices"][0]["delta"]["tool_calls"][0]["type"] == "function"
    assert tool_call_start["choices"][0]["delta"]["tool_calls"][0]["function"]["name"] == "read_file"
    
    assert tool_call_delta["choices"][0]["delta"]["tool_calls"][0]["function"]["arguments"] == "{\"file"
    
    assert tool_call_end["choices"][0]["finish_reason"] == "tool_calls"
    assert tool_call_end["usage"]["prompt_tokens"] == 100


# ─── Test 7: Edge cases ─────────────────────────────────────────────────────

def test_extract_sse_usage_with_extra_fields():
    """extract_sse_usage() ignores extra fields in usage."""
    from http_response import extract_sse_usage
    
    chunk = json.dumps({
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "prompt_tokens_details": {"cached_tokens": 50}
        }
    })
    result = extract_sse_usage(chunk)
    assert result["prompt_tokens"] == 100


def test_build_usage_chunk_ensure_ascii():
    """build_usage_chunk() handles non-ASCII in usage values."""
    from streaming_events import build_usage_chunk
    
    usage = {"prompt_tokens": 100, "note": "测试"}
    result = build_usage_chunk("test123", usage)
    # Should be valid JSON
    payload = json.loads(result[6:].strip())
    assert payload["usage"]["note"] == "测试"


def test_extract_meta_whitespace():
    """_extract_meta() handles whitespace after prefix."""
    from routes.chat_stream import _extract_meta
    
    result = _extract_meta("__LIMA_META__:  {\"usage\":{}}")
    # Should still parse (JSON parser handles leading whitespace)
    assert result is not None