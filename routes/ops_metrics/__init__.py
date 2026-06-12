"""Ops metrics submodule."""
from .collectors import *
from .correlator import *
from .formatters import *

# Import parent module components for backward compatibility
import importlib.util
import sys
spec = importlib.util.spec_from_file_location("_ops_metrics_main", __file__.replace("__init__.py", "../ops_metrics.py"))
if spec and spec.loader:
    _main = importlib.util.module_from_spec(spec)
    sys.modules["_ops_metrics_main"] = _main
    spec.loader.exec_module(_main)
    router = _main.router
else:
    router = None

__all__ = [
    "redacted", "backend_call_count", "backend_call_detail",
    "top_backend_counts", "top_backend_details",
    "app_stats", "recent_agent_tasks", "get_capability_evidence",
    "get_cli_telemetry", "get_backend_telemetry", "get_routing_guard",
    "backend_recovery_snapshot", "ops_metrics_snapshot",
    "correlate_by_id", "correlate_recent", "correlation_summary", "build_trace",
    "router",
]
