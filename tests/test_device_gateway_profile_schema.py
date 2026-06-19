"""Device intelligence profile schema tests."""

from unittest.mock import AsyncMock

import pytest

from device_gateway.device_route_memory import reset_route_memory_for_tests
from device_gateway.profiles import reset_profiles_for_tests
from device_intelligence.schemas import DeviceProfile


def setup_function():
    reset_profiles_for_tests()
    reset_route_memory_for_tests()


@pytest.fixture(autouse=True)
def _mock_device_draw(monkeypatch):
    monkeypatch.setattr(
        "device_gateway.task_draw_params.handle_device_draw",
        AsyncMock(
            return_value={
                "status": "success",
                "image_url": "",
                "svg_path": "M 10 10 L 50 50 L 90 10 Z",
                "width": 180,
                "height": 180,
                "model": "test-draw",
                "error": None,
            }
        ),
    )


def test_device_intelligence_profile_fields():
    profile = DeviceProfile(
        profile_id="test-id",
        model="test-model",
        workspace_mm={"x": 100.0, "y": 100.0, "z": 20.0},
        max_feed=1200.0,
        max_path_points=200,
        supported_fw_prefixes=("v2.",),
        profile_version="1.2",
        fw_rev="v2.1.0",
        u1_fw_rev="u1-1.0",
        hw_rev="hw-v1",
        limits={"max_points": 200},
    )

    assert profile.profile_id == "test-id"
    assert profile.model == "test-model"
    assert profile.fw_rev == "v2.1.0"
    assert profile.u1_fw_rev == "u1-1.0"
    assert profile.hw_rev == "hw-v1"
    assert profile.limits == {"max_points": 200}


def test_device_intelligence_profile_to_dict_includes_new_fields():
    profile = DeviceProfile(
        profile_id="test-id",
        model="test-model",
        fw_rev="v2.1.0",
        u1_fw_rev="u1-1.0",
        hw_rev="hw-v1",
        limits={"max_points": 200},
    )

    d = profile.to_dict()
    assert d["fw_rev"] == "v2.1.0"
    assert d["u1_fw_rev"] == "u1-1.0"
    assert d["hw_rev"] == "hw-v1"
    assert d["limits"] == {"max_points": 200}
