"""UX helpers for Weixin LiMa bridge."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.hermes_weixin_lima_bridge import _split_reply, _user_facing_error


def test_user_facing_error_duplicate_silent():
    assert _user_facing_error("duplicate message") == ""


def test_user_facing_error_http5():
    assert "繁忙" in _user_facing_error("HTTP 503")


def test_split_reply_chunks():
    long = "a" * 5000
    parts = _split_reply(long, chunk=2000)
    assert len(parts) >= 2
    assert "(1/" in parts[0]
    assert "a" * 100 in parts[0]
