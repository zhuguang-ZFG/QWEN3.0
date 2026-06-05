import code_orchestrator

from lima_context import build_context_digest


def test_build_context_digest_extracts_file_error_and_language():
    messages = [
        {
            "role": "user",
            "content": (
                "Fix D:\\GIT\\server.py after this error:\n"
                "Traceback (most recent call last):\n"
                "  File \"server.py\", line 10\n"
                "SyntaxError: invalid syntax"
            ),
        }
    ]

    digest = build_context_digest(
        "Fix the bug",
        messages,
        system_prompt="Working directory: D:\\GIT",
        ide_source="OpenCode",
    )

    assert "LiMa context preflight" in digest
    assert "IDE: OpenCode" in digest
    assert "Language: python" in digest
    assert "D:\\GIT\\server.py" in digest
    assert "SyntaxError" in digest
    assert "VPS cannot read the user's local workspace directly" in digest


def test_build_context_digest_summarizes_tool_results():
    messages = [
        {"role": "user", "content": "Why did tests fail?"},
        {
            "role": "tool",
            "content": "pytest failed\nFAILED tests/test_api.py::test_login - AssertionError",
        },
    ]

    digest = build_context_digest("Why did tests fail?", messages, ide_source="OpenCode")

    assert "Tool/error signals" in digest
    assert "pytest failed" in digest
    assert "tests/test_api.py" in digest


def test_build_context_digest_returns_empty_for_trivial_chat():
    digest = build_context_digest("hello", [{"role": "user", "content": "hello"}])

    assert digest == ""


def test_build_context_digest_respects_max_chars():
    long_path_list = "\n".join(f"/repo/src/module_{i}/file_{i}.py" for i in range(50))

    digest = build_context_digest(
        "Fix many files",
        [{"role": "user", "content": long_path_list + "\nTypeError: bad"}],
        max_chars=420,
    )

    assert len(digest) <= 420
    assert digest.endswith("...")


def test_code_orchestrator_injects_preflight_into_coding_context():
    messages = [
        {
            "role": "user",
            "content": "Fix D:\\GIT\\server.py\nTypeError: bad operand",
        }
    ]

    ctx = code_orchestrator.enhance_context(
        "Fix D:\\GIT\\server.py", messages, "coding"
    )

    assert "LiMa context preflight" in ctx["system_prompt"]
    assert "D:\\GIT\\server.py" in ctx["system_prompt"]
