"""Anthropic message conversion edge cases."""

from converters.anthropic_format import convert_messages_anthropic_to_openai


def test_tool_result_and_text_blocks_preserved_in_user_turn():
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_1",
                    "content": "file contents here",
                },
                {
                    "type": "text",
                    "text": "now continue with step 2",
                },
            ],
        }
    ]

    openai_msgs = convert_messages_anthropic_to_openai(messages)

    assert len(openai_msgs) == 2
    assert openai_msgs[0] == {
        "role": "user",
        "content": "now continue with step 2",
    }
    assert openai_msgs[1]["role"] == "tool"
    assert openai_msgs[1]["tool_call_id"] == "toolu_1"
    assert "file contents" in openai_msgs[1]["content"]
