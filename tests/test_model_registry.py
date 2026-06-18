"""Tests for model_registry.py adapter version registry."""

import json
import os
from pathlib import Path

import pytest

import model_registry as mr


@pytest.fixture(autouse=True)
def _isolate_registry(tmp_path, monkeypatch):
    """Redirect registry path and active link to a temporary directory."""
    monkeypatch.setattr(mr, "REGISTRY_PATH", str(tmp_path / "registry.json"))
    monkeypatch.setattr(mr, "ACTIVE_LINK", str(tmp_path / "active_model"))


def _write_trainer_state(adapter_dir: Path, global_step: int) -> None:
    state = {"global_step": global_step, "log_history": [{"step": global_step - 100, "loss": 0.42}]}
    (adapter_dir / "trainer_state.json").write_text(json.dumps(state), encoding="utf-8")


def test_register_reads_step_from_trainer_state(tmp_path):
    adapter = tmp_path / "fake_adapter"
    adapter.mkdir()
    _write_trainer_state(adapter, 4000)

    record = mr.register(
        adapter_path=str(adapter),
        metrics={"loss": 0.38, "grbl_acc": 0.91, "cnc_acc": 0.87, "embed_acc": 0.93, "overall": 0.90},
        base_model="Qwen3-8B",
        training_data_count=12000,
        notes="第一轮蒸馏测试",
    )

    assert record["version"] == "r1_step4000"
    assert record["adapter_path"] == str(adapter)
    assert record["metrics"]["overall"] == 0.90
    assert record["active"] is False


def test_get_active_returns_none_when_no_active_version():
    assert mr.get_active() is None


def test_promote_activates_version_and_deactivates_others(tmp_path):
    adapter1 = tmp_path / "a1"
    adapter2 = tmp_path / "a2"
    adapter1.mkdir()
    adapter2.mkdir()
    _write_trainer_state(adapter1, 4000)
    _write_trainer_state(adapter2, 8000)

    record1 = mr.register(str(adapter1), {"overall": 0.90})
    record2 = mr.register(str(adapter2), {"overall": 0.93})

    assert mr.promote(record1["version"]) is True
    active = mr.get_active()
    assert active is not None
    assert active["version"] == record1["version"]
    assert active["active"] is True

    assert mr.promote(record2["version"]) is True
    active = mr.get_active()
    assert active["version"] == record2["version"]

    versions = mr.list_versions()
    assert len(versions) == 2
    assert sum(1 for v in versions if v["active"]) == 1


def test_promote_returns_false_for_missing_version():
    assert mr.promote("nonexistent") is False


def test_rollback_switches_to_previous_version(tmp_path):
    adapter1 = tmp_path / "a1"
    adapter2 = tmp_path / "a2"
    adapter1.mkdir()
    adapter2.mkdir()
    _write_trainer_state(adapter1, 4000)
    _write_trainer_state(adapter2, 8000)

    record1 = mr.register(str(adapter1), {"overall": 0.90})
    record2 = mr.register(str(adapter2), {"overall": 0.93})
    mr.promote(record2["version"])

    rolled = mr.rollback()
    assert rolled is not None
    assert rolled["version"] == record1["version"]
    assert mr.get_active()["version"] == record1["version"]


def test_rollback_returns_none_when_no_previous_version(tmp_path):
    adapter = tmp_path / "a1"
    adapter.mkdir()
    _write_trainer_state(adapter, 4000)
    record = mr.register(str(adapter), {"overall": 0.90})
    mr.promote(record["version"])

    assert mr.rollback() is None


def test_list_versions_sorted_by_created_at_desc(tmp_path):
    adapter1 = tmp_path / "a1"
    adapter2 = tmp_path / "a2"
    adapter1.mkdir()
    adapter2.mkdir()
    _write_trainer_state(adapter1, 1000)
    _write_trainer_state(adapter2, 2000)

    record1 = mr.register(str(adapter1), {"overall": 0.80})
    record2 = mr.register(str(adapter2), {"overall": 0.90})

    versions = mr.list_versions()
    assert [v["version"] for v in versions] == [record2["version"], record1["version"]]


def test_get_status_summarizes_registry(tmp_path):
    adapter = tmp_path / "a1"
    adapter.mkdir()
    _write_trainer_state(adapter, 4000)

    record = mr.register(
        str(adapter),
        {"loss": 0.38, "grbl_acc": 0.91, "cnc_acc": 0.87, "embed_acc": 0.93, "overall": 0.90},
    )

    status = mr.get_status()
    assert status["total_versions"] == 1
    assert status["active_version"] is None
    assert status["latest_metrics"]["overall"] == 0.90

    mr.promote(record["version"])
    status = mr.get_status()
    assert status["active_version"] == record["version"]


def test_register_without_trainer_state_falls_back_to_timestamp(tmp_path):
    adapter = tmp_path / "no_state"
    adapter.mkdir()

    record = mr.register(str(adapter), {"overall": 0.85})
    assert record["version"].startswith("v")
    assert len(record["version"]) >= 14
