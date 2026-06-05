import socket

import pytest

import search_gateway.safety as safety
from search_gateway.safety import is_public_http_url, sanitize_error_text
from search_gateway.policy import should_dev_search
from search_gateway.dev_tools import (
    build_prompt_evidence,
    fetch_github_file,
    read_url,
    search_docs,
    search_error,
    summarize_sources,
)
from lima_mcp import TOOL_DEFINITIONS
from lima_mcp.tools import handle_tool_call


@pytest.fixture(autouse=True)
def deterministic_dns(monkeypatch):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        normalized = host.lower().rstrip(".")
        if normalized == "localtest.me":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]
        if normalized == "docs.python.org":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("198.18.0.243", port))]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    monkeypatch.setattr(safety.socket, "getaddrinfo", fake_getaddrinfo)


def test_sanitize_error_text_redacts_tokens_paths_and_limits_length():
    secret = "sk-" + "abc123456789xyz"
    raw = f"Traceback token {secret} at D:\\GIT\\.env host 192.168.1.10\n" + ("x" * 6000)

    result = sanitize_error_text(raw, max_chars=200)

    assert "sk-" not in result
    assert "D:\\GIT" not in result
    assert "192.168.1.10" not in result
    assert len(result) <= 200
    assert "[REDACTED_TOKEN]" in result


def test_is_public_http_url_blocks_private_and_non_http_targets():
    assert is_public_http_url("https://docs.python.org/3/library/asyncio.html") is True
    assert is_public_http_url("http://example.com/a") is True
    assert is_public_http_url("file:///etc/passwd") is False
    assert is_public_http_url("http://127.0.0.1:8080/admin") is False
    assert is_public_http_url("http://192.168.1.2/config") is False
    assert is_public_http_url("https://localhost:3000") is False


def test_is_public_http_url_blocks_obfuscated_loopback_and_metadata_targets():
    assert is_public_http_url("http://[::1]:8080/admin") is False
    assert is_public_http_url("http://0x7f000001/admin") is False
    assert is_public_http_url("http://2130706433/admin") is False
    assert is_public_http_url("http://169.254.169.254/latest/meta-data/") is False
    assert is_public_http_url("http://[fd00::1]/admin") is False
    assert is_public_http_url("http://localhost./admin") is False
    assert is_public_http_url("http://localtest.me/admin") is False


def test_is_public_http_url_allows_proxy_fake_ip_for_normal_hostname():
    assert is_public_http_url("https://docs.python.org/3/") is True


def test_should_dev_search_detects_programming_docs_errors_and_urls():
    assert should_dev_search("check FastAPI official docs for Depends") is True
    assert should_dev_search("search latest React useActionState docs") is True
    assert should_dev_search("read https://docs.python.org/3/library/asyncio.html") is True
    assert should_dev_search("how to fix TypeError: object NoneType cannot be awaited") is True
    assert should_dev_search("查一下 FastAPI 官方文档 Depends 怎么用") is True
    assert should_dev_search("这个报错怎么修") is True
    assert should_dev_search("读取 https://docs.python.org/3/library/asyncio.html") is True
    assert should_dev_search("help me rename functions in routing_engine.py") is False


class FakeAdapter:
    def __init__(self):
        self.calls = []

    def search(self, query, *, domain=None, max_results=5):
        self.calls.append(("search", query, domain, max_results))
        return {
            "ok": True,
            "results": [
                {
                    "title": "FastAPI Depends",
                    "url": "https://fastapi.tiangolo.com/tutorial/dependencies/",
                    "snippet": "Dependency injection docs",
                }
            ],
        }

    def batch_search(self, queries, *, domain=None, max_results=5):
        self.calls.append(("batch_search", queries, domain, max_results))
        return {"ok": True, "results": []}

    def extract_url(self, url):
        self.calls.append(("extract_url", url))
        return {"ok": True, "text": "hello docs body", "title": "Docs"}


def test_search_docs_normalizes_results_and_domains():
    adapter = FakeAdapter()

    result = search_docs("FastAPI Depends", ["fastapi.tiangolo.com"], adapter=adapter, max_results=3)

    assert result["ok"] is True
    assert result["tool"] == "dev_search_docs"
    assert result["results"][0]["url"].startswith("https://fastapi")
    assert adapter.calls[0] == ("search", "FastAPI Depends", "fastapi.tiangolo.com", 3)


def test_search_error_sanitizes_stack_before_search():
    adapter = FakeAdapter()
    secret = "sk-" + "abc123456789xyz"

    result = search_error(f"TypeError boom {secret} D:\\GIT\\.env", language="python", adapter=adapter)

    assert result["ok"] is True
    assert "sk-" not in adapter.calls[0][1]
    assert "D:\\GIT" not in adapter.calls[0][1]
    assert "python" in adapter.calls[0][1]


def test_read_url_blocks_private_targets():
    adapter = FakeAdapter()

    result = read_url("http://127.0.0.1:8080/admin", adapter=adapter)

    assert result == {"ok": False, "tool": "dev_read_url", "error": "url_blocked"}
    assert adapter.calls == []


def test_fetch_github_file_uses_raw_github_url():
    adapter = FakeAdapter()

    result = fetch_github_file("psf/requests", "src/requests/sessions.py", "main", adapter=adapter)

    assert result["ok"] is True
    assert adapter.calls[0] == (
        "extract_url",
        "https://raw.githubusercontent.com/psf/requests/main/src/requests/sessions.py",
    )


def test_fetch_github_file_preserves_slash_in_ref():
    adapter = FakeAdapter()

    fetch_github_file("psf/requests", "README.md", "feature/docs", adapter=adapter)

    assert adapter.calls[0][1] == (
        "https://raw.githubusercontent.com/psf/requests/feature/docs/README.md"
    )


def test_summarize_sources_builds_compact_evidence_block():
    result = summarize_sources([
        {"title": "A", "url": "https://example.com/a", "snippet": "alpha"},
        {"title": "B", "url": "https://example.com/b", "snippet": "beta"},
    ], max_chars=500)

    assert result["ok"] is True
    assert "https://example.com/a" in result["evidence"]
    assert "alpha" in result["evidence"]


def test_mcp_lists_dev_search_tools():
    names = {tool["name"] for tool in TOOL_DEFINITIONS}

    assert "dev_search_docs" in names
    assert "dev_search_error" in names
    assert "dev_read_url" in names
    assert "dev_fetch_github_file" in names
    assert "dev_search_gitee" in names
    assert "dev_fetch_gitee_file" in names
    assert "dev_search_codesearch" in names
    assert "dev_summarize_sources" in names


def test_mcp_dev_search_codesearch_disabled(monkeypatch):
    monkeypatch.setenv("CODESEARCH_MCP_ENABLED", "0")
    result = handle_tool_call("dev_search_codesearch", {"query": "routing_engine"})
    assert result["ok"] is False
    assert result["tool"] == "dev_search_codesearch"
    assert result["error"] == "codesearch_disabled"


def test_should_codesearch_local():
    from search_gateway.policy import should_codesearch_local

    assert should_codesearch_local("where is routing_engine.py classify tier") is True
    assert should_codesearch_local("查一下 FastAPI 官方文档") is False


def test_mcp_dev_read_url_blocks_private_url_without_network():
    result = handle_tool_call("dev_read_url", {"url": "http://127.0.0.1:8080/admin"})

    assert result["ok"] is False
    assert result["error"] == "url_blocked"


def test_mcp_dev_search_docs_clamps_invalid_max_results(monkeypatch):
    import lima_mcp.tools as mcp_tools

    adapter = FakeAdapter()
    monkeypatch.setattr(mcp_tools, "_dev_adapter", lambda: adapter)

    result = handle_tool_call(
        "dev_search_docs",
        {"query": "FastAPI docs", "max_results": "not-an-int"},
    )

    assert result["ok"] is True
    assert adapter.calls[0] == ("search", "FastAPI docs", None, 5)


def test_mcp_dev_read_url_clamps_max_chars(monkeypatch):
    import lima_mcp.tools as mcp_tools

    adapter = FakeAdapter()
    monkeypatch.setattr(mcp_tools, "_dev_adapter", lambda: adapter)

    result = handle_tool_call(
        "dev_read_url",
        {"url": "https://docs.python.org/3/library/asyncio.html", "max_chars": 999999},
    )

    assert result["ok"] is True
    assert len(result["text"]) <= 12000


def test_build_prompt_evidence_includes_source_urls_and_tool_names():
    evidence = build_prompt_evidence([
        {
            "tool": "dev_search_docs",
            "results": [
                {
                    "title": "Python asyncio",
                    "url": "https://docs.python.org/3/library/asyncio.html",
                    "snippet": "asyncio runs coroutines",
                    "source": "search",
                }
            ],
        }
    ], max_chars=1000)

    assert evidence["ok"] is True
    assert "dev_search_docs" in evidence["evidence"]
    assert "https://docs.python.org" in evidence["evidence"]
    assert "asyncio runs coroutines" in evidence["evidence"]


def test_dev_search_gitee_skips_without_token(monkeypatch):
    import search_gateway.gitee_tools as gt

    monkeypatch.delenv("GITEE_TOKEN", raising=False)
    gt._git_remote_token = ""
    monkeypatch.setattr(gt, "gitee_token_from_git_remotes", lambda *a, **k: "")

    from search_gateway.dev_tools import search_gitee

    result = search_gitee("routing")
    assert result["ok"] is False
    assert result["tool"] == "dev_search_gitee"
    assert result.get("skipped") is True


def test_mcp_dev_search_gitee_returns_normalized_results(monkeypatch):
    import search_gateway.gitee_tools as gt

    monkeypatch.setenv("GITEE_TOKEN", "test-token")

    def fake_search(query, *, repo=None, max_results=5):
        return {
            "ok": True,
            "repo": repo or "zhuguang-cn/QWEN3.0",
            "results": [
                {
                    "title": "issue",
                    "url": "https://gitee.com/x/issues/1",
                    "snippet": "routing",
                    "source": "gitee_issue",
                    "repo": "zhuguang-cn/QWEN3.0",
                }
            ],
        }

    monkeypatch.setattr(gt, "search_gitee", fake_search)

    result = handle_tool_call("dev_search_gitee", {"query": "routing", "max_results": 3})
    assert result["ok"] is True
    assert result["tool"] == "dev_search_gitee"
    assert result["results"][0]["source"] == "gitee"


def test_mcp_dev_fetch_gitee_file(monkeypatch):
    import search_gateway.gitee_tools as gt

    monkeypatch.setenv("GITEE_TOKEN", "test-token")
    monkeypatch.setattr(
        gt,
        "fetch_repo_file",
        lambda repo, path, *, ref="master", max_chars=8000: {
            "ok": True,
            "text": "hello mirror",
            "repo": repo,
            "path": path,
        },
    )

    result = handle_tool_call(
        "dev_fetch_gitee_file",
        {"repo": "zhuguang-cn/QWEN3.0", "path": "README.md"},
    )
    assert result["ok"] is True
    assert result["text"] == "hello mirror"
