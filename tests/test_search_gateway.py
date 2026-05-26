from search_gateway.anysearch_adapter import AnySearchAdapter
from search_gateway.policy import should_search
from search_gateway.safety import redact_sensitive_query


def test_should_search_only_for_explicit_realtime_or_url_requests():
    assert should_search("search latest Cohere pricing") is True
    assert should_search("read https://example.com/docs") is True
    assert should_search("查一下今天的模型状态") is True
    assert should_search("why did routing_engine.select fail?") is False


def test_redact_sensitive_query_removes_tokens_paths_and_private_ips():
    fake_secret = "sk-" + "abc123456789xyz"
    query = f"error token {fake_secret} path D:\\GIT\\.env host 192.168.1.10"
    redacted = redact_sensitive_query(query)

    assert "sk-" not in redacted
    assert "D:\\GIT" not in redacted
    assert "192.168.1.10" not in redacted
    assert "[REDACTED_TOKEN]" in redacted
    assert "[REDACTED_PATH]" in redacted
    assert "[REDACTED_PRIVATE_IP]" in redacted


def test_anysearch_adapter_uses_injected_transport_with_sanitized_query():
    calls = []

    def transport(payload):
        calls.append(payload)
        return {"ok": True, "results": [{"title": "Doc", "url": "https://example.com"}]}

    adapter = AnySearchAdapter(transport=transport)
    fake_secret = "sk-" + "abc123456789xyz"
    result = adapter.search(f"latest docs token {fake_secret}", max_results=3)

    assert result["ok"] is True
    assert calls[0]["method"] == "search"
    assert calls[0]["params"]["max_results"] == 3
    assert "sk-" not in calls[0]["params"]["query"]


def test_anysearch_adapter_supports_domain_limited_batch_search():
    calls = []

    def transport(payload):
        calls.append(payload)
        return {"ok": True, "results": []}

    adapter = AnySearchAdapter(transport=transport)
    result = adapter.batch_search(
        ["latest FastAPI release", "site docs " + "sk-" + "abc123456789xyz"],
        domain="docs",
        max_results=2,
    )

    assert result == {"ok": True, "results": []}
    assert calls[0]["method"] == "batch_search"
    assert calls[0]["params"]["domain"] == "docs"
    assert calls[0]["params"]["max_results"] == 2
    assert all("sk-" not in query for query in calls[0]["params"]["queries"])


def test_anysearch_adapter_extract_url_uses_extract_method():
    calls = []

    def transport(payload):
        calls.append(payload)
        return {"ok": True, "text": "hello"}

    adapter = AnySearchAdapter(transport=transport)
    result = adapter.extract_url("https://example.com/docs")

    assert result == {"ok": True, "text": "hello"}
    assert calls[0] == {
        "method": "extract_url",
        "params": {"url": "https://example.com/docs"},
    }


def test_searxng_adapter_normalizes_results():
    calls = []

    def fake_http(url: str) -> dict:
        calls.append(url)
        return {
            "results": [
                {
                    "title": "FastAPI Depends",
                    "url": "https://fastapi.tiangolo.com/tutorial/dependencies/",
                    "content": "Depends snippet",
                    "engine": "google",
                }
            ]
        }

    from search_gateway.searxng_adapter import SearXNGAdapter

    adapter = SearXNGAdapter(base_url="http://127.0.0.1:8081")
    adapter._http_get_json = fake_http  # type: ignore[method-assign]
    result = adapter.search("FastAPI Depends", max_results=2)

    assert result["ok"] is True
    assert result["results"][0]["source"] == "searxng:google"
    assert "format=json" in calls[0]


def test_dev_adapter_fallback_to_tinyfish(monkeypatch):
    monkeypatch.setenv("SEARXNG_ENABLED", "1")
    monkeypatch.setenv("SEARXNG_BASE_URL", "http://127.0.0.1:59999")

    from search_gateway.dev_adapter import get_dev_search_adapter

    adapter = get_dev_search_adapter()
    result = adapter.search("test query", max_results=2)
    assert "ok" in result
