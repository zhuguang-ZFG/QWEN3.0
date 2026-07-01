"""Node role and capability switches for multi-node LiMa deployments.

Primary node (JDCloud): runs the full LiMa stack including session memory,
device gateway, MQTT, context retrieval, and observability.

Auxiliary node (Aliyun): runs a stripped-down ``lima-router`` that only serves
stateless or low-state requests backed by free/cheap cloud providers.
"""

from __future__ import annotations

import os


NODE_ROLE_PRIMARY = "primary"
NODE_ROLE_FREE_BACKEND_ONLY = "free_backend_only"


def node_role() -> str:
    """Return the configured node role. Defaults to primary."""
    role = os.environ.get("LIMA_NODE_ROLE", NODE_ROLE_PRIMARY).strip().lower()
    if role in {NODE_ROLE_PRIMARY, NODE_ROLE_FREE_BACKEND_ONLY}:
        return role
    return NODE_ROLE_PRIMARY


def is_primary() -> bool:
    """True when this node is the primary/full-capability node."""
    return node_role() == NODE_ROLE_PRIMARY


def is_free_backend_only() -> bool:
    """True when this node should only run free/low-cost backend traffic."""
    return node_role() == NODE_ROLE_FREE_BACKEND_ONLY


def _env_enabled(name: str, default: bool = True) -> bool:
    """Read a LIMA_*_ENABLED variable with safe defaults."""
    raw = os.environ.get(name, "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def session_memory_enabled() -> bool:
    """Session memory daemon is enabled unless explicitly disabled."""
    return _env_enabled("LIMA_SESSION_MEMORY_ENABLED", default=True)


def device_gateway_enabled() -> bool:
    """Device gateway runtime + MQTT are enabled unless explicitly disabled."""
    return _env_enabled("LIMA_DEVICE_GATEWAY_ENABLED", default=True)


def mqtt_enabled() -> bool:
    """MQTT client is enabled unless explicitly disabled."""
    return _env_enabled("LIMA_MQTT_CLIENT_ENABLED", default=True)


def context_retrieval_enabled() -> bool:
    """Context pipeline retrieval injection is enabled unless explicitly disabled."""
    return _env_enabled("LIMA_CONTEXT_RETRIEVAL_ENABLED", default=True)


def prometheus_enabled() -> bool:
    """Prometheus metrics exporter is enabled unless explicitly disabled."""
    return _env_enabled("LIMA_PROMETHEUS_ENABLED", default=True)


def alert_evaluator_enabled() -> bool:
    """Alert evaluator is enabled unless explicitly disabled."""
    return _env_enabled("LIMA_ALERT_EVALUATOR_ENABLED", default=True)


def structured_logging_enabled() -> bool:
    """Structured JSON logging is enabled unless explicitly disabled."""
    return _env_enabled("LIMA_STRUCTURED_LOGGING_ENABLED", default=True)
