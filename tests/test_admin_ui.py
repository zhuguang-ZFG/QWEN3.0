"""Tests for admin dashboard template extraction (CQ-014 slice 2)."""

from routes.admin_ui import render_admin_dashboard


def test_render_admin_dashboard_contains_core_sections():
    html = render_admin_dashboard()
    assert "LiMa 管理后台" in html
    assert 'id="panel-stats"' in html
    assert 'id="panel-backends"' in html
    assert "function authFetch" in html
    assert "function esc(" in html
