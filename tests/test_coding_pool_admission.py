"""Tests for eval-driven IDE coding pool admission."""

from __future__ import annotations

import json
from pathlib import Path

import coding_pool_admission as mod


def test_assign_tiers_from_stats_promotes_strong(tmp_path: Path):
    stats = {
        "good": {"avg_score": 95.0, "avg_latency_ms": 1200, "pass_rate": 1.0, "passes": 3, "cases": 3},
        "weak": {"avg_score": 40.0, "avg_latency_ms": 9000, "pass_rate": 0.2, "passes": 1, "cases": 5},
    }
    tiers = mod.assign_tiers_from_stats(stats)
    assert tiers["good"]["tier"] == "strong"
    assert "weak" not in tiers


def test_private_code_blocked_for_sandbox_web(monkeypatch):
    monkeypatch.setattr(mod, "_free_web_private_code", lambda b: False if b == "mimo_web" else None)
    monkeypatch.setattr(mod, "_registry_private_code_allowed", lambda b: False)
    assert mod.private_code_blocked("mimo_web") is True


def test_blocked_without_evidence_when_tiers_exist(tmp_path: Path, monkeypatch):
    tiers_file = tmp_path / "coding_backend_tiers.json"
    tiers_file.write_text(
        json.dumps({"backends": {"proven": {"tier": "primary", "pool": "coder"}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_TIERS_PATH", tiers_file)
    monkeypatch.setenv("LIMA_IDE_POOL_EVIDENCE_GATE", "1")
    assert mod.blocked_without_evidence("unknown_backend") is True
    assert mod.blocked_without_evidence("proven") is False


def test_filter_ide_coding_pool_strips_sandbox(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LIMA_EVAL_POOL_GATE", "0")
    monkeypatch.setenv("LIMA_IDE_POOL_EVIDENCE_GATE", "0")
    monkeypatch.setattr(mod, "private_code_blocked", lambda b: b == "mimo_web")
    out = mod.filter_ide_coding_pool(["scnet_ds_flash", "mimo_web", "github_gpt4o"])
    assert out == ["scnet_ds_flash", "github_gpt4o"]
