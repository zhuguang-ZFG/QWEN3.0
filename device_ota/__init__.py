"""Device OTA (Over-The-Air) updates with canary deployment.

Safe release gate before touching production devices.
"""
from device_ota.release import ReleaseGate
from device_ota.canary import CanaryDeployment

__all__ = ["ReleaseGate", "CanaryDeployment"]
