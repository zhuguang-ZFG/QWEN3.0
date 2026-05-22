import json

import server


def _first_text(resp):
    blocks = resp.get("content", [])
    assert blocks
    assert blocks[0]["type"] == "text"
    return blocks[0]["text"]


def _event_payload(chunk):
    for line in chunk.splitlines():
        if line.startswith("data: "):
            return json.loads(line.removeprefix("data: "))
    raise AssertionError(f"missing data line: {chunk!r}")


def test_empty_openai_message_converts_to_valid_anthropic_text():
    resp = server._convert_response_openai_to_anthropic(
        {
            "choices": [{"message": {"role": "assistant", "content": ""}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 0},
        },
        "backend-model",
    )

    assert resp["type"] == "message"
    assert resp["stop_reason"] == "end_turn"
    assert _first_text(resp)


def test_malformed_openai_response_converts_to_valid_anthropic_text():
    resp = server._convert_response_openai_to_anthropic({}, "backend-model")

    assert resp["type"] == "message"
    assert resp["model"] == "backend-model"
    assert "empty or malformed" in _first_text(resp)


def test_openai_text_list_content_is_normalized_to_string():
    resp = server._convert_response_openai_to_anthropic(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "hello"},
                            {"type": "text", "text": " world"},
                        ],
                    }
                }
            ]
        },
        "backend-model",
    )

    assert _first_text(resp) == "hello world"


def test_tool_use_stream_start_contains_empty_input_object():
    chunks = list(
        server._simulate_anthropic_sse(
            {
                "id": "msg_test",
                "model": "backend-model",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_test",
                        "name": "Read",
                        "input": {"file_path": "D:/GIT/server.py"},
                    }
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        )
    )
    starts = [
        _event_payload(chunk)
        for chunk in chunks
        if chunk.startswith("event: content_block_start")
    ]

    assert starts[0]["content_block"] == {
        "type": "tool_use",
        "id": "toolu_test",
        "name": "Read",
        "input": {},
    }
