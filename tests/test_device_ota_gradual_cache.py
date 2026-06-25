"""PD-001: GradualRollout selection cache correctness.

The cache must stay consistent with `select_devices_for_stage()` across the
lifecycle (start / promote / rollback / reload) and drop to O(1) membership
checks on the hot path (`is_device_selected`).
"""

from __future__ import annotations

from device_ota.gradual import GradualRollout


def _rollout(tmp_path) -> GradualRollout:
    return GradualRollout(tmp_path / "ota_state.json")


def _devices(n: int) -> list[str]:
    return [f"dev-{i:03d}" for i in range(n)]


def test_is_device_selected_matches_select_for_stage(tmp_path):
    rollout = _rollout(tmp_path)
    rollout.start("v1.2.0", _devices(50), {})
    selected = set(rollout.select_devices_for_stage())
    for device_id in rollout.all_devices:
        assert rollout.is_device_selected(device_id) == (device_id in selected)


def test_cache_invalidates_on_promote(tmp_path):
    rollout = _rollout(tmp_path)
    devices = _devices(50)
    rollout.start("v1.2.0", devices, {})
    stage0_selected = set(rollout.select_devices_for_stage())
    assert rollout.promote()
    stage1_selected = set(rollout.select_devices_for_stage())
    # Stage 1 (20%) is a strict superset of stage 0 (5%); at least one device
    # must flip from not-selected to selected, proving the cache was rebuilt.
    newly_selected = stage1_selected - stage0_selected
    assert newly_selected, "promote did not expand the selected set"
    for device_id in devices:
        assert rollout.is_device_selected(device_id) == (device_id in stage1_selected)


def test_cache_invalidates_on_rollback(tmp_path):
    rollout = _rollout(tmp_path)
    devices = _devices(50)
    rollout.start("v1.2.0", devices, {})
    rollout.promote()
    stage1_selected = set(rollout.select_devices_for_stage())
    assert rollout.rollback()
    stage0_selected = set(rollout.select_devices_for_stage())
    for device_id in devices:
        assert rollout.is_device_selected(device_id) == (device_id in stage0_selected)


def test_cache_invalidates_on_start(tmp_path):
    rollout = _rollout(tmp_path)
    rollout.start("v1.2.0", _devices(50), {})
    first = rollout.is_device_selected("dev-000")
    rollout.start("v2.0.0", _devices(50), {})
    second = rollout.is_device_selected("dev-000")
    # A new version reshuffles the stable hash; assert the cache reflects the
    # new computation (whatever it is), not a stale value.
    expected = "dev-000" in set(rollout.select_devices_for_stage())
    assert second == expected
    # Sanity: first call also matched the then-current computation.
    rollout2 = _rollout(tmp_path)
    rollout2.start("v1.2.0", _devices(50), {})
    assert first == ("dev-000" in set(rollout2.select_devices_for_stage()))


def test_reload_rebuilds_cache(tmp_path):
    rollout = _rollout(tmp_path)
    rollout.start("v1.2.0", _devices(40), {})
    rollout.promote()
    selected = set(rollout.select_devices_for_stage())

    reloaded = _rollout(tmp_path)
    for device_id in rollout.all_devices:
        assert reloaded.is_device_selected(device_id) == (device_id in selected)


def test_empty_rollout_is_device_selected_false(tmp_path):
    rollout = _rollout(tmp_path)
    assert rollout.is_device_selected("dev-000") is False


def test_is_device_selected_uses_cache_not_recompute(tmp_path, monkeypatch):
    """PD-001 hot path: many membership checks must trigger one selection, not N."""
    rollout = _rollout(tmp_path)
    rollout.start("v1.2.0", _devices(50), {})

    calls = {"n": 0}
    real = rollout.select_devices_for_stage

    def counting(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(rollout, "select_devices_for_stage", counting)

    for device_id in rollout.all_devices:
        rollout.is_device_selected(device_id)

    # Cache hit: 50 membership checks must trigger zero recomputations.
    assert calls["n"] == 0, f"expected cache hits only, got {calls['n']} recomputations"
