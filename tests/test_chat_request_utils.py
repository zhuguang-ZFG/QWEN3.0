from chat_request_utils import extract_last_user_text, extract_system_preview


def test_extract_system_preview_uses_openai_system_message():
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "system", "content": "x" * 250},
    ]

    assert extract_system_preview(messages) == "x" * 200


def test_extract_system_preview_uses_anthropic_system_string_when_no_message():
    assert (
        extract_system_preview(
            [{"role": "user", "content": "hello"}],
            system="base prompt",
        )
        == "base prompt"
    )


def test_extract_system_preview_joins_anthropic_system_text_blocks():
    system = [
        {"type": "text", "text": "base"},
        {"type": "image", "source": {}},
        {"type": "text", "text": "prompt"},
    ]

    assert extract_system_preview([], system=system) == "base prompt"


def test_extract_last_user_text_handles_string_and_text_blocks():
    assert (
        extract_last_user_text(
            [
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "ignored"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "second"},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
                        {"type": "text", "text": "question"},
                    ],
                },
            ]
        )
        == "second question"
    )


def test_extract_last_user_text_ignores_non_dict_items():
    assert extract_last_user_text([None, "bad", {"role": "assistant", "content": "no"}]) == ""
