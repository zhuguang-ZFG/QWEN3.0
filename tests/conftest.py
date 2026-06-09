"""Pytest configuration for async test support."""

import pytest_asyncio  # noqa: F401

# Enable auto mode so @pytest.mark.asyncio tests run without manual event loop setup
pytest_plugins = ["pytest_asyncio"]


def pytest_addoption(parser):
    parser.addoption("--stability-rounds", action="store", default=0, type=int,
                     help="Number of stability loop iterations (0 = skip).")


# 批量跳过依赖已删除模块的测试（战略转型 Phase 0 - 编码助手特性移除）
collect_ignore_glob = [
    # agent_runtime 相关测试（已删除模块）
    "test_approval_gate.py",
    "test_operator_features.py",
    "test_prompt_contract.py",
    "test_real_execution.py",
    "test_real_executor.py",
    "test_safe_execution.py",
    "test_worker_summary_constraints.py",
    # quality_gate 相关测试（临时 stub，Phase 2 移除）
    "test_e2e_release.py",
    # 其他编码助手特性测试
    "test_stream_footer.py",
]
