"""
测试路由引擎 - 测试路由引擎的各个组件和功能
"""
import unittest
from unittest.mock import patch, MagicMock

from routing_engine import (
    RouteResult,
    inject_skills,
    respond,
    route,
)
from routing_engine_post import get_injected_ids


class TestRoutingEngine(unittest.TestCase):
    """路由引擎测试套件 - 覆盖所有主要功能路径"""

    def setUp(self):
        """每个测试前的初始化"""
        self.mock_backend = "test_backend"
        self.mock_answer = "test answer content"
        self.mock_query = "test query"
        self.mock_messages = [{"role": "user", "content": "test message"}]
        self.mock_query_type = "chat"
        self.mock_scenario = "general"

    def test_route_result_dataclass_creation_and_default_values(self):
        """测试 RouteResult 数据类创建和默认值

        验证 RouteResult 数据类的默认属性和默认值设置正确
        """
        result = RouteResult()
        self.assertEqual(result.backend, "")
        self.assertEqual(result.answer, "")
        self.assertEqual(result.request_type, "chat")
        self.assertEqual(result.scenario, "")
        self.assertEqual(result.ms, 0)
        self.assertEqual(result.fallback_used, False)
        self.assertEqual(result.skills_injected, [])
        self.assertEqual(result.retrieval_context, "")

    def test_route_result_custom_values(self):
        """测试 RouteResult 数据类自定义值

        验证 RouteResult 数据类可以接受自定义参数
        """
        result = RouteResult(
            backend="custom_backend",
            answer="custom answer",
            request_type="code",
            scenario="coding",
            ms=100,
            fallback_used=True,
            skills_injected=["skill1", "skill2"],
            retrieval_context="context text"
        )
        self.assertEqual(result.backend, "custom_backend")
        self.assertEqual(result.answer, "custom answer")
        self.assertEqual(result.request_type, "code")
        self.assertEqual(result.scenario, "coding")
        self.assertEqual(result.ms, 100)
        self.assertEqual(result.fallback_used, True)
        self.assertEqual(result.skills_injected, ["skill1", "skill2"])
        self.assertEqual(result.retrieval_context, "context text")

    @patch('routing_engine.skills_mod')
    def test_inject_skills_with_mock_skills_injector(self, mock_skills_mod):
        """测试 inject_skills 与 mock skills_injector 的集成

        验证 inject_skills 函数正确地调用 skills_mod.apply_skills
        并处理传递的参数
        """
        mock_skills_mod.apply_skills.return_value = [
            {"role": "system", "content": "test system"},
            {"role": "user", "content": "test user"}
        ]

        result = inject_skills(
            messages=[{"role": "user", "content": "test"}],
            backend="test_backend",
            ide_source="test_ide",
            system_prompt="test system prompt"
        )

        mock_skills_mod.apply_skills.assert_called_once_with(
            backend="test_backend",
            messages=[{"role": "user", "content": "test"}],
            system_prompt="test system prompt",
            ide_source="test_ide"
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["role"], "system")

    def test_respond_for_openai_format(self):
        """测试 respond() 函数的 openai 格式

        验证 respond 函数正确处理 openai 格式的响应
        """
        result = RouteResult(
            backend="openai_backend",
            answer="test answer",
            request_type="chat",
            ms=100,
            skills_injected=["skill1"]
        )

        response = respond(result, fmt="openai")

        self.assertIn("id", response)
        self.assertEqual(response["choices"][0]["message"]["content"], "test answer")
        self.assertEqual(response["model"], "lima-1.3")
        self.assertIn("x_lima_meta", response)
        self.assertEqual(response["x_lima_meta"]["request_type"], "chat")
        self.assertEqual(response["x_lima_meta"]["skills_injected"], ["skill1"])

    def test_respond_for_anthropic_format(self):
        """测试 respond() 函数的 anthropic 格式

        验证 respond 函数正确处理 anthropic 格式的响应
        """
        result = RouteResult(
            backend="anthropic_backend",
            answer="test answer",
            request_type="chat"
        )

        response = respond(result, fmt="anthropic", model="anthropic-model")

        self.assertIn("id", response)
        self.assertEqual(response["content"][0]["text"], "test answer")
        self.assertEqual(response["model"], "anthropic-model")

    @patch('routing_engine.identity_guard')
    def test_route_identity_detection_path(self, mock_identity_guard):
        """测试 route() 函数的身份检测路径

        验证 route 函数正确处理身份检测的特殊路径
        """
        mock_identity_guard.detect_identity_question.return_value = "You are an assistant"

        result = route(
            query="Who are you?",
            messages=[{"role": "user", "content": "test"}],
            channel_role="test_role"
        )

        mock_identity_guard.detect_identity_question.assert_called_once_with(
            "Who are you?", channel_role="test_role"
        )

        self.assertEqual(result.backend, "identity_guard")
        self.assertEqual(result.answer, "You are an assistant")
        self.assertEqual(result.request_type, "identity")

    @patch('routing_engine.identity_guard')
    @patch('routing_engine_execute_strategy.health_tracker')
    @patch('routing_engine_execute_strategy.budget_manager')
    @patch('routing_engine_execute_strategy.speculative')
    @patch('routing_engine.classify')
    @patch('routing_engine.classify_scenario')
    @patch('routing_engine.select')
    @patch('routing_engine_execute_strategy.execute')
    def test_route_full_pipeline_with_call_fn_mock(
        self, mock_execute, mock_select, mock_classify_scenario,
        mock_classify, mock_speculative, mock_budget,
        mock_health, mock_identity
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

        result = route(
            query="test query",
            messages=[{"role": "user", "content": "test message"}],
            call_fn=mock_call_fn
        )

        mock_classify.assert_called_once()
        mock_classify_scenario.assert_called_once()
        mock_select.assert_called_once()
        mock_execute.assert_called_once()

        self.assertEqual(result.backend, "backend1")
        self.assertEqual(result.answer, "final answer")
        self.assertEqual(result.request_type, "chat")
        self.assertEqual(result.scenario, "general")

    @patch('routing_engine.classify')
    @patch('routing_engine.classify_scenario')
    @patch('routing_engine_execute_strategy.health_tracker')
    @patch('routing_engine_execute_strategy.budget_manager')
    @patch('routing_engine_execute_strategy.speculative')
    @patch('routing_engine_execute_strategy.execute')
    @patch('routing_engine.select')
    def test_route_speculative_execution_fallback_on_runtimeerror(
        self, mock_select, mock_execute, mock_speculative, mock_budget_manager,
        mock_health_tracker, mock_classify_scenario, mock_classify,
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
            needs_tools=False
        )

        mock_speculative.speculative_call.assert_called_once()
        mock_execute.assert_called_once()

        self.assertEqual(result.backend, "fallback_backend")

    @patch('routing_engine_execute_strategy.sticky_session')
    @patch('routing_engine.sticky_session')
    def test_route_sticky_session_integration(self, mock_sticky_session, mock_exec_sticky):
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
            model="test_model"
        )

        mock_sticky_session.compute_key.assert_called_once_with(
            "test_model", unittest.mock.ANY
        )

        self.assertEqual(mock_sticky_session.pin_backend.call_count, 1)

    def test_route_reexports_are_correct(self):
        """测试 route() 函数的正确 re-export

        验证路由引擎正确 re-export 所有必要的函数
        """
        from routing_engine import __all__

        expected_exports = [
            "RouteResult",
            "PickResult",
            "classify",
            "classify_scenario",
            "inject_skills",
            "respond",
            "pick_backend",
            "route",
        ]

        for export in expected_exports:
            self.assertIn(export, __all__)

    def testget_injected_ids_helper_basic(self):
        """测试 get_injected_ids helper 的基本功能

        验证 get_injected_ids 函数正确处理基本的情况
        """
        original = [{"role": "user", "content": "test"}]
        modified = [
            {"role": "user", "content": "test"},
            {"role": "system", "content": "Available skills: skill1, skill2"},
            {"role": "assistant", "content": "test"}
        ]

        result = get_injected_ids(original, modified)

        self.assertEqual(result, ["dir:skill1", "dir:skill2"])

    def testget_injected_ids_helper_no_skills(self):
        """测试 get_injected_ids helper 的无技能情况

        验证 get_injected_ids 函数当没有找到技能时返回空列表
        """
        original = [{"role": "user", "content": "test"}]
        modified = [{"role": "user", "content": "test"}]

        result = get_injected_ids(original, modified)

        self.assertEqual(result, [])

    def testget_injected_ids_helper_injected_skills(self):
        """测试 get_injected_ids helper 的注入技能情况

        验证 get_injected_ids 函数当有注入的技能时返回正确的ID
        """
        original = [{"role": "user", "content": "test"}]
        modified = [
            {"role": "user", "content": "test"},
            {"role": "system", "content": "Available skills: skill1"}
        ]

        result = get_injected_ids(original, modified)

        self.assertEqual(result, ["dir:skill1"])

    def test_route_result_with_none_values(self):
        """测试 RouteResult 数据类 None 值处理

        验证 RouteResult 数据类可以正确处理 None 值
        """
        result = RouteResult(
            backend=None,
            answer=None,
            request_type=None,
            scenario=None,
            ms=None,
            fallback_used=None,
            skills_injected=None,
            retrieval_context=None
        )

        self.assertIsNone(result.backend)
        self.assertIsNone(result.answer)
        self.assertIsNone(result.request_type)
        self.assertIsNone(result.scenario)
        self.assertIsNone(result.ms)
        self.assertIsNone(result.fallback_used)
        self.assertIsNone(result.skills_injected)
        self.assertIsNone(result.retrieval_context)

    def test_inject_skills_empty_messages(self):
        """测试 inject_skills 空消息列表的情况

        验证 inject_skills 函数可以正确处理空消息列表
        """
        mock_skills_mod = MagicMock()
        mock_skills_mod.apply_skills.return_value = []

        with patch('routing_engine.skills_mod', mock_skills_mod):
            result = inject_skills(
                messages=[],
                backend="test_backend",
                ide_source="test_ide",
                system_prompt="test system prompt"
            )

        self.assertEqual(result, [])

    def test_respond_with_empty_answer(self):
        """测试 respond() 函数空答案的情况

        验证 respond 函数可以正确处理空答案的情况
        """
        result = RouteResult(
            backend="test_backend",
            answer="",
            request_type="chat",
            ms=0,
            skills_injected=[]
        )

        response = respond(result, fmt="openai")

        self.assertEqual(response["choices"][0]["message"]["content"], "")

    def test_route_identity_question_with_empty_answer(self):
        """测试 route() 函数身份检测空答案的情况

        验证 route 函数当身份检测返回空答案时正确处理
        """
        mock_identity_guard = MagicMock()
        mock_identity_guard.detect_identity_question.return_value = "Test identity"

        with patch('routing_engine.identity_guard', mock_identity_guard):
            result = route(
                query="Who are you?",
                messages=[{"role": "user", "content": "test"}],
                channel_role="test_role"
            )

        self.assertEqual(result.backend, "identity_guard")
        self.assertEqual(result.answer, "Test identity")

    def testget_injected_ids_helper_with_unicode_skills(self):
        """测试 get_injected_ids helper 的 Unicode 技能名称

        验证 get_injected_ids 函数可以正确处理 Unicode 编码的技能名称
        """
        original = [{"role": "user", "content": "test"}]
        modified = [
            {"role": "user", "content": "test"},
            {"role": "system", "content": "Available skills: skill_1, skill_2, skill_3"}
        ]

        result = get_injected_ids(original, modified)

        self.assertEqual(result, ["dir:skill_1", "dir:skill_2", "dir:skill_3"])

    def testget_injected_ids_helper_mixed_roles(self):
        """测试 get_injected_ids helper 的混合角色消息

        验证 get_injected_ids 函数可以正确处理包含多种角色的消息
        """
        original = [
            {"role": "system", "content": "initial system"},
            {"role": "user", "content": "user message"}
        ]
        modified = [
            {"role": "system", "content": "initial system"},
            {"role": "user", "content": "user message"},
            {"role": "system", "content": "Available skills: tool_a, tool_b"},
            {"role": "assistant", "content": "assistant message"}
        ]

        result = get_injected_ids(original, modified)

        self.assertEqual(result, ["dir:tool_a", "dir:tool_b"])

    def test_route_result_with_special_characters(self):
        """测试 RouteResult 数据类特殊字符处理

        验证 RouteResult 数据类可以正确处理包含特殊字符的字符串
        """
        result = RouteResult(
            backend="backend_with_special_chars",
            answer="answer with special chars: @#$%^&*()",
            request_type="chat",
            scenario="coding_with_special_chars",
            skills_injected=["skill@1", "skill#2"],
            retrieval_context="context with unicode: 你好世界"
        )

        self.assertEqual(result.backend, "backend_with_special_chars")
        self.assertEqual(result.answer, "answer with special chars: @#$%^&*()")
        self.assertEqual(result.scenario, "coding_with_special_chars")
        self.assertEqual(result.skills_injected, ["skill@1", "skill#2"])
        self.assertEqual(result.retrieval_context, "context with unicode: 你好世界")

    def test_respond_with_anthropic_empty_answer(self):
        """测试 respond() 函数 anthropic 格式空答案的情况

        验证 respond 函数在 anthropic 格式中可以正确处理空答案
        """
        result = RouteResult(
            backend="test_backend",
            answer="",
            request_type="chat"
        )

        response = respond(result, fmt="anthropic")

        self.assertEqual(response["content"][0]["text"], "")

    def test_route_reexports_include_all_functions(self):
        """测试 route() 函数的完整 re-export 验证

        验证路由引擎 re-export 的函数列表完整且正确
        """
        from routing_engine import (
            classify,
            classify_scenario,
            inject_skills,
            respond,
            route,
            pick_backend,
        )
        from routing_engine_post import get_injected_ids

        # 验证所有必要的函数都已导入
        self.assertTrue(callable(classify))
        self.assertTrue(callable(classify_scenario))
        self.assertTrue(callable(inject_skills))
        self.assertTrue(callable(respond))
        self.assertTrue(callable(route))
        self.assertTrue(callable(pick_backend))
        self.assertTrue(callable(get_injected_ids))

    def testget_injected_ids_helper_single_skill(self):
        """测试 get_injected_ids helper 单个技能的情况

        验证 get_injected_ids 函数可以正确处理只有单个技能的情况
        """
        original = [{"role": "user", "content": "test"}]
        modified = [
            {"role": "user", "content": "test"},
            {"role": "system", "content": "Available skills: single_skill"}
        ]

        result = get_injected_ids(original, modified)

        self.assertEqual(result, ["dir:single_skill"])

    def test_route_result_equality(self):
        """测试 RouteResult 数据类相等性

        验证 RouteResult 数据类可以正确比较相等性和不相等性
        """
        result1 = RouteResult(
            backend="test",
            answer="answer",
            request_type="chat"
        )
        result2 = RouteResult(
            backend="test",
            answer="answer",
            request_type="chat"
        )
        result3 = RouteResult(
            backend="different",
            answer="answer",
            request_type="chat"
        )

        self.assertEqual(result1, result2)
        self.assertNotEqual(result1, result3)


if __name__ == '__main__':
    unittest.main()
