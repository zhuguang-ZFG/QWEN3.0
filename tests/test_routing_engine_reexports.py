"""routing_engine __all__ / re-export tests."""

from routing_engine import (
    RouteResult,
    classify,
    classify_scenario,
    inject_skills,
    pick_backend,
    respond,
    route,
)
from routing_engine import __all__ as routing_engine_all
from routing_engine.post import get_injected_ids


def test_route_reexports_are_correct():
    """测试 route() 函数的正�?re-export

    验证路由引擎正确 re-export 所有必要的函数
    """
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
        assert export in routing_engine_all


def test_route_reexports_include_all_functions():
    """测试 route() 函数的完�?re-export 验证

    验证路由引擎 re-export 的函数列表完整且正确
    """
    assert callable(classify)
    assert callable(classify_scenario)
    assert callable(inject_skills)
    assert callable(respond)
    assert callable(route)
    assert callable(pick_backend)
    assert callable(get_injected_ids)
