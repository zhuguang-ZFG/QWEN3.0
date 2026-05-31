import runtime_topology
import router_v3
from code_orchestrator_context import POOLS as CODE_POOLS
from reverse_gateway.errors import classify_error
from reverse_gateway.health import probe_provider
from reverse_gateway.providers.scnet import forward_chat, sidecar_health
from reverse_gateway.providers.scnet_adapter import attach_text_file, build_payload, extract_sse_text, message_transcript
from reverse_gateway.providers.scnet_cookie import REDACTED as COOKIE_REDACTED
from reverse_gateway.providers.scnet_cookie import load_cookie_state, write_cookie_state
from reverse_gateway.providers.scnet_protocol import REDACTED, ProtocolTemplate, load_template, write_redacted_capture
from reverse_gateway.registry import list_provider_status, provider_status
from routes.reverse_gateway import reverse_gateway_health, reverse_gateway_probe, reverse_gateway_provider


HOST_DEPENDENT_BACKENDS = {
    "deepseek_free",
    "ddg_gpt4o_mini",
    "ddg_gpt5_mini",
    "ddg_claude_haiku_45",
    "ddg_llama4",
    "ddg_mistral",
    "ddg_tinfoil_gptoss_120b",
    # M3: kimi VPS; M4: longcat VPS
    # M2: scnet_large/scnet_code now VPS sidecar
    "mimo_web",
    "mimo_web_think",
    "mimo_web_flash",
    "mimo_web_code",
    "mimo_web_think_code",
    # M1: local_* Ollama models removed
}


def _router_pool_names() -> set[str]:
    return {
        name
        for groups in router_v3.POOLS.values()
        for names in groups.values()
        for name in names
    } | set(router_v3.DIRECT_BACKENDS)


def _code_pool_names() -> set[str]:
    return {name for names in CODE_POOLS.values() for name in names}


def test_default_router_pools_exclude_host_dependent_backends():
    assert _router_pool_names().isdisjoint(HOST_DEPENDENT_BACKENDS)


def test_production_registry_excludes_host_dependent_backends():
    from backends_registry import BACKENDS, DISABLED_HOST_DEPENDENT_BACKENDS

    assert set(BACKENDS).isdisjoint(runtime_topology.LOCAL_ONLY_BACKENDS)
    assert HOST_DEPENDENT_BACKENDS.issubset(set(DISABLED_HOST_DEPENDENT_BACKENDS))


def test_code_orchestrator_pools_exclude_host_dependent_backends():
    assert _code_pool_names().isdisjoint(HOST_DEPENDENT_BACKENDS)


def test_host_dependent_backends_require_explicit_opt_in(monkeypatch):
    monkeypatch.delenv(runtime_topology.HOST_DEPENDENT_OPT_IN, raising=False)
    monkeypatch.setenv("SCNET_LARGE_TUNNEL_URL", "http://127.0.0.1:4505")

    # M2/M3: scnet_large + kimi now VPS sidecars. Use ddg (still host-dependent).
    assert not runtime_topology.backend_available("ddg_gpt4o_mini")
    assert runtime_topology.backend_available("scnet_ds_flash")


def test_reverse_gateway_registry_starts_disabled():
    statuses = list_provider_status()

    assert statuses
    # M2: scnet ready; M3: kimi ready; M4: longcat ready
    assert provider_status("scnet_large")["status"] == "ready_protocol_adapter"
    assert provider_status("kimi_web")["status"] == "ready_proxy_shell"
    assert provider_status("longcat_web")["status"] == "ready_proxy_shell"


def test_reverse_gateway_health_endpoint_payload():
    payload = reverse_gateway_health()

    assert payload["status"] == "ok"
    assert payload["routing_policy"] == "disabled_until_adapter_health_and_eval"
    assert any(item["name"] == "scnet_large" for item in payload["providers"])
    assert payload["probes"]["scnet_large"]["status"] == "disabled_no_adapter"


def test_reverse_gateway_provider_endpoint_payload():
    payload = reverse_gateway_provider("mimo_web")

    assert payload["port"] == 4507
    assert "mimo_web" in payload["backends"]


def test_scnet_probe_is_disabled_until_adapter_exists():
    probe = probe_provider("scnet_large")

    assert probe["healthy"] is False
    assert probe["status"] == "disabled_no_adapter"
    assert probe["error_class"] == "disabled_no_adapter"
    assert reverse_gateway_probe("scnet_large") == probe


def test_scnet_sidecar_health_is_openai_shell_only():
    payload = sidecar_health()

    assert payload["port"] == 4505
    assert payload["probe"]["status"] == "disabled_no_adapter"


def test_scnet_forward_chat_returns_503_until_enabled(monkeypatch):
    monkeypatch.delenv("SCNET_REVERSE_ENABLED", raising=False)
    monkeypatch.delenv("SCNET_REVERSE_UPSTREAM_URL", raising=False)

    status_code, payload = forward_chat({"messages": []})

    assert status_code == 503
    assert payload["error"]["type"] == "disabled_no_adapter"


def test_scnet_probe_requires_upstream_when_enabled(monkeypatch):
    monkeypatch.setenv("SCNET_REVERSE_ENABLED", "1")
    monkeypatch.delenv("SCNET_REVERSE_UPSTREAM_URL", raising=False)

    probe = probe_provider("scnet_large")

    assert probe["healthy"] is False
    assert probe["status"] == "disabled_missing_protocol"


def test_scnet_forward_chat_requires_upstream_when_enabled(monkeypatch):
    monkeypatch.setenv("SCNET_REVERSE_ENABLED", "1")
    monkeypatch.delenv("SCNET_REVERSE_UPSTREAM_URL", raising=False)

    status_code, payload = forward_chat({"messages": []})

    assert status_code == 503
    assert payload["error"]["type"] == "protocol_error"


def test_scnet_probe_requires_cookies_with_protocol(monkeypatch, tmp_path):
    output = tmp_path / "scnet_protocol.json"
    write_redacted_capture(
        {
            "endpoint": "https://www.scnet.cn/acx/chatbot/v1/chat",
            "headers": {},
            "payload_template": {"content": "", "modelId": 520},
        },
        output,
    )
    monkeypatch.setenv("SCNET_REVERSE_ENABLED", "1")
    monkeypatch.setenv("SCNET_REVERSE_PROTOCOL_PATH", str(output))
    monkeypatch.delenv("SCNET_REVERSE_UPSTREAM_URL", raising=False)

    probe = probe_provider("scnet_large")

    assert probe["healthy"] is False
    assert probe["status"] == "disabled_missing_cookies"


def test_scnet_forward_chat_proxies_explicit_upstream(monkeypatch):
    from reverse_gateway.config import ProviderConfig
    import reverse_gateway.providers.scnet as scnet

    class Response:
        status_code = 200
        text = '{"ok": true}'

        def json(self):
            return {"ok": True}

    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return Response()

    monkeypatch.setattr(scnet.httpx, "post", fake_post)
    cfg = ProviderConfig(
        enabled=True,
        upstream_url="http://127.0.0.1:4999/v1/chat/completions",
        max_concurrency=1,
        timeout_seconds=3.0,
        file_context_enabled=False,
        file_context_threshold_chars=10000,
        file_context_chunk_chars=45000,
        file_context_max_files=30,
        file_context_max_total_chars=50000,
    )

    status_code, payload = forward_chat({"messages": []}, cfg=cfg)

    assert status_code == 200
    assert payload == {"ok": True}
    assert calls[0][0] == cfg.upstream_url


def test_scnet_forward_chat_uses_protocol_template(monkeypatch, tmp_path):
    import reverse_gateway.providers.scnet as scnet

    protocol = tmp_path / "scnet_protocol.json"
    cookies = tmp_path / "scnet_cookies.json"
    write_redacted_capture(
        {
            "endpoint": "https://www.scnet.cn/acx/chatbot/v1/chat",
            "headers": {"User-Agent": "pytest"},
            "payload_template": {"content": "", "modelId": 520, "history": [], "tools": []},
        },
        protocol,
    )
    write_cookie_state([{"name": "Token", "value": "secret-token"}], cookies)
    monkeypatch.setenv("SCNET_REVERSE_ENABLED", "1")
    monkeypatch.setenv("SCNET_REVERSE_PROTOCOL_PATH", str(protocol))
    monkeypatch.setenv("SCNET_REVERSE_COOKIE_PATH", str(cookies))

    class Response:
        status_code = 200
        text = '{"code":"0","data":{"content":"pong"}}'

        def json(self):
            return {"code": "0", "data": {"content": "pong"}}

    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return Response()

    monkeypatch.setattr(scnet.httpx, "post", fake_post)

    status_code, payload = forward_chat(
        {
            "model": "scnet-large",
            "messages": [{"role": "user", "content": "ping"}],
            "tools": [{"type": "mcp", "name": "repo"}],
        }
    )

    assert status_code == 200
    assert payload["choices"][0]["message"]["content"] == "pong"
    assert calls[0][0] == "https://www.scnet.cn/acx/chatbot/v1/chat"
    assert calls[0][1]["Cookie"] == "Token=secret-token"
    assert calls[0][2]["content"] == "ping"
    assert calls[0][2]["history"] == [{"role": "user", "content": "ping"}]
    assert calls[0][2]["tools"] == [{"type": "mcp", "name": "repo"}]



def test_scnet_forward_chat_bridges_long_context_file(monkeypatch, tmp_path):
    import reverse_gateway.providers.scnet as scnet

    protocol = tmp_path / "scnet_protocol.json"
    cookies = tmp_path / "scnet_cookies.json"
    write_redacted_capture(
        {
            "endpoint": "https://www.scnet.cn/acx/chatbot/v1/chat/completion",
            "headers": {"User-Agent": "pytest"},
            "payload_template": {"content": "", "modelId": 520, "textFile": [], "imageFile": []},
        },
        protocol,
    )
    write_cookie_state([{"name": "Token", "value": "secret-token"}], cookies)
    monkeypatch.setenv("SCNET_REVERSE_ENABLED", "1")
    monkeypatch.setenv("SCNET_REVERSE_PROTOCOL_PATH", str(protocol))
    monkeypatch.setenv("SCNET_REVERSE_COOKIE_PATH", str(cookies))
    monkeypatch.setenv("SCNET_REVERSE_ENABLE_FILE_CONTEXT", "1")
    monkeypatch.setenv("SCNET_REVERSE_FILE_CONTEXT_THRESHOLD_CHARS", "10")

    class Response:
        status_code = 200
        text = '{"code":"0","data":{"content":"bridged"}}'

        def json(self):
            return {"code": "0", "data": {"content": "bridged"}}

    uploaded = []
    calls = []

    class Uploaded:
        def __init__(self, name):
            self.name = name

        def as_payload(self):
            return {
                "name": self.name,
                "path": f"https://acx-ai.oss-cn-hangzhou.aliyuncs.com/dir/{self.name}",
                "size": 42,
                "type": "text/plain",
            }

    def fake_upload(content, headers, timeout, chunk_chars, max_files, max_total_chars):
        uploaded.append((content, headers, timeout, chunk_chars, max_files, max_total_chars))
        return [Uploaded("lima_context_001.txt"), Uploaded("lima_context_002.txt")]

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return Response()

    monkeypatch.setattr(scnet, "upload_text_context_chunks", fake_upload)
    monkeypatch.setattr(scnet.httpx, "post", fake_post)

    status_code, payload = forward_chat({"messages": [{"role": "user", "content": "A" * 20}]})

    assert status_code == 200
    assert payload["choices"][0]["message"]["content"] == "bridged"
    assert uploaded[0][0] == "A" * 20
    assert uploaded[0][3] == 45000
    assert uploaded[0][4] == 30
    assert uploaded[0][5] == 50000
    assert calls[0][2]["content"] == "????????????????????????????????"
    assert calls[0][2].get("history") in (None, [])
    assert calls[0][2]["textFile"] == [
        {
            "name": "lima_context_001.txt",
            "path": "https://acx-ai.oss-cn-hangzhou.aliyuncs.com/dir/lima_context_001.txt",
            "size": 42,
            "type": "text/plain",
        },
        {
            "name": "lima_context_002.txt",
            "path": "https://acx-ai.oss-cn-hangzhou.aliyuncs.com/dir/lima_context_002.txt",
            "size": 42,
            "type": "text/plain",
        },
    ]



def test_scnet_long_context_above_web_limit_fails_fast(monkeypatch, tmp_path):
    protocol = tmp_path / "scnet_protocol.json"
    cookies = tmp_path / "scnet_cookies.json"
    write_redacted_capture(
        {
            "endpoint": "https://www.scnet.cn/acx/chatbot/v1/chat/completion",
            "headers": {},
            "payload_template": {"content": "", "modelId": 520, "textFile": []},
        },
        protocol,
    )
    write_cookie_state([{"name": "Token", "value": "secret-token"}], cookies)
    monkeypatch.setenv("SCNET_REVERSE_ENABLED", "1")
    monkeypatch.setenv("SCNET_REVERSE_PROTOCOL_PATH", str(protocol))
    monkeypatch.setenv("SCNET_REVERSE_COOKIE_PATH", str(cookies))
    monkeypatch.setenv("SCNET_REVERSE_ENABLE_FILE_CONTEXT", "1")
    monkeypatch.setenv("SCNET_REVERSE_FILE_CONTEXT_THRESHOLD_CHARS", "10")
    monkeypatch.setenv("SCNET_REVERSE_FILE_CONTEXT_MAX_TOTAL_CHARS", "20")

    status_code, payload = forward_chat({"messages": [{"role": "user", "content": "A" * 30}]})

    assert status_code == 502
    assert payload["error"]["type"] in {"protocol_error", "upstream_error"}
    assert "Use retrieval/MCP chunk selection" in payload["error"]["message"]


def test_scnet_sidecar_health_reports_config(monkeypatch):
    monkeypatch.setenv("SCNET_REVERSE_MAX_CONCURRENCY", "2")

    payload = sidecar_health()

    assert payload["config"]["max_concurrency"] >= 1
    assert payload["config"]["upstream_configured"] is False


def test_scnet_protocol_capture_redacts_secrets(tmp_path):
    output = tmp_path / "scnet_protocol.json"

    write_redacted_capture(
        {
            "endpoint": "https://example.test/chat",
            "method": "POST",
            "headers": {
                "Authorization": "Bearer secret",
                "Cookie": "session=secret",
                "User-Agent": "test-agent",
            },
            "payload_template": {"model": "deepseek-v4-pro"},
            "stream": True,
        },
        output,
    )
    text = output.read_text(encoding="utf-8")

    assert "secret" not in text
    assert f'"Authorization": "{REDACTED}"' in text
    template = load_template(output)
    assert template.endpoint == "https://example.test/chat"
    assert template.stream is True


def test_scnet_sidecar_health_reports_loaded_protocol(monkeypatch, tmp_path):
    output = tmp_path / "scnet_protocol.json"
    write_redacted_capture(
        {
            "endpoint": "https://example.test/chat",
            "headers": {"Authorization": "Bearer secret"},
            "payload_template": {"model": "deepseek-v4-flash"},
        },
        output,
    )
    monkeypatch.setenv("SCNET_REVERSE_PROTOCOL_PATH", str(output))
    monkeypatch.delenv("SCNET_REVERSE_ENABLED", raising=False)

    payload = sidecar_health()

    assert payload["probe"]["status"] == "disabled_no_adapter"
    assert payload["config"]["protocol_template_loaded"] is True
    assert payload["config"]["protocol_template"]["headers"]["Authorization"] == REDACTED


def test_scnet_cookie_state_redacts_sensitive_values(tmp_path):
    path = tmp_path / "scnet_cookies.json"
    state = write_cookie_state(
        [
            {"name": "Token", "value": "secret-token", "domain": "www.scnet.cn"},
            {"name": "jsessionid", "value": "secret-session", "domain": "www.scnet.cn"},
            {"name": "language", "value": "zh", "domain": "www.scnet.cn"},
        ],
        path,
    )

    assert "Token=secret-token" in state.cookie_header()
    redacted = load_cookie_state(path).redacted()
    assert redacted[0]["value"] == COOKIE_REDACTED
    assert redacted[1]["value"] == COOKIE_REDACTED
    assert redacted[2]["value"] == "zh"


def test_scnet_sidecar_health_reports_cookie_state_without_secrets(monkeypatch, tmp_path):
    path = tmp_path / "scnet_cookies.json"
    write_cookie_state(
        [
            {"name": "Token", "value": "secret-token", "domain": "www.scnet.cn"},
            {"name": "language", "value": "zh", "domain": "www.scnet.cn"},
        ],
        path,
    )
    monkeypatch.setenv("SCNET_REVERSE_COOKIE_PATH", str(path))

    payload = sidecar_health()
    text = str(payload)

    assert payload["config"]["cookie_state_loaded"] is True
    assert payload["config"]["cookie_count"] == 2
    assert "secret-token" not in text
    assert COOKIE_REDACTED in text


def test_scnet_payload_supports_long_context_and_tools():
    template = ProtocolTemplate(
        endpoint="https://www.scnet.cn/acx/chatbot/v1/chat",
        method="POST",
        headers={},
        payload_template={
            "content": "",
            "history": [],
            "modelId": 520,
            "tools": [],
            "mcpServers": [],
        },
    )

    body = {
        "model": "DeepSeek-V4-Pro",
        "messages": [
            {"role": "system", "content": "use repo context"},
            {"role": "user", "content": "A" * 10000},
        ],
        "tools": [{"type": "function", "function": {"name": "search"}}],
        "mcp_servers": [{"name": "codegraph"}],
    }

    payload = build_payload(template, body)

    assert payload["content"] == "A" * 10000
    assert payload["history"] == message_transcript(body)
    assert payload["tools"] == body["tools"]
    assert payload["mcpServers"] == body["mcp_servers"]



def test_scnet_payload_defaults_online_enabled():
    template = ProtocolTemplate(
        endpoint="https://www.scnet.cn/acx/chatbot/v1/chat/completion",
        method="POST",
        headers={},
        payload_template={"content": "", "onlineEnable": False, "modelId": 17},
    )

    payload = build_payload(template, {"messages": [{"role": "user", "content": "ping"}]})

    assert payload["onlineEnable"] is True


def test_scnet_attach_text_file_replaces_prompt():
    payload = {"content": "original", "textFile": [], "history": [{"role": "user", "content": "large"}]}

    attach_text_file(
        payload,
        {"name": "ctx.txt", "path": "https://example.test/ctx.txt", "size": 12, "type": "text/plain"},
        "read attached context",
    )

    assert payload["content"] == "read attached context"
    assert payload["history"] == []
    assert payload["textFile"][0]["name"] == "ctx.txt"


def test_scnet_model_aliases_map_to_model_ids():
    template = ProtocolTemplate(
        endpoint="https://www.scnet.cn/acx/chatbot/v1/chat/completion",
        method="POST",
        headers={},
        payload_template={"content": "", "modelId": 17},
    )

    payload = build_payload(
        template,
        {"model": "deepseek-v4-pro", "messages": [{"role": "user", "content": "ping"}]},
    )

    assert payload["modelId"] == 510


def test_scnet_sse_response_extracts_incremental_content():
    text = 'data:{"content":"hello"}\n\ndata:{"content":" world"}\n\ndata:{"content":"[done]"}\n\n'

    assert extract_sse_text(text) == "hello world"


def test_reverse_error_classifier():
    assert classify_error("anonymous_usage_exceeded") == "quota_exceeded"
    assert classify_error("captcha required") == "captcha_required"
    assert classify_error("401 unauthorized session") == "auth_expired"
    assert classify_error("429 too many requests") == "rate_limited"
