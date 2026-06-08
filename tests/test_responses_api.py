"""Tests for OpenAI Responses API adapter."""

from __future__ import annotations

import json

from chat_models import ChatRequest
from chat_request_utils import request_sampling_params
from converters.responses_api import (
    chat_completion_to_response,
    responses_body_to_chat,
    transform_chat_sse_iter,
)


def _responses_events(out: str) -> list[dict]:
    events: list[dict] = []
    for block in out.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


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


def test_responses_text_verbosity_merges_with_instructions():
    body = {
        "model": "lima-1.3",
        "input": "Hello",
        "instructions": "You are concise.",
        "text": {"verbosity": "low"},
    }

    chat = responses_body_to_chat(body)

    assert chat["messages"][0]["role"] == "system"
    assert "You are concise." in chat["messages"][0]["content"]
    assert "Keep the response concise." in chat["messages"][0]["content"]
    assert chat["messages"][1] == {"role": "user", "content": "Hello"}


def test_responses_text_verbosity_adds_system_message_without_instructions():
    body = {
        "model": "lima-1.3",
        "input": "Explain the diff.",
        "text": {"verbosity": "high"},
    }

    chat = responses_body_to_chat(body)

    assert chat["messages"][0] == {
        "role": "system",
        "content": "Provide thorough detail when useful.",
    }
    assert chat["messages"][1] == {"role": "user", "content": "Explain the diff."}


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


def test_responses_tool_choice_function_object_to_chat_shape():
    body = {
        "model": "lima-1.3",
        "input": "Use the read tool.",
        "tools": [{
            "type": "function",
            "name": "read",
            "description": "Read a file",
            "parameters": {"type": "object", "properties": {}},
            "strict": True,
        }],
        "tool_choice": {"type": "function", "name": "read"},
    }

    chat = responses_body_to_chat(body)

    assert chat["tool_choice"] == {"type": "function", "function": {"name": "read"}}
    assert chat["tools"][0]["function"]["strict"] is True


def test_responses_tool_choice_strings_pass_through():
    for choice in ("auto", "none", "required"):
        chat = responses_body_to_chat({
            "model": "lima-1.3",
            "input": "hi",
            "tool_choice": choice,
        })

        assert chat["tool_choice"] == choice


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


def test_responses_preserves_reasoning_summary_without_encrypted_state():
    body = {
        "model": "lima-1.3",
        "input": [
            {"role": "user", "content": [{"type": "input_text", "text": "What happened?"}]},
            {
                "type": "reasoning",
                "id": "rs_1",
                "summary": [{
                    "type": "summary_text",
                    "text": "I inspected the previous turn.",
                }],
                "encrypted_content": "encrypted-state",
            },
            {"role": "assistant", "content": [{"type": "output_text", "text": "It showed a file."}]},
            {"role": "user", "content": [{"type": "input_text", "text": "Continue."}]},
        ],
        "store": False,
        "include": ["reasoning.encrypted_content"],
    }

    chat = responses_body_to_chat(body)

    dumped = json.dumps(chat["messages"])
    assert "Previous reasoning summary" in dumped
    assert "I inspected the previous turn." in dumped
    assert "encrypted-state" not in dumped
    assert [message["role"] for message in chat["messages"]] == [
        "user",
        "assistant",
        "assistant",
        "user",
    ]


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


def test_request_sampling_params_does_not_materialize_temperature_default():
    req = ChatRequest(messages=[{"role": "user", "content": "hi"}])

    assert request_sampling_params(req) == {}


def test_request_sampling_params_keeps_explicit_responses_sampling():
    req = ChatRequest(
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.2,
        top_p=0.7,
    )

    assert request_sampling_params(req) == {"temperature": 0.2, "top_p": 0.7}


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


def test_chat_completion_to_response_preserves_reasoning_output():
    data = {
        "created": 1700000000,
        "model": "lima-1.3",
        "choices": [{
            "message": {
                "role": "assistant",
                "reasoning_content": "I should inspect the result first.",
                "content": "OK",
            },
            "finish_reason": "stop",
        }],
    }

    resp = chat_completion_to_response(data)

    assert resp["output"][0]["type"] == "reasoning"
    assert resp["output"][0]["summary"] == [{
        "type": "summary_text",
        "text": "I should inspect the result first.",
    }]
    assert resp["output"][0]["encrypted_content"] is None
    assert resp["output"][1]["type"] == "message"
    assert resp["output"][1]["content"][0]["text"] == "OK"


def test_chat_completion_to_response_maps_length_finish_to_incomplete():
    data = {
        "created": 1700000000,
        "model": "lima-1.3",
        "choices": [{
            "message": {"role": "assistant", "content": "partial"},
            "finish_reason": "length",
        }],
    }

    resp = chat_completion_to_response(data)

    assert resp["status"] == "incomplete"
    assert resp["incomplete_details"] == {"reason": "max_output_tokens"}
    assert resp["output"][0]["content"][0]["text"] == "partial"


def test_chat_completion_to_response_maps_content_filter_finish_to_incomplete():
    data = {
        "created": 1700000000,
        "model": "lima-1.3",
        "choices": [{
            "message": {"role": "assistant", "content": ""},
            "finish_reason": "content_filter",
        }],
    }

    resp = chat_completion_to_response(data)

    assert resp["status"] == "incomplete"
    assert resp["incomplete_details"] == {"reason": "content_filter"}


def test_chat_completion_to_response_preserves_usage_details():
    data = {
        "created": 1700000000,
        "model": "lima-1.3",
        "choices": [{
            "message": {"role": "assistant", "content": "OK"},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": 30,
            "completion_tokens": 12,
            "total_tokens": 42,
            "prompt_tokens_details": {"cached_tokens": 8},
            "completion_tokens_details": {"reasoning_tokens": 5},
        },
    }

    resp = chat_completion_to_response(data)

    assert resp["usage"]["input_tokens"] == 30
    assert resp["usage"]["output_tokens"] == 12
    assert resp["usage"]["input_tokens_details"] == {"cached_tokens": 8}
    assert resp["usage"]["output_tokens_details"] == {"reasoning_tokens": 5}


def test_chat_completion_to_response_preserves_opencode_response_metadata():
    data = {
        "created": 1700000000,
        "model": "lima-1.3",
        "choices": [{
            "message": {"role": "assistant", "content": "OK"},
            "finish_reason": "stop",
        }],
    }
    request_body = {
        "store": False,
        "prompt_cache_key": "session-recorded-opencode-loop",
        "include": ["reasoning.encrypted_content"],
        "reasoning": {"effort": "medium", "summary": "auto"},
        "text": {"verbosity": "low"},
        "temperature": 1.0,
        "top_p": 0.98,
        "input": "not echoed",
        "stream": False,
    }

    resp = chat_completion_to_response(data, request_body=request_body)

    assert resp["store"] is False
    assert resp["prompt_cache_key"] == "session-recorded-opencode-loop"
    assert resp["include"] == ["reasoning.encrypted_content"]
    assert resp["reasoning"] == {"effort": "medium", "summary": "auto"}
    assert resp["text"] == {"verbosity": "low"}
    assert resp["temperature"] == 1.0
    assert resp["top_p"] == 0.98
    assert "input" not in resp
    assert "stream" not in resp


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
    done_messages = [
        event["item"]
        for event in _responses_events(out)
        if event.get("type") == "response.output_item.done"
        and event.get("item", {}).get("type") == "message"
    ]
    assert done_messages[0]["content"] == [{"type": "output_text", "text": "Hello"}]
    terminal = _responses_events(out)[-1]
    assert terminal["response"]["output"][0]["content"] == [
        {"type": "output_text", "text": "Hello"}
    ]


def test_stream_converter_maps_length_finish_to_response_incomplete():
    lines = [
        'data: {"choices":[{"delta":{"content":"partial"},"finish_reason":"length"}]}',
        "data: [DONE]",
    ]
    out = "".join(transform_chat_sse_iter(iter(lines), model="lima-1.3"))
    events = _responses_events(out)

    terminal = events[-1]
    assert terminal["type"] == "response.incomplete"
    assert terminal["response"]["status"] == "incomplete"
    assert terminal["response"]["incomplete_details"] == {"reason": "max_output_tokens"}
    assert not any(event.get("type") == "response.completed" for event in events)


def test_stream_converter_preserves_usage_details_in_completed_event():
    chunk = {
        "usage": {
            "prompt_tokens": 30,
            "completion_tokens": 12,
            "total_tokens": 42,
            "prompt_tokens_details": {"cached_tokens": 8},
            "completion_tokens_details": {"reasoning_tokens": 5},
        },
        "choices": [{"delta": {}}],
    }
    lines = [f"data: {json.dumps(chunk)}", "data: [DONE]"]

    out = "".join(transform_chat_sse_iter(iter(lines), model="lima-1.3"))

    assert '"input_tokens_details": {"cached_tokens": 8}' in out
    assert '"output_tokens_details": {"reasoning_tokens": 5}' in out


def test_stream_converter_preserves_opencode_response_metadata():
    request_body = {
        "store": False,
        "prompt_cache_key": "session-recorded-opencode-loop",
        "include": ["reasoning.encrypted_content"],
        "reasoning": {"effort": "medium", "summary": "auto"},
        "text": {"verbosity": "low"},
    }
    lines = [
        'data: {"choices":[{"delta":{"content":"OK"}}]}',
        "data: [DONE]",
    ]

    out = "".join(
        transform_chat_sse_iter(
            iter(lines),
            model="lima-1.3",
            request_body=request_body,
        )
    )
    events = _responses_events(out)
    created = events[0]["response"]
    terminal = events[-1]["response"]

    for response in (created, terminal):
        assert response["store"] is False
        assert response["prompt_cache_key"] == "session-recorded-opencode-loop"
        assert response["include"] == ["reasoning.encrypted_content"]
        assert response["reasoning"] == {"effort": "medium", "summary": "auto"}
        assert response["text"] == {"verbosity": "low"}


def test_stream_converter_maps_chat_error_to_response_failed_without_completed():
    chunk = {
        "error": {
            "message": "upstream overloaded",
            "code": "server_overloaded",
            "param": "model",
        },
    }
    lines = [f"data: {json.dumps(chunk)}", "data: [DONE]"]

    out = "".join(transform_chat_sse_iter(iter(lines), model="lima-1.3"))

    assert "response.failed" in out
    assert '"status": "failed"' in out
    assert '"message": "upstream overloaded"' in out
    assert '"code": "server_overloaded"' in out
    assert '"param": "model"' in out
    assert "response.completed" not in out


def test_stream_converter_maps_chat_reasoning_content_to_responses_reasoning_events():
    chunk = {
        "choices": [{
            "delta": {
                "reasoning_content": "I should inspect the file first.",
            },
        }],
    }
    lines = [f"data: {json.dumps(chunk)}", "data: [DONE]"]

    out = "".join(transform_chat_sse_iter(iter(lines), model="lima-1.3"))

    assert "response.output_item.added" in out
    assert '"type": "reasoning"' in out
    assert "response.reasoning_summary_part.added" in out
    assert "response.reasoning_summary_text.delta" in out
    assert "I should inspect the file first." in out
    assert "response.reasoning_summary_part.done" in out
    assert "response.output_item.done" in out


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


def test_stream_converter_suppresses_tool_argument_delta_until_tool_is_announced():
    first = {
        "choices": [{
            "delta": {
                "tool_calls": [{
                    "index": 0,
                    "id": "call_late",
                    "function": {"arguments": "{\"path\""},
                }],
            },
        }],
    }
    second = {
        "choices": [{
            "delta": {
                "tool_calls": [{
                    "index": 0,
                    "function": {"name": "read_file", "arguments": ":\"AGENTS.md\"}"},
                }],
            },
        }],
    }
    lines = [f"data: {json.dumps(first)}", f"data: {json.dumps(second)}", "data: [DONE]"]

    out = "".join(transform_chat_sse_iter(iter(lines)))

    assert '"output_index": null' not in out
    assert "response.output_item.added" in out
    assert '"arguments": "{\\"path\\":\\"AGENTS.md\\"}"' in out
    terminal = _responses_events(out)[-1]
    assert terminal["response"]["output"][0]["arguments"] == "{\"path\":\"AGENTS.md\"}"
