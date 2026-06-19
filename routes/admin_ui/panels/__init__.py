"""Admin UI panel HTML templates — aggregated dashboard panels."""

from routes.admin_ui.panels.overview import OVERVIEW
from routes.admin_ui.panels.traffic import TRAFFIC
from routes.admin_ui.panels.backends import BACKENDS
from routes.admin_ui.panels.retrieval import RETRIEVAL
from routes.admin_ui.panels.model import MODEL
from routes.admin_ui.panels.health import HEALTH
from routes.admin_ui.panels.keys import CLIENT_KEYS, KEYS
from routes.admin_ui.panels.agents import AGENTS, AGENT_TASKS
from routes.admin_ui.panels.config import CONFIG
from routes.admin_ui.panels.devices import DEVICES
from routes.admin_ui.panels.alerts import ALERTS
from routes.admin_ui.panels.live_logs import LIVE_LOGS

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
