"""Admin UI panel HTML templates — aggregated dashboard panels."""

from routes.admin_ui.panels._metrics import BACKENDS, OVERVIEW, TRAFFIC
from routes.admin_ui.panels._analysis import HEALTH, MODEL, RETRIEVAL
from routes.admin_ui.panels._admin import AGENT_TASKS, AGENTS, CLIENT_KEYS, KEYS
from routes.admin_ui.panels._system import ALERTS, CONFIG, DEVICES, LIVE_LOGS

__all__ = [
    "AGENT_TASKS",
    "AGENTS",
    "ALERTS",
    "BACKENDS",
    "CLIENT_KEYS",
    "CONFIG",
    "DEVICES",
    "HEALTH",
    "KEYS",
    "LIVE_LOGS",
    "MODEL",
    "OVERVIEW",
    "RETRIEVAL",
    "TRAFFIC",
]
