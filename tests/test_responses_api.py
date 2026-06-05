"""Tests for OpenAI Responses API adapter."""

from __future__ import annotations

import json

from converters.responses_api import (
    chat_completion_to_response,
    responses_body_to_chat,
    transform_chat_sse_iter,
)


def test_responses_string_input_to_chat():
    body = {
        "model": "lima-1.3",
        "input": "Hello",
        "instructions": "You are OpenCode, an AI coding assistant.",
        "stream": True,
        "max_output_tokens": 256,
    }
    chat = responses_body_to_chat(body)
    assert chat["model"] == "lima-1.3"
    assert chat["stream"] is True
    assert chat["max_tokens"] == 256
    assert chat["messages"][0]["role"] == "system"
    assert "OpenCode" in chat["messages"][0]["content"]
    assert chat["messages"][1] == {"role": "user", "content": "Hello"}


def test_responses_structured_input_and_tools():
    body = {
        "model": "lima-1.3",
        "input": [
            {"role": "user", "content": [{"type": "input_text", "text": "Hi"}]},
        ],
        "tools": [{
            "type": "function",
            "name": "read_file",
            "description": "Read a file",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
        }],
        "reasoning": {"effort": "high"},
    }
    chat = responses_body_to_chat(body)
    assert chat["messages"][-1]["content"] == "Hi"
    assert chat["tools"][0]["function"]["name"] == "read_file"
    assert chat["reasoning_effort"] == "high"


def test_chat_completion_to_response_text():
    data = {
        "created": 1700000000,
        "model": "lima-1.3",
        "choices": [{
            "message": {"role": "assistant", "content": "OK"},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
    }
    resp = chat_completion_to_response(data)
    assert resp["object"] == "response"
    assert resp["status"] == "completed"
    assert resp["output"][0]["content"][0]["text"] == "OK"
    assert resp["usage"]["total_tokens"] == 4


def test_stream_converter_emits_text_deltas():
    lines = [
        'data: {"choices":[{"delta":{"content":"Hel"}}]}',
        'data: {"choices":[{"delta":{"content":"lo"}}]}',
        "data: [DONE]",
    ]
    out = "".join(transform_chat_sse_iter(iter(lines), model="lima-1.3"))
    assert "response.created" in out
    assert "response.output_text.delta" in out
    assert "response.completed" in out
    assert '"delta": "Hel"' in out or '"delta":"Hel"' in out.replace(" ", "")


def test_stream_converter_emits_tool_events():
    chunk = {
        "choices": [{
            "delta": {
                "tool_calls": [{
                    "index": 0,
                    "id": "call_abc",
                    "function": {"name": "read_file", "arguments": "{\"path\":"},
                }],
            },
        }],
    }
    lines = [f"data: {json.dumps(chunk)}", "data: [DONE]"]
    out = "".join(transform_chat_sse_iter(iter(lines)))
    assert "function_call" in out
    assert "response.function_call_arguments.delta" in out
    assert "response.completed" in out
