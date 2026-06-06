"""Regression tests for security and deploy closeout fixes."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

import session_memory.outcome_ledger as outcome_ledger

ROOT = Path(__file__).resolve().parents[1]


def _load_script_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_switch_codex_api_script_does_not_hardcode_provider_keys():
    script = (ROOT / "switch-codex-api.ps1").read_text(encoding="utf-8")

    assert "OPENAI_NEXT_API_KEY" in script
    assert "CENTOS_API_KEY" in script
    assert "sk-" not in script


def test_deploy_unified_stop_port_command_is_posix_shell_compatible():
    deploy_unified = _load_script_module("deploy_unified", ROOT / "scripts" / "deploy_unified.py")

    command = deploy_unified._stop_port_8080_cmd()

    assert "{1.." not in command
    assert 'while [ "$attempt" -le 10 ]' in command
    assert 'while [ "$wait_attempt" -le 15 ]' in command


def test_outcome_ledger_schema_migration_only_ignores_duplicate_columns(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_OUTCOME_DB", str(tmp_path / "outcomes.db"))

    class FailingConnection:
        def __init__(self, real_conn):
            self._real_conn = real_conn

        def execute(self, sql: str):
            if sql.startswith("ALTER TABLE outcomes ADD COLUMN loop "):
                raise sqlite3.OperationalError("database is locked")
            return self._real_conn.execute(sql)

        def __getattr__(self, name: str):
            return getattr(self._real_conn, name)

    real_connect = sqlite3.connect

    def fake_connect(*args, **kwargs):
        return FailingConnection(real_connect(*args, **kwargs))

    monkeypatch.setattr(outcome_ledger.sqlite3, "connect", fake_connect)

    with pytest.raises(sqlite3.OperationalError, match="database is locked"):
        outcome_ledger._get_conn()
