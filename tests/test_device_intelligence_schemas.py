import pytest

from device_intelligence.schemas import DeviceProfile, TaskPlan


def test_device_profile_rejects_empty_profile_id():
    with pytest.raises(ValueError, match="profile_id"):
        DeviceProfile(profile_id="", model="dlc-p1")


def test_device_profile_serializes_deterministically():
    profile = DeviceProfile(
        profile_id="dlc-p1",
        model="draw-line-control-p1",
        workspace_mm={"y": 80, "x": 120, "z": 20},
        max_feed=900,
        capabilities=("run_path", "home"),
        supported_fw_prefixes=("u8-",),
    )

    assert profile.to_dict() == {
        "profile_id": "dlc-p1",
        "model": "draw-line-control-p1",
        "workspace_mm": {"x": 120.0, "y": 80.0, "z": 20.0},
        "max_feed": 900.0,
        "max_path_points": 200,
        "capabilities": ["home", "run_path"],
        "supported_fw_prefixes": ["u8-"],
        "profile_version": "1",
    }
    assert profile.to_json() == (
        '{"capabilities":["home","run_path"],"max_feed":900.0,"max_path_points":200,'
        '"model":"draw-line-control-p1","profile_id":"dlc-p1","profile_version":"1",'
        '"supported_fw_prefixes":["u8-"],"workspace_mm":{"x":120.0,"y":80.0,"z":20.0}}'
    )


def test_task_plan_rejects_empty_plan_id_and_serializes():
    with pytest.raises(ValueError, match="plan_id"):
        TaskPlan(plan_id="", device_id="dev-1", capability="run_path", params={})

    plan = TaskPlan(
        plan_id="plan-1",
        device_id="dev-1",
        capability="run_path",
        params={"feed": 500, "path": [{"x": 1, "y": 2, "z": 0}]},
        profile_id="dlc-p1",
    )

    assert plan.to_dict()["profile_id"] == "dlc-p1"
    assert plan.to_json().startswith('{"capability":"run_path","device_id":"dev-1"')
