"""Admin UI module — templates and panels."""

from routes.admin_ui.main import render_admin_dashboard, render_admin_login
from routes.admin_ui import panels, templates

__all__ = ["panels", "templates", "render_admin_dashboard", "render_admin_login"]
