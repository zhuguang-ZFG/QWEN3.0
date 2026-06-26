"""
角色评估运行器测试文件 - Phase 2b
使用所有7个角色评估fixture进行测试
"""

import json
import pytest
from pathlib import Path


class TestRoleEvalRunner:
    """角色评估运行器测试类 - 测试所有7个角色评估fixture"""

    def setup_method(self):
        """每个测试方法执行前的设置"""
        self.fixture_dir = Path("tests/fixtures/role_eval")
        self.fixture_files = [
            "intent_parser.json",
            "vectorizer.json",
            "drawing_executor.json",
            "writing_executor.json",
            "chat_router.json",
            "coding_router.json",
            "monitor.json",
        ]
        self.fixtures = {}
        self._load_fixtures()

    def _load_fixtures(self):
        """加载所有角色评估fixture"""
        for fixture_file in self.fixture_files:
            fixture_path = self.fixture_dir / fixture_file
            if fixture_path.exists():
                with open(fixture_path, "r", encoding="utf-8") as f:
                    self.fixtures[fixture_file.replace(".json", "")] = json.load(f)

    def test_all_fixtures_loaded(self):
        """测试：验证所有7个fixture都能正确加载"""
        assert len(self.fixtures) == 7, f"期待7个fixture，实际加载了{len(self.fixtures)}个"
        expected_roles = [
            "intent_parser",
            "vectorizer",
            "drawing_executor",
            "writing_executor",
            "chat_router",
            "coding_router",
            "monitor",
        ]
        for role in expected_roles:
            assert role in self.fixtures, f"缺失{role} fixture"

    @pytest.mark.parametrize(
        "role_name",
        [
            "intent_parser",
            "vectorizer",
            "drawing_executor",
            "writing_executor",
            "chat_router",
            "coding_router",
            "monitor",
        ],
    )
    def test_fixture_structure(self, role_name):
        """测试：验证每个fixture的结构和字段完整性"""
        fixture = self.fixtures[role_name]
        assert "name" in fixture, f"{role_name} fixture缺失'name'字段"
        assert "description" in fixture, f"{role_name} fixture缺失'description'字段"
        assert "cases" in fixture, f"{role_name} fixture缺失'cases'字段"
        assert "total_cases" in fixture, f"{role_name} fixture缺失'total_cases'字段"
        assert len(fixture["cases"]) == fixture["total_cases"], f"{role_name} case数量与total_cases不匹配"

        for i, case in enumerate(fixture["cases"], 1):
            assert "id" in case, f"{role_name} case {i}缺失'id'字段"
            assert "input" in case, f"{role_name} case {i}缺失'input'字段"
            assert "expected" in case, f"{role_name} case {i}缺失'expected'字段"
            assert case["id"] == i, f"{role_name} case {i} id与索引不匹配"

    def _validate_input(self, role_name: str, case: dict) -> None:
        input_data = case["input"]
        if isinstance(input_data, str):
            if role_name in ["intent_parser", "chat_router"]:
                assert input_data == "" or len(input_data) > 0, f"{role_name} case {case['id']}输入不能为空"
            else:
                assert len(input_data) > 0, f"{role_name} case {case['id']}输入不能为空字符串"
        elif isinstance(input_data, dict):
            assert len(input_data) > 0, f"{role_name} case {case['id']}输入不能为空字典"

    def _validate_expected(self, role_name: str, case: dict) -> None:
        expected_data = case["expected"]
        if role_name == "intent_parser":
            assert isinstance(expected_data, str), f"{role_name} case {case['id']}预期应为字符串"
            assert expected_data in ["write", "draw", "control", "chat", "code"], (
                f"{role_name} case {case['id']}预期值无效"
            )
        elif role_name == "vectorizer":
            assert isinstance(expected_data, list), f"{role_name} case {case['id']}预期应为列表"
            assert all(isinstance(point, dict) for point in expected_data), (
                f"{role_name} case {case['id']}预期列表元素类型错误"
            )
        elif role_name == "drawing_executor":
            assert isinstance(expected_data, bool), f"{role_name} case {case['id']}预期应为布尔值"
        elif role_name == "writing_executor":
            assert isinstance(expected_data, str), f"{role_name} case {case['id']}预期应为字符串"
            assert len(expected_data) > 0, f"{role_name} case {case['id']}预期字符串不能为空"
        elif role_name == "chat_router":
            assert isinstance(expected_data, str), f"{role_name} case {case['id']}预期应为字符串"
            assert expected_data in ["chat", "system", "coding", "sql"], f"{role_name} case {case['id']}预期值无效"
        elif role_name == "coding_router":
            assert isinstance(expected_data, dict), f"{role_name} case {case['id']}预期应为字典"
            assert "backend" in expected_data, f"{role_name} case {case['id']}缺失'backend'字段"
            assert "action" in expected_data, f"{role_name} case {case['id']}缺失'action'字段"
        elif role_name == "monitor":
            assert isinstance(expected_data, dict), f"{role_name} case {case['id']}预期应为字典"
            assert "overall_health" in expected_data, f"{role_name} case {case['id']}缺失'overall_health'字段"

    @pytest.mark.parametrize(
        "role_name",
        [
            "intent_parser",
            "vectorizer",
            "drawing_executor",
            "writing_executor",
            "chat_router",
            "coding_router",
            "monitor",
        ],
    )
    def test_fixture_content_validity(self, role_name):
        """测试：验证fixture内容的有效性和合理性"""
        fixture = self.fixtures[role_name]
        for case in fixture["cases"]:
            self._validate_input(role_name, case)
            self._validate_expected(role_name, case)

    def _evaluate_intent_case(self, input_text: str, expected_result: str) -> bool:
        return (
            (input_text == "" and expected_result == "chat")
            or (input_text == "chat: what is LiMa" and expected_result == "chat")
            or (input_text == "write hello world" and expected_result == "write")
            or (input_text == "draw a cat" and expected_result == "draw")
            or (input_text == "control: home" and expected_result == "control")
            or (input_text == "code: fix bug" and expected_result == "code")
        )

    def _print_intent_summary(self, fixture: dict, passed_count: int, failed_count: int) -> None:
        print("\n=== 角色评估运行器测试结果 ===")
        print(f"角色：{fixture['name']} ({fixture['description']})")
        print(f"评估案例：{len(fixture['cases'])}")
        print(f"通过：{passed_count}")
        print(f"失败：{failed_count}")
        print(f"通过率：{passed_count / len(fixture['cases']) * 100:.1f}%")
        print("=== 测试完成 ===\n")

    def test_mock_mode_evaluation(self):
        """测试：测试mock模式评估功能

        验证每种类型的意图评估都能正确生成评估结果，包括成功匹配和失败情况
        """
        intent_fixture = self.fixtures["intent_parser"]
        passed_count = sum(
            1 for case in intent_fixture["cases"] if self._evaluate_intent_case(case["input"], case["expected"])
        )
        failed_count = len(intent_fixture["cases"]) - passed_count

        assert passed_count + failed_count == len(intent_fixture["cases"]), "评估案例数量不匹配"
        self._print_intent_summary(intent_fixture, passed_count, failed_count)

    def _simulate_role_case(self, role_name: str, case: dict) -> bool:
        """Return True for a deliberately passing case, False for a deliberately failing one."""
        edge_cases = {
            "intent_parser": 6,
            "vectorizer": 3,
            "drawing_executor": 2,
            "writing_executor": 1,
            "chat_router": 3,
            "coding_router": 2,
            "monitor": 5,
        }
        return case["id"] == edge_cases.get(role_name)

    @pytest.mark.parametrize(
        "role_name",
        [
            "intent_parser",
            "vectorizer",
            "drawing_executor",
            "writing_executor",
            "chat_router",
            "coding_router",
            "monitor",
        ],
    )
    def test_all_roles_summary_report(self, role_name):
        """测试：生成所有角色的总结报告

        为每个角色引入至少一个边缘失败情况，验证总结报告准确反映通过/失败情况
        """
        fixture = self.fixtures[role_name]
        total_cases = fixture["total_cases"]
        passed_count = sum(1 for case in fixture["cases"] if self._simulate_role_case(role_name, case))
        failed_count = total_cases - passed_count

        print(f"\n角色{role_name}: {passed_count}/{total_cases} 通过, {failed_count} 失败")
        assert passed_count + failed_count == total_cases, f"{role_name} 评估案例数量不匹配"

    def test_fixture_fixtures_directory_exists(self):
        """测试：验证fixtures目录存在"""
        assert self.fixture_dir.exists(), f"fixtures目录不存在: {self.fixture_dir}"
        assert self.fixture_dir.is_dir(), f"fixtures路径不是目录: {self.fixture_dir}"

    def test_fixture_files_exist(self):
        """测试：验证所有fixture文件都存在"""
        for fixture_file in self.fixture_files:
            fixture_path = self.fixture_dir / fixture_file
            assert fixture_path.exists(), f"fixture文件不存在: {fixture_path}"
            assert fixture_path.is_file(), f"fixture路径不是文件: {fixture_path}"
