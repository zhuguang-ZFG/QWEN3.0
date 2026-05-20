"""
V3 路由模块本地测试
验证: 分类器 / 后端池选择 / 健康追踪 / 会话亲和
"""

import sys
import asyncio
sys.path.insert(0, ".")

import router_v3
import health_tracker
import sticky_session
import v3_integration


def test_classify():
    """测试请求分类器"""
    # Anthropic 格式 = IDE
    r = router_v3.classify_request("/v1/messages", {}, {})
    assert r["type"] == "ide", f"Expected ide, got {r['type']}"

    # OpenAI 格式 + Cursor UA = IDE
    r = router_v3.classify_request("/v1/chat/completions",
        {"user-agent": "cursor/1.0"}, {})
    assert r["type"] == "ide", f"Expected ide, got {r['type']}"

    # 普通请求 = chat
    r = router_v3.classify_request("/v1/chat/completions", {}, {})
    assert r["type"] == "chat", f"Expected chat, got {r['type']}"

    # system prompt 含 Cursor 指纹 = IDE
    r = router_v3.classify_request("/v1/chat/completions", {},
        {"messages": [{"role": "system", "content": "You are Cursor"}]})
    assert r["type"] == "ide", f"Expected ide, got {r['type']}"

    print("  classify_request: PASS")


def test_select_backends():
    """测试后端池选择"""
    hmap = {}
    # IDE 请求不含 chat_ubi
    backends = router_v3.select_backends("ide", hmap)
    assert "chat_ubi" not in backends, f"chat_ubi in IDE backends: {backends}"
    assert len(backends) > 0

    # Chat 请求: floor 层包含 chat_ubi (即使被 MAX_FALLBACKS 截断)
    all_chat = router_v3.POOLS["chat"]
    floor = all_chat.get("floor", [])
    assert "chat_ubi" in floor or "pollinations" in floor

    # Dead 后端被排除
    hmap = {"longcat_chat": "dead", "deepseek_flash": "dead"}
    backends = router_v3.select_backends("ide", hmap)
    assert "longcat_chat" not in backends
    assert "deepseek_flash" not in backends

    print("  select_backends: PASS")


def test_health_tracker():
    """测试健康追踪"""
    # 成功记录
    health_tracker.record_success("test_backend", 200.0)
    assert health_tracker.get_health("test_backend") == "healthy"

    # 429 = degraded, 不是 dead
    health_tracker.record_failure("test_429", error_code=429)
    assert health_tracker.get_health("test_429") == "degraded"

    # 400 不冷却
    health_tracker.record_failure("test_400", error_code=400)
    assert health_tracker.get_health("test_400") == "healthy"

    # 401 = suspicious
    health_tracker.record_failure("test_401", error_code=401)
    assert health_tracker.get_health("test_401") == "suspicious"

    # 冷却机制
    health_tracker.set_cooldown("cooled", ttl=1.0)
    assert health_tracker.is_cooled_down("cooled") == True
    assert health_tracker.is_cooled_down("not_cooled") == False

    print("  health_tracker: PASS")


def test_sticky_session():
    """测试会话亲和"""
    key = sticky_session.compute_key("model-a", '[{"role":"user","content":"hi"}]')
    assert key.startswith("model-a:")
    assert len(key) > 10

    # Pin and retrieve
    sticky_session.pin_backend(key, "backend_x")
    assert sticky_session.get_pinned_backend(key) == "backend_x"

    # Unpin
    sticky_session.unpin(key)
    assert sticky_session.get_pinned_backend(key) is None

    # 不同消息 = 不同 key
    key2 = sticky_session.compute_key("model-a", '[{"role":"user","content":"bye"}]')
    assert key != key2

    print("  sticky_session: PASS")


async def test_integration():
    """测试集成层"""
    call_count = {"n": 0}

    async def mock_backend(backend, messages, max_tokens):
        call_count["n"] += 1
        if backend == "longcat_chat":
            return "Hello from longcat_chat"
        raise Exception("backend unavailable")

    result = await v3_integration.handle_request_v3(
        query="test",
        messages=[{"role": "user", "content": "test"}],
        fmt="anthropic",
        ide_source="Claude Code",
        call_backend_fn=mock_backend,
    )
    assert result["backend"] == "longcat_chat"
    assert "Hello" in result["answer"]
    assert result["ms"] >= 0
    print("  v3_integration: PASS")


if __name__ == "__main__":
    print("=== V3 Router Tests ===")
    test_classify()
    test_select_backends()
    test_health_tracker()
    test_sticky_session()
    asyncio.run(test_integration())
    print("\nAll tests PASSED!")
