"""Tests for routes/admin_auth.py — admin authentication helpers."""

from routes.admin_auth import get_admin_token, admin_session_value, is_valid_admin_session


class TestGetAdminToken:
    def test_default_empty(self, monkeypatch):
        monkeypatch.setenv("LIMA_ADMIN_TOKEN", "")
        assert get_admin_token() == ""

    def test_reads_env(self, monkeypatch):
        monkeypatch.setenv("LIMA_ADMIN_TOKEN", "secret123")
        assert get_admin_token() == "secret123"


class TestAdminSessionValue:
    def test_deterministic(self, monkeypatch):
        monkeypatch.setenv("LIMA_ADMIN_TOKEN", "secret")
        v1 = admin_session_value()
        v2 = admin_session_value()
        assert v1 == v2
        assert len(v1) == 64


class TestIsValidAdminSession:
    def test_valid(self, monkeypatch):
        monkeypatch.setenv("LIMA_ADMIN_TOKEN", "secret")
        assert is_valid_admin_session(admin_session_value()) is True

    def test_invalid(self, monkeypatch):
        monkeypatch.setenv("LIMA_ADMIN_TOKEN", "secret")
        assert is_valid_admin_session("wrong") is False

    def test_empty_token(self, monkeypatch):
        monkeypatch.setenv("LIMA_ADMIN_TOKEN", "")
        assert is_valid_admin_session(admin_session_value()) is False
