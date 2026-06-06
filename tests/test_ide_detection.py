import router_v3
import server

# ─── Layer 3: _detect_ide (message content scanning) ─────────────────────────

def test_detect_ide_returns_empty_string_for_ordinary_chat():
    assert server._detect_ide([
        {"role": "user", "content": "hello, how are you?"}
    ]) == ""


def test_detect_ide_opencode():
    assert server._detect_ide([
        {"role": "system", "content": "OpenCode workspace context"}
    ]) == "OpenCode"
    assert server._detect_ide([
        {"role": "system", "content": "opencode-ai coding assistant"}
    ]) == "OpenCode"


# ─── Layer 2: router_v3 system prompt fingerprinting ─────────────────────────

def test_fingerprint_detects_opencode():
    result = router_v3.detect_ide_from_system_prompt("OpenCode coding assistant")
    assert result == "OpenCode"


def test_fingerprint_detects_opencode_ai():
    result = router_v3.detect_ide_from_system_prompt("opencode-ai workspace")
    assert result == "OpenCode"


# ─── Layer 1: User-Agent header detection ────────────────────────────────────

def test_classify_request_detects_opencode_ua():
    info = router_v3.classify_request("/v1/chat/completions", {"user-agent": "opencode/1.0"}, {})
    assert info["type"] == "ide"


def test_classify_request_detects_opencode_ai_ua():
    info = router_v3.classify_request("/v1/chat/completions", {"user-agent": "opencode-ai/2.0"}, {})
    assert info["type"] == "ide"


def test_classify_request_ignores_generic_ua():
    info = router_v3.classify_request("/v1/chat/completions", {"user-agent": "curl/8.0"}, {})
    assert info["type"] == "chat"
