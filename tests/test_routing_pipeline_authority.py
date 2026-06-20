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
        assert "health_tracker.record" not in src, "routing_classifier should not record health events"


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
        assert "call_api" not in src, "router_v3 should not call http_caller.call_api directly"


class TestRoutingSelectorAuthority:
    """routing_selector owns select() —综合排名。"""

    def test_select_exists(self):
        from routing_selector import select

        assert callable(select)

    def test_selector_does_not_call_http(self):
        src = _read_module_source("routing_selector")
        assert "call_api" not in src, "routing_selector should not perform HTTP calls"


class TestRoutingExecutorAuthority:
    """routing_executor owns execute() —按序/并行 fallback。"""

    def test_execute_exists(self):
        from routing_executor import execute

        assert callable(execute)

    def test_executor_records_health(self):
        src = (
            _read_module_source("routing_executor")
            + _read_module_source("routing_executor_serial")
            + _read_module_source("routing_executor_fallback")
        )
        assert "health_tracker.record" in src or "re.health_tracker.record" in src, (
            "routing_executor should record health success/failure"
        )


class TestRoutingEngineAuthority:
    """routing_engine.route() is the single authoritative routing entry point."""

    def test_route_exists(self):
        from routing_engine import route

        assert callable(route)

    def test_pick_backend_exists(self):
        from routing_engine import pick_backend

        assert callable(pick_backend)

    def test_route_imports_all_layers(self):
        src = _read_module_source("routing_engine")
        for module in [
            "routing_classifier",
            "routing_selector",
            "routing_engine_execute_strategy",
            "health_tracker",
            "skills_injector",
        ]:
            assert module in src, f"routing_engine should import {module}"

    def test_public_api_excludes_select_execute(self):
        from routing_engine import __all__

        assert "select" not in __all__
        assert "execute" not in __all__
        assert "pick_backend" in __all__
        assert "route" in __all__

    def test_engine_does_not_call_caller_directly(self):
        src = _read_module_source("routing_engine")
        # routing_engine delegates to routing_executor, not http_caller directly
        # except for the call_fn callback pattern
        lines = [l.strip() for l in src.split("\n") if not l.strip().startswith("#")]
        direct_call_lines = [l for l in lines if "http_caller.call_api" in l and "call_fn" not in l]
        assert not direct_call_lines, (
            f"routing_engine should use routing_executor, not call http_caller directly: {direct_call_lines}"
        )

    def test_eval_internal_uses_pinned_executor_not_http_caller(self):
        src = _read_module_source("routes.eval_internal")
        assert "http_caller" not in src, "eval_internal should delegate to eval_pinned_call, not http_caller"
        assert "call_pinned_backend" in src


class TestDeviceRoutingIsolation:
    """Device routing must be isolated from general chat/coding routing."""

    def test_device_gateway_does_not_import_routing_engine(self):
        """Device gateway should not depend on routing_engine for chat routing."""
        src = _read_module_source("device_gateway.tasks")
        # device_gateway should use its own routing, not routing_engine
        # (routing_engine is for chat/coding, not device tasks)
        assert "import routing_engine" not in src, "device_gateway should not import routing_engine directly"

    def test_routing_engine_does_not_import_device_gateway(self):
        """Routing engine should not import device gateway modules."""
        src = _read_module_source("routing_engine")
        assert "import device_gateway" not in src, "routing_engine should not import device_gateway"


class TestLocalProxyTopologyGuard:
    """Local Windows proxy backends should not be promoted to VPS priority routing."""

    def test_local_backends_marked_in_registry(self):
        """Local/proxy backends should be marked as local in backends_constants."""
        from backends_constants import KEY_POOL_PREFIXES

        # Local backends should not have cloud provider prefixes
        # This is a structural check — local backends use different naming
        assert isinstance(KEY_POOL_PREFIXES, dict)


class TestProviderHealthVisibility:
    """Provider health/cooldown/budget failures must be visible in logs and metrics."""

    def test_health_tracker_records_failures(self):
        """health_tracker must record failure events for observability."""
        src = _read_module_source("health_tracker")
        assert "record_failure" in src or "record" in src, "health_tracker must have failure recording capability"

    def test_budget_manager_records_usage(self):
        """budget_manager must record usage for observability."""
        src = _read_module_source("budget_manager")
        assert "record_usage" in src or "is_budget_available" in src, (
            "budget_manager must have usage recording capability"
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


class TestRoutesBypassGuard:
    """routes/ must not call routing_engine.select/execute outside allowlist."""

    ALLOWLIST: dict[str, set[str]] = {}

    def test_no_select_execute_bypass_outside_allowlist(self):
        routes_dir = REPO / "routes"
        violations: list[str] = []
        patterns = ("routing_engine.select(", "routing_engine.execute(")
        for path in sorted(routes_dir.glob("*.py")):
            rel = path.relative_to(REPO).as_posix()
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for pattern in patterns:
                    if pattern not in line:
                        continue
                    allowed = self.ALLOWLIST.get(rel, set())
                    if pattern not in allowed:
                        violations.append(f"{rel}:{line_no}: {pattern}")
        assert not violations, "routing authority bypass in routes/:\n" + "\n".join(violations)
