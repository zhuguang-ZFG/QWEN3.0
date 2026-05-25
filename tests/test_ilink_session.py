"""iLink session keepalive / relogin helpers."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wechat_bridge.ilink_session import is_session_dead, _write_relogin_html


def test_session_dead_errcode_14():
    assert is_session_dead(-14, 0) is True
    assert is_session_dead(0, -14) is True


def test_session_dead_ok():
    assert is_session_dead(0, 0) is False


def test_relogin_html_written(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "wechat_bridge.ilink_session.RELONGIN_HTML",
        tmp_path / "relogin.html",
    )
    p = _write_relogin_html("https://example.com/qr", "abc123")
    assert p.exists()
    assert "续登" in p.read_text(encoding="utf-8")
