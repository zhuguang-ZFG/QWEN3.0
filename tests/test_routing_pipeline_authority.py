"""Tests that guard routing pipeline authority boundaries.

See docs/REQUEST_PIPELINE_AUTHORITY.md for the authoritative ownership matrix.
These tests verify that module responsibilities don't leak across boundaries.
"""

from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


def _read_module_source(name: str) -> str:
    path = REPO / f"{name.replace('.', '/')}.py"
    if not path.exists():
        path = REPO / f"{name.replace('.', '/')}/__init__.py"
    return path.read_text(encoding="utf-8") if path.exists() else ""


class TestRoutingClassifierAuthority:
    """routing_classifier owns classify() and classify_scenario() only."""

    def test_classify_exists(self):
        from routing_classifier import classify, classify_scenario
        assert callable(classify)
        assert callable(classify_scenario)

    def test_classifier_does_not_call_health_tracker(self):
        src = _read_module_source("routing_classifier")
        assert "health_tracker.record" not in src, (
            "routing_classifier should not record health events"
        )


class TestRouterV3Authority:
    """router_v3 owns POOLS and select_backends()."""

    def test_pools_defined(self):
        from router_v3 import POOLS
        assert isinstance(POOLS, dict)
        assert "ide" in POOLS or "chat" in POOLS

    def test_select_backends_exists(self):
        from router_v3 import select_backends
        assert callable(select_backends)

    def test_v3_does_not_execute(self):
        src = _read_module_source("router_v3")
        assert "call_api" not in src, (
            "router_v3 should not call http_caller.call_api directly"
        )


class TestRoutingSelectorAuthority:
    """routing_selector owns select() —综合排名。"""

    def test_select_exists(self):
        from routing_selector import select
        assert callable(select)

    def test_selector_does_not_call_http(self):
        src = _read_module_source("routing_selector")
        assert "call_api" not in src, (
            "routing_selector should not perform HTTP calls"
        )


class TestRoutingExecutorAuthority:
    """routing_executor owns execute() —按序/并行 fallback。"""

    def test_execute_exists(self):
        from routing_executor import execute
        assert callable(execute)

    def test_executor_records_health(self):
        src = _read_module_source("routing_executor")
        assert "health_tracker.record" in src or "re.health_tracker.record" in src, (
            "routing_executor should record health success/failure"
        )


class TestRoutingEngineAuthority:
    """routing_engine.route() is the single authoritative routing entry point."""

    def test_route_exists(self):
        from routing_engine import route
        assert callable(route)

    def test_route_imports_all_layers(self):
        src = _read_module_source("routing_engine")
        for module in [
            "routing_classifier",
            "routing_selector",
            "routing_executor",
            "health_tracker",
            "skills_injector",
        ]:
            assert module in src, f"routing_engine should import {module}"

    def test_engine_does_not_call_caller_directly(self):
        src = _read_module_source("routing_engine")
        # routing_engine delegates to routing_executor, not http_caller directly
        # except for the call_fn callback pattern
        lines = [l.strip() for l in src.split("\n") if not l.strip().startswith("#")]
        direct_call_lines = [
            l for l in lines
            if "http_caller.call_api" in l and "call_fn" not in l
        ]
        assert not direct_call_lines, (
            f"routing_engine should use routing_executor, not call http_caller directly: {direct_call_lines}"
        )


class TestSmartRouterLegacy:
    """smart_router is legacy — should not be imported by routing_engine."""

    def test_engine_does_not_import_smart_router(self):
        src = _read_module_source("routing_engine")
        assert "import smart_router" not in src, (
            "routing_engine should not depend on smart_router"
        )

    def test_smart_router_has_legacy_marker(self):
        src = _read_module_source("smart_router")
        assert "legacy" in src.lower() or "V3" in src or "deprecated" in src.lower(), (
            "smart_router should be marked as legacy/deprecated"
        )


class TestHttpCallerAuthority:
    """http_caller owns HTTP transport only."""

    def test_caller_exists(self):
        from http_caller import call_api
        assert callable(call_api)

    def test_caller_does_not_route(self):
        src = _read_module_source("http_caller")
        assert "classify" not in src or "classify" in src.split("class")[0], (
            "http_caller should not perform routing classification"
        )
