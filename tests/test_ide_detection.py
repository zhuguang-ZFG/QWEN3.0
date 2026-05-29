import server
import router_v3


# ─── Layer 3: _detect_ide (message content scanning) ─────────────────────────

def test_detect_ide_returns_empty_string_for_ordinary_chat():
    assert server._detect_ide([
        {"role": "user", "content": "hello, how are you?"}
    ]) == ""


def test_detect_ide_claude_code():
    assert server._detect_ide([
        {"role": "system", "content": "Claude Code workspace context"}
    ]) == "Claude Code"
    assert server._detect_ide([
        {"role": "system", "content": "You are claude-code assistant"}
    ]) == "Claude Code"


def test_detect_ide_cursor():
    assert server._detect_ide([
        {"role": "system", "content": "You are Cursor, an intelligent programmer"}
    ]) == "Cursor"


def test_detect_ide_kiro():
    assert server._detect_ide([
        {"role": "system", "content": "You are Kiro, an AI-powered development environment."}
    ]) == "Kiro"


def test_detect_ide_zed():
    assert server._detect_ide([
        {"role": "system", "content": "You are an AI assistant in Zed editor"}
    ]) == "Zed"
    assert server._detect_ide([
        {"role": "system", "content": "zed-editor context"}
    ]) == "Zed"


def test_detect_ide_trae():
    assert server._detect_ide([
        {"role": "system", "content": "You are Trae, a coding assistant by ByteDance"}
    ]) == "Trae"


def test_detect_ide_windsurf():
    assert server._detect_ide([
        {"role": "system", "content": "Windsurf AI coding assistant"}
    ]) == "Windsurf"
    assert server._detect_ide([
        {"role": "system", "content": "Powered by Codeium engine"}
    ]) == "Windsurf"


def test_detect_ide_copilot():
    assert server._detect_ide([
        {"role": "system", "content": "GitHub Copilot instructions"}
    ]) == "GitHub Copilot"


def test_detect_ide_codex():
    assert server._detect_ide([
        {"role": "system", "content": "You are Codex, a coding agent"}
    ]) == "Codex"


def test_detect_ide_continue():
    assert server._detect_ide([
        {"role": "system", "content": "Continue is an open-source AI code assistant from continue.dev"}
    ]) == "Continue"


def test_detect_ide_cline():
    assert server._detect_ide([
        {"role": "system", "content": "Cline assistant with <environment_details>"}
    ]) == "Cline"


def test_detect_ide_aider():
    assert server._detect_ide([
        {"role": "system", "content": "Use SEARCH/REPLACE blocks to edit files"}
    ]) == "Aider"


# ─── Layer 2: router_v3 system prompt fingerprinting ─────────────────────────

def test_fingerprint_detects_kiro():
    result = router_v3.detect_ide_from_system_prompt("You are Kiro, an AI-powered IDE")
    assert result == "kiro"


def test_fingerprint_detects_zed():
    result = router_v3.detect_ide_from_system_prompt("You are an AI assistant in Zed editor")
    assert result == "zed"


def test_fingerprint_detects_trae():
    result = router_v3.detect_ide_from_system_prompt("Trae coding assistant")
    assert result == "trae"


def test_fingerprint_detects_windsurf():
    result = router_v3.detect_ide_from_system_prompt("Windsurf by Codeium")
    assert result == "windsurf"


def test_fingerprint_detects_copilot():
    result = router_v3.detect_ide_from_system_prompt("GitHub Copilot chat")
    assert result == "copilot"


def test_fingerprint_detects_cursor():
    result = router_v3.detect_ide_from_system_prompt("You are Cursor, an intelligent programmer")
    assert result == "cursor"


def test_fingerprint_detects_claude_code():
    result = router_v3.detect_ide_from_system_prompt("CLAUDE.md workspace context")
    assert result == "claude_code"


# ─── Layer 1: User-Agent header detection ────────────────────────────────────

def test_classify_request_detects_kiro_ua():
    info = router_v3.classify_request("/v1/chat/completions", {"user-agent": "kiro/1.0"}, {})
    assert info["type"] == "ide"


def test_classify_request_detects_zed_ua():
    info = router_v3.classify_request("/v1/chat/completions", {"user-agent": "zed-editor/0.150"}, {})
    assert info["type"] == "ide"


def test_classify_request_detects_trae_ua():
    info = router_v3.classify_request("/v1/chat/completions", {"user-agent": "trae/2.0"}, {})
    assert info["type"] == "ide"


def test_classify_request_detects_windsurf_ua():
    info = router_v3.classify_request("/v1/chat/completions", {"user-agent": "windsurf/1.5"}, {})
    assert info["type"] == "ide"


def test_classify_request_detects_copilot_ua():
    info = router_v3.classify_request("/v1/chat/completions", {"user-agent": "copilot-chat/0.8"}, {})
    assert info["type"] == "ide"
