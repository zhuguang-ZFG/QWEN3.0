"""Tests for admin dashboard template (redesigned sidebar layout)."""

from routes.admin_ui import render_admin_dashboard


def test_render_admin_dashboard_contains_core_sections():
    html = render_admin_dashboard()
    assert "LiMa" in html
    assert 'id="panel-overview"' in html
    assert 'id="panel-backends"' in html
    assert 'id="panel-health"' in html
    assert 'id="panel-live-logs"' in html
    assert 'href="/chat/admin.css' in html
    assert 'src="/chat/admin.js' in html
    # 14 sidebar nav buttons
    assert html.count("data-panel=") == 14
