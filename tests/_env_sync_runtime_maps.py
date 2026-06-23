"""Runtime/infra env-to-singleton mappings for the test monkeypatch wrapper."""

from __future__ import annotations

from typing import Any, Callable

from tests._env_sync_maps import _bool_env, _strip_or_empty

_Map = dict[str, tuple[Any, str, Callable[[str | None], Any]]]


def _backend_ops_map(settings: Any) -> _Map:
    return {
        "LIMA_ALLOW_HTTP_BACKENDS": (settings.FLAGS, "allow_http_backends", _bool_env),
        "LIMA_PROBE_INTERVAL": (settings.BACKEND_OPS, "probe_interval", lambda v: int(v or "300")),
        "LIMA_OPERATOR_PROBE_TIMEOUT": (
            settings.BACKEND_OPS,
            "operator_probe_timeout",
            lambda v: float(v or "25"),
        ),
        "LIMA_OPERATOR_PROBE_WORKERS": (
            settings.BACKEND_OPS,
            "operator_probe_workers",
            lambda v: int(v or "4"),
        ),
        "LIMA_BACKEND_RETIREMENT_RELOAD_SEC": (
            settings.BACKEND_OPS,
            "retirement_reload_sec",
            lambda v: float(v or "300"),
        ),
        "LIMA_DYNAMIC_ADMISSION": (settings.BACKEND_OPS, "dynamic_admission", lambda v: v == "1"),
    }


def _db_map(settings: Any) -> _Map:
    return {
        "LIMA_AUDIT_DB": (settings.DB, "tool_audit_db", lambda v: v or ""),
        "LIMA_WORKER_DB": (settings.DB, "worker_db", lambda v: v or ""),
    }


def _embedding_map(settings: Any) -> _Map:
    return {
        "LIMA_EMBEDDINGS_URL": (
            settings.EMBEDDING,
            "url",
            lambda v: v or "https://api.jina.ai/v1/embeddings",
        ),
        "JINA_API_KEY": (settings.EMBEDDING, "jina_api_key", lambda v: v or ""),
        "GFW_PROXY": (settings.EMBEDDING, "gfw_proxy", lambda v: v or ""),
        "GOOGLE_INVENTORY_PROXY": (settings.EMBEDDING, "google_inventory_proxy", _strip_or_empty),
        "MCP_INVENTORY_PROXY": (settings.EMBEDDING, "mcp_inventory_proxy", _strip_or_empty),
    }


def _fleet_map(settings: Any) -> _Map:
    return {
        "LIMA_FLEET_ALLOWED_COMMANDS": (settings.FLEET, "allowed_commands", _strip_or_empty),
    }


def _paths_map(settings: Any) -> _Map:
    return {
        "LIMA_PROJECT_ROOT": (settings.PATHS, "project_root", lambda v: v or ""),
        "LIMA_CODE_DIR": (settings.PATHS, "code_dir", lambda v: v or "/opt/lima-router"),
        "LIMA_ROUTING_MODEL_PATH": (
            settings.PATHS,
            "routing_model_path",
            lambda v: v or "data/routing_model.json",
        ),
        "LOCAL_ROUTER_URL": (
            settings.PATHS,
            "local_router_url",
            lambda v: v or "http://127.0.0.1:11434/v1/chat/completions",
        ),
    }
