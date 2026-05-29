from response_cleaner import clean_response


def test_clean_response_preserves_third_party_facts():
    text = "ChatGPT was developed by OpenAI as a chatbot."
    result = clean_response(text)
    assert result == text
