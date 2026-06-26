"""route() main flow tests."""

from unittest.mock import ANY, MagicMock, patch

from routing_engine import route


def test_route_identity_detection_path():
    """测试 route() 函数的身份检测路径

    验证 route 函数正确处理身份检测的特殊路径
    """
    with patch("routing_engine_helpers.identity_guard") as mock_identity_guard:
        mock_identity_guard.detect_identity_question.return_value = "You are an assistant"

        result = route(
            query="Who are you?",
            messages=[{"role": "user", "content": "test"}],
            channel_role="test_role",
        )

        mock_identity_guard.detect_identity_question.assert_called_once_with("Who are you?", channel_role="test_role")

        assert result.backend == "identity_guard"
        assert result.answer == "You are an assistant"
        assert result.request_type == "identity"


@patch("routing_engine_helpers.identity_guard")
@patch("routing_engine_execute_strategy.health_tracker")
@patch("routing_engine_execute_strategy.budget_manager")
@patch("routing_engine_execute_strategy.speculative")
@patch("routing_engine.classify")
@patch("routing_engine.classify_scenario")
@patch("routing_engine.select")
@patch("routing_engine_execute_strategy.execute")
def test_route_full_pipeline_with_call_fn_mock(
    mock_execute,
    mock_select,
    mock_classify_scenario,
    mock_classify,
    mock_speculative,
    mock_budget,
    mock_health,
    mock_identity,
):
    """测试 route() 函数的完整管道流程

    验证 route 函数在 call_fn 存在时正确执行完整管道
    """
    mock_identity.detect_identity_question.return_value = ""
    mock_speculative.classify_complexity.return_value = "normal"
    mock_health.is_cooled_down.return_value = False
    mock_budget.is_budget_available.return_value = True
    mock_classify.return_value = "chat"
    mock_classify_scenario.return_value = "general"
    mock_select.return_value = ["backend1", "backend2"]
    mock_execute.return_value = ("backend1", "final answer", None)

    mock_call_fn = MagicMock(return_value="backend1 response")

    with patch("routing_engine_intent.analyze_intent") as mock_analyze_intent:
        mock_analyze_intent.return_value = {"intent": "device_stop"}
        result = route(
            query="test query",
            messages=[{"role": "user", "content": "test message"}],
            call_fn=mock_call_fn,
        )

    mock_classify.assert_called_once()
    mock_classify_scenario.assert_called_once()
    mock_select.assert_called_once()
    mock_execute.assert_called_once()

    assert result.backend == "backend1"
    assert result.answer == "final answer"
    assert result.request_type == "chat"
    assert result.scenario == "device_control"


@patch("routing_engine.classify")
@patch("routing_engine.classify_scenario")
@patch("routing_engine_execute_strategy.health_tracker")
@patch("routing_engine_execute_strategy.budget_manager")
@patch("routing_engine_execute_strategy.speculative")
@patch("routing_engine_execute_strategy.execute")
@patch("routing_engine.select")
def test_route_speculative_execution_fallback_on_runtimeerror(
    mock_select,
    mock_execute,
    mock_speculative,
    mock_budget_manager,
    mock_health_tracker,
    mock_classify_scenario,
    mock_classify,
):
    """测试 route() 函数的 speculative 执行回退机制

    验证当 speculative.speculative_call 抛出 RuntimeError 时
    route 函数正确回退到 execute
    """
    mock_classify.return_value = "chat"
    mock_classify_scenario.return_value = "chat"
    mock_select.return_value = ["backend1", "backend2"]
    mock_speculative.classify_complexity.return_value = "simple"
    mock_speculative.get_affinity_backends.return_value = ["fast_backend1", "fast_backend2"]
    mock_health_tracker.is_cooled_down.return_value = False
    mock_budget_manager.is_budget_available.return_value = True
    mock_speculative.is_historically_fast.return_value = True

    mock_speculative.speculative_call.side_effect = RuntimeError("speculative failed")
    mock_execute.return_value = ("fallback_backend", "fallback answer", None)

    mock_call_fn = MagicMock(return_value="test response")

    result = route(
        query="test query",
        messages=[{"role": "user", "content": "test message"}],
        call_fn=mock_call_fn,
        needs_tools=False,
    )

    mock_speculative.speculative_call.assert_called_once()
    mock_execute.assert_called_once()

    assert result.backend == "fallback_backend"


@patch("routing_engine_execute_strategy.sticky_session")
@patch("routing_engine.sticky_session")
def test_route_sticky_session_integration(mock_sticky_session, mock_exec_sticky):
    """测试 route() 函数的 sticky_session 集成

    验证 route 函数正确调用 sticky_session.compute_key 和 pin_backend
    """
    mock_sticky_session.compute_key.return_value = "sticky_key_123"
    mock_exec_sticky.pin_backend = mock_sticky_session.pin_backend

    mock_call_fn = MagicMock(return_value="test response")

    route(
        query="test query",
        messages=[{"role": "user", "content": "test message"}],
        call_fn=mock_call_fn,
        model="test_model",
    )

    mock_sticky_session.compute_key.assert_called_once_with("test_model", ANY)
    assert mock_sticky_session.pin_backend.call_count == 1


def test_route_identity_question_with_empty_answer():
    """测试 route() 函数身份检测空答案的情况

    验证 route 函数当身份检测返回空答案时正确处理
    """
    mock_identity_guard = MagicMock()
    mock_identity_guard.detect_identity_question.return_value = "Test identity"

    with patch("routing_engine_helpers.identity_guard", mock_identity_guard):
        result = route(
            query="Who are you?",
            messages=[{"role": "user", "content": "test"}],
            channel_role="test_role",
        )

    assert result.backend == "identity_guard"
    assert result.answer == "Test identity"


def test_route_semantic_cache_hits_on_second_identical_query(monkeypatch, tmp_path):
    """测试 route() 在启用语义缓存时，第二次相同查询命中缓存。"""
    import os
    import tempfile

    from semantic_cache.cache import SemanticCache

    db_path = tmp_path / "semantic_cache.db"
    monkeypatch.setenv("LIMA_SEMANTIC_CACHE_ENABLED", "1")
    monkeypatch.setenv("LIMA_SEMANTIC_CACHE_DB", str(db_path))
    monkeypatch.setenv("LIMA_SEMANTIC_CACHE_THRESHOLD", "0.95")

    # Use a deterministic fake embedder so identical queries always hit.
    cache = SemanticCache()
    with patch("routing_engine_cache.get_cache", return_value=cache):
        with patch("routing_engine_helpers.identity_guard") as mock_identity:
            mock_identity.detect_identity_question.return_value = ""
            first = route(
                query="hello",
                messages=[{"role": "user", "content": "hello"}],
                call_fn=MagicMock(return_value="backend answer"),
            )
            assert first.answer == "backend answer"

            # Second call without call_fn should still return cached answer.
            second = route(
                query="hello",
                messages=[{"role": "user", "content": "hello"}],
            )
            assert second.answer == "backend answer"
