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


def test_responses_standalone_function_call_output_to_non_empty_user_turn():
    body = {
        "model": "lima-1.3",
        "input": [{
            "type": "function_call_output",
            "call_id": "call_read_1",
            "output": "# AGENTS.md\n\nProject instructions",
        }],
    }
    chat = responses_body_to_chat(body)

    assert chat["messages"] == [{
        "role": "user",
        "content": (
            "Tool output for call call_read_1:\n"
            "# AGENTS.md\n\nProject instructions\n\n"
            "Continue from this tool result and answer the user's request."
        ),
    }]


def test_responses_content_list_function_call_output_to_user_turn():
    body = {
        "model": "lima-1.3",
        "input": [{
            "role": "user",
            "content": [{
                "type": "function_call_output",
                "call_id": "call_read_2",
                "output": "README heading",
            }],
        }],
    }
    chat = responses_body_to_chat(body)

    assert chat["messages"][0]["role"] == "user"
    assert "Tool output for call call_read_2" in chat["messages"][0]["content"]
    assert "README heading" in chat["messages"][0]["content"]


def test_responses_skips_reasoning_and_item_reference_replay_metadata():
    body = {
        "model": "lima-1.3",
        "input": [
            {"role": "user", "content": [{"type": "input_text", "text": "Use the tool."}]},
            {
                "type": "reasoning",
                "id": "rs_1",
                "summary": [],
                "encrypted_content": "encrypted-state",
            },
            {"type": "item_reference", "id": "rs_1"},
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "read",
                "arguments": "{\"filePath\":\"AGENTS.md\"}",
            },
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "# AGENTS.md",
            },
        ],
        "store": False,
        "include": ["reasoning.encrypted_content"],
    }

    chat = responses_body_to_chat(body)

    assert [message["role"] for message in chat["messages"]] == ["user", "assistant", "user"]
    assert all(message.get("content") != "" for message in chat["messages"])
    assert "encrypted-state" not in json.dumps(chat["messages"])


def test_responses_structured_function_call_output_to_readable_continuation():
    body = {
        "model": "lima-1.3",
        "input": [{
            "type": "function_call_output",
            "call_id": "call_screenshot",
            "output": [
                {"type": "input_text", "text": "Screenshot captured"},
                {"type": "input_image", "image_url": "data:image/png;base64," + ("a" * 400)},
            ],
        }],
    }

    chat = responses_body_to_chat(body)

    content = chat["messages"][0]["content"]
    assert "Tool output for call call_screenshot" in content
    assert "Screenshot captured" in content
    assert "[image:" in content
    assert len(content) < 700


def test_responses_passthrough_sampling_options_and_ignores_response_state_options():
    body = {
        "model": "lima-1.3",
        "input": "hi",
        "stream": True,
        "top_p": 0.7,
        "temperature": 0.2,
        "store": False,
        "include": ["reasoning.encrypted_content"],
        "previous_response_id": "resp_previous",
    }

    chat = responses_body_to_chat(body)

    assert chat["top_p"] == 0.7
    assert chat["temperature"] == 0.2
    assert "store" not in chat
    assert "include" not in chat
    assert "previous_response_id" not in chat


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
