import server


def test_detect_ide_returns_empty_string_for_ordinary_chat():
    assert server._detect_ide([
        {"role": "user", "content": "hello, how are you?"}
    ]) == ""


def test_detect_ide_keeps_known_ide_source():
    assert server._detect_ide([
        {"role": "system", "content": "Claude Code workspace context"}
    ]) == "Claude Code"
