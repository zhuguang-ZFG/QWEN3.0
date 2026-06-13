"""Tests for OTA release gate and canary deployment."""
from device_ota.release import ReleaseGate
from device_ota.canary import CanaryDeployment


def test_release_gate_blocks_by_default():
    """Release gate blocks deployment until all criteria pass."""
    gate = ReleaseGate()
    assert gate.is_ready() is False


def test_release_gate_allows_when_ready():
    """Release gate allows deployment when all criteria pass."""
    gate = ReleaseGate()
    gate.set_criteria("tests_passing", True)
    gate.set_criteria("canary_verified", True)
    gate.set_criteria("safety_review", True)
    assert gate.is_ready() is True


def test_release_gate_status():
    """Release gate returns status."""
    gate = ReleaseGate()
    gate.set_criteria("tests_passing", True)
    status = gate.get_status()
    assert status["ready"] is False
    assert status["criteria"]["tests_passing"] is True


def test_canary_identifies_devices():
    """Canary deployment identifies canary devices."""
    canary = CanaryDeployment()
    canary.add_canary_device("dev_canary_1")
    assert canary.is_canary("dev_canary_1") is True
    assert canary.is_canary("dev_prod_1") is False


def test_canary_tracks_success_rate():
    """Canary tracks success/failure rate."""
    canary = CanaryDeployment()
    canary.add_canary_device("dev_1")
    canary.add_canary_device("dev_2")

    canary.record_success("dev_1")
    canary.record_success("dev_2")

    assert canary.is_healthy(threshold=0.9) is True


def test_canary_fails_on_low_success_rate():
    """Canary fails when success rate is too low."""
    canary = CanaryDeployment()
    canary.add_canary_device("dev_1")
    canary.add_canary_device("dev_2")

    canary.record_success("dev_1")
    canary.record_failure("dev_2")

    assert canary.is_healthy(threshold=0.9) is False  # 50% < 90%


def test_canary_not_healthy_without_data():
    """Canary is not healthy without deployment data."""
    canary = CanaryDeployment()
    canary.add_canary_device("dev_1")
    assert canary.is_healthy() is False  # No data yet
