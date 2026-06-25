"""Runtime singletons for the OTA subsystem.

Owns the module-level instances of the release gate, canary deployment,
gradual rollout, and rollback monitor. Route modules (routes/device_ota.py,
routes/device_ota_app.py) import from here so the OTA domain lifecycle is
not subordinate to an HTTP adapter. Tests reset state via
``reset_for_tests()`` instead of poking sibling route privates.
"""
from __future__ import annotations

from config.env import device_ota_state_path
from device_ota.canary import CanaryDeployment
from device_ota.gradual import GradualRollout
from device_ota.release import ReleaseGate
from device_ota.rollback_monitor import RollbackMonitor

_gate = ReleaseGate(device_ota_state_path())
_canary = CanaryDeployment(device_ota_state_path())
_gradual = GradualRollout(device_ota_state_path())
_monitor = RollbackMonitor(_gradual, _canary)


def reset_for_tests() -> None:
    """Rebuild all four singletons from the current env state path."""
    global _gate, _canary, _gradual, _monitor
    _gate = ReleaseGate(device_ota_state_path())
    _canary = CanaryDeployment(device_ota_state_path())
    _gradual = GradualRollout(device_ota_state_path())
    _monitor = RollbackMonitor(_gradual, _canary)


def get_release_gate() -> ReleaseGate:
    return _gate


def get_canary() -> CanaryDeployment:
    return _canary


def get_gradual() -> GradualRollout:
    return _gradual


def get_monitor() -> RollbackMonitor:
    return _monitor
