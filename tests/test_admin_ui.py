"""Tests for the LiMa admin console template."""

from routes.admin_ui import render_admin_dashboard, render_admin_login


def test_render_admin_dashboard_contains_core_sections():
    html = render_admin_dashboard()
    assert "&#x674e;&#x9a6c;" in html
    assert 'id="panel-overview"' in html
    assert 'id="panel-traffic"' in html
    assert 'id="panel-backends"' in html
    assert 'id="panel-retrieval"' in html
    assert 'id="panel-model"' in html
    assert 'id="panel-agents"' in html
    assert "function authFetch" in html
    assert "function esc(" in html
    assert "/admin/api/stats" in html
    assert "/admin/api/agent-audit" in html
    assert "/admin/backends" in html
    assert "/admin/api/backends/toggle" not in html
    assert "��" not in html


def test_render_admin_login_contains_token_form():
    html = render_admin_login("Token error")
    assert "&#x674e;&#x9a6c;" in html
    assert 'method="post"' in html
    assert 'name="token"' in html
    assert "Token error" in html
