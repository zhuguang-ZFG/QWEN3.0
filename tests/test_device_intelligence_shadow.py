from device_intelligence.shadow import DeviceShadowStore


def test_shadow_tracks_hello_heartbeat_device_info_self_check_and_motion_event():
    store = DeviceShadowStore()

    store.update_hello(
        {
            "type": "hello",
            "device_id": "dev-1",
            "fw_rev": "u8-test",
            "capabilities": ["run_path", "home"],
            "profile_id": "dlc-p1",
        }
    )
    store.update_heartbeat("dev-1", uptime_ms=1234)
    store.update_device_info(
        {
            "type": "device_info",
            "device_id": "dev-1",
            "model": "draw-line-control-p1",
            "hw_rev": "p1",
            "workspace_mm": {"x": 120, "y": 80, "z": 20},
        }
    )
    store.update_self_check({"type": "self_check", "device_id": "dev-1", "status": "ok", "checks": ["u1"]})
    store.update_motion_event({"type": "motion_event", "device_id": "dev-1", "task_id": "task-1", "phase": "done"})

    snapshot = store.snapshot("dev-1")

    assert snapshot is not None
    assert snapshot["device_id"] == "dev-1"
    assert snapshot["fw_rev"] == "u8-test"
    assert snapshot["capabilities"] == ["home", "run_path"]
    assert snapshot["profile_id"] == "dlc-p1"
    assert snapshot["last_heartbeat_uptime_ms"] == 1234
    assert snapshot["device_info"]["model"] == "draw-line-control-p1"
    assert snapshot["self_check"]["status"] == "ok"
    assert snapshot["last_motion_event"]["phase"] == "done"


def test_shadow_delta_for_hello_is_v1_compatible():
    store = DeviceShadowStore()
    store.update_hello({"type": "hello", "device_id": "dev-1", "profile_id": "dlc-p1"})

    assert store.delta_for_hello("dev-1") == {
        "shadow": {
            "known": True,
            "profile_id": "dlc-p1",
            "desired": {},
        }
    }
