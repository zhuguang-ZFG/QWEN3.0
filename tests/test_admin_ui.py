"""Tests for routes/admin_ui/main.py and templates.py — admin HTML rendering."""

from routes.admin_ui.main import render_admin_login, render_admin_dashboard
from routes.admin_ui import templates


class TestRenderAdminLogin:
    def test_contains_form(self):
        html = render_admin_login()
        assert "<form" in html
        assert "Admin Token" in html

    def test_escapes_error(self):
        html = render_admin_login("<script>alert(1)</script>")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestRenderAdminDashboard:
    def test_contains_panels(self):
        html = render_admin_dashboard()
        assert "概览" in html
        assert "后端管理" in html
        assert "live-logs" in html


class TestTemplates:
    def test_head_contains_title(self):
        assert "LiMa" in templates.HEAD

    def test_close_closes_tags(self):
        assert "</html>" in templates.CLOSE
