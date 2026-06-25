"""Device OTA release management routes."""
from __future__ import annotations
import json, os, re, tempfile
from fastapi import APIRouter, Body, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from access_guard import extract_bearer_token, require_private_api_key
from config.env import device_ota_state_path, ota_signing_public_key
from device_gateway.attestation import verifier as attestation_verifier
from device_gateway.auth import validate_device_token
from device_ota.canary import CanaryDeployment
from device_ota.gradual import GradualRollout
from device_ota.release import ReleaseGate
from device_ota.rollback_monitor import RollbackMonitor
from device_ota.signature import FirmwareSignatureError, FirmwareVerifier

router = APIRouter(prefix="/device/v1/ota", tags=["device-ota"])
_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FIRMWARE_HASHES_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "firmware_hashes.json")

def _state_path() -> str | None:
    return device_ota_state_path()

_gate = ReleaseGate(_state_path())

_canary = CanaryDeployment(_state_path())
_gradual = GradualRollout(_state_path())
_monitor = RollbackMonitor(_gradual, _canary)


def reset_ota_state_for_tests() -> None:
    global _gate, _canary, _gradual, _monitor
    _gate = ReleaseGate(_state_path())
    _canary = CanaryDeployment(_state_path())
    _gradual = GradualRollout(_state_path())
    _monitor = RollbackMonitor(_gradual, _canary)


def get_release_gate() -> ReleaseGate:
    return _gate


def get_canary() -> CanaryDeployment:
    return _canary


def get_gradual() -> GradualRollout:
    return _gradual


def _require_device_token(device_id: str, authorization: str) -> None:
    token = extract_bearer_token(authorization)
    if not validate_device_token(device_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/release/status", dependencies=[Depends(require_private_api_key)])
async def release_status():
    """Check OTA release gate status."""
    return JSONResponse(_gate.get_status())


@router.post("/release/criteria", dependencies=[Depends(require_private_api_key)])
async def set_criteria(name: str, passed: bool):
    """Set a release criterion (admin only)."""
    if not _gate.set_criteria(name, passed):
        raise HTTPException(status_code=400, detail=f"unknown criterion '{name}'; allowed: {list(_gate.criteria.keys())}")
    return JSONResponse({"ok": True, "name": name, "passed": passed})


@router.post("/deploy/{version}", dependencies=[Depends(require_private_api_key)])
async def deploy_version(version: str, body: dict | None = Body(default=None)):
    """Start deployment of a firmware version.

    Deployment is blocked until the release gate is ready. Canary counters are
    reset when a new version is deployed.
    """
    if not _gate.is_ready():
        raise HTTPException(status_code=412, detail="release gate not ready; all criteria must pass before deploy")
    firmware = _firmware_metadata(version, body or {})
    _canary.deploy_version(version, firmware)
    return JSONResponse({"ok": True, "version": version, "canary_devices": _canary.canary_devices, "firmware": firmware})


@router.get("/canary/status", dependencies=[Depends(require_private_api_key)])
async def canary_status():
    """Check canary deployment health."""
    return JSONResponse({"canary_devices": _canary.canary_devices, "deployed_version": _canary.deployed_version,
                         "success_count": _canary.success_count, "failure_count": _canary.failure_count,
                         "healthy": _canary.is_healthy()})


@router.post("/canary/devices/{device_id}", dependencies=[Depends(require_private_api_key)])
async def add_canary_device(device_id: str):
    """Add a device to the canary group."""
    _canary.add_canary_device(device_id)
    return JSONResponse({"ok": True, "device_id": device_id})


@router.delete("/canary/devices/{device_id}", dependencies=[Depends(require_private_api_key)])
async def remove_canary_device(device_id: str):
    """Remove a device from the canary group."""
    removed = _canary.remove_canary_device(device_id)
    return JSONResponse({"ok": removed, "device_id": device_id})


@router.post("/canary/record-success/{device_id}", dependencies=[Depends(require_private_api_key)])
async def record_canary_success(device_id: str):
    """Record a successful canary deployment for a device."""
    _canary.record_success(device_id)
    return JSONResponse({"ok": True, "device_id": device_id, "success_count": _canary.success_count,
                         "failure_count": _canary.failure_count, "healthy": _canary.is_healthy()})


@router.post("/canary/record-failure/{device_id}", dependencies=[Depends(require_private_api_key)])
async def record_canary_failure(device_id: str):
    """Record a failed canary deployment for a device."""
    _canary.record_failure(device_id)
    return JSONResponse({"ok": True, "device_id": device_id, "success_count": _canary.success_count,
                         "failure_count": _canary.failure_count, "healthy": _canary.is_healthy()})


@router.post("/upgrade-plan")
async def device_upgrade_plan(body: dict, authorization: str = Header(default="")):
    """Device-facing OTA check endpoint."""
    device_id = str(body.get("device_id") or "").strip()
    current_version = str(body.get("current_version") or "").strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    _require_device_token(device_id, authorization)
    firmware = _canary.firmware
    if (
        not _canary.deployed_version
        or current_version == _canary.deployed_version
        or not firmware
        or not _canary.is_canary(device_id)
    ):
        return JSONResponse({"firmware": None})
    return JSONResponse({"firmware": firmware})


@router.post("/install-result")
async def device_install_result(body: dict, authorization: str = Header(default="")):
    """Device-facing OTA install result endpoint."""
    device_id = str(body.get("device_id") or "").strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    _require_device_token(device_id, authorization)
    if not _canary.is_canary(device_id):
        raise HTTPException(status_code=403, detail="device is not in canary rollout")
    success = bool(body.get("success"))
    if success:
        _canary.record_success(device_id)
    else:
        _canary.record_failure(device_id)
    return JSONResponse({"ok": True, "device_id": device_id, "success_count": _canary.success_count,
                         "failure_count": _canary.failure_count, "healthy": _canary.is_healthy()})


@router.post("/gradual/start/{version}", dependencies=[Depends(require_private_api_key)])
async def start_gradual_release(version: str, body: dict | None = Body(default=None)):
    """Start a new gradual rollout; signature is verified before any state changes."""
    payload = body or {}
    firmware = _firmware_metadata(version, payload)
    devices = _device_list(payload.get("devices"))
    if not devices:
        raise HTTPException(status_code=400, detail="devices list is required")

    if not _verify_firmware_or_raise(firmware):
        raise HTTPException(status_code=400, detail="firmware signature verification failed")

    _gradual.start(version, devices, firmware)
    status = _gradual.status_dict()
    return JSONResponse({"ok": True, "version": version, "stage": status["stage"], "ratio": status["ratio"],
                         "selected_devices": status["selected_devices"], "status": status})


@router.post("/gradual/promote", dependencies=[Depends(require_private_api_key)])
async def promote_gradual_stage():
    """Manually advance to the next rollout stage."""
    return _gradual_json({"promoted": _gradual.promote()})


@router.post("/gradual/rollback", dependencies=[Depends(require_private_api_key)])
async def rollback_gradual_stage():
    """Manually move one rollout stage back."""
    return _gradual_json({"rolled_back": _gradual.rollback()})


@router.get("/gradual/status", dependencies=[Depends(require_private_api_key)])
async def gradual_status():
    """Return current rollout stage, counters, and selected devices."""
    return JSONResponse(_gradual.status_dict())


@router.post("/gradual/record-success/{device_id}", dependencies=[Depends(require_private_api_key)])
async def record_gradual_success(device_id: str):
    """Record a successful deployment for the current stage."""
    _gradual.record_success(device_id)
    return _gradual_json()


@router.post("/gradual/record-failure/{device_id}", dependencies=[Depends(require_private_api_key)])
async def record_gradual_failure(device_id: str):
    """Record a failed deployment for the current stage."""
    _gradual.record_failure(device_id)
    return _gradual_json()


@router.post("/verify-signature", dependencies=[Depends(require_private_api_key)])
async def verify_firmware_signature(body: dict | None = Body(default=None)):
    """Ad-hoc Ed25519 firmware signature verification."""
    payload = body or {}
    url = str(payload.get("url") or "").strip()
    sha256 = str(payload.get("sha256") or "").strip()
    signature = str(payload.get("signature") or "").strip()
    if not url or not sha256 or not signature:
        raise HTTPException(status_code=400, detail="url, sha256, and signature are required")
    firmware = {"url": url, "sha256": sha256, "signature": signature}
    return JSONResponse({"valid": _verify_firmware_or_raise(firmware)})


@router.get("/firmware-hashes", dependencies=[Depends(require_private_api_key)])
async def list_firmware_hashes():
    """List registered known-good firmware hashes (admin only)."""
    return JSONResponse({"hashes": attestation_verifier.list_hashes()})


@router.post("/firmware-hashes", dependencies=[Depends(require_private_api_key)])
async def register_firmware_hash(body: dict = Body(...)):
    """Register a known-good firmware hash (admin only)."""
    version = str(body.get("version") or "").strip()
    hash_value = str(body.get("hash") or "").strip().lower()
    if not version:
        raise HTTPException(status_code=400, detail="version is required")
    if not _LOWER_HEX_SHA256.match(hash_value):
        raise HTTPException(status_code=400, detail="hash must be 64 lowercase hex chars")
    hash_value = f"sha256:{hash_value}"
    attestation_verifier.register(version, hash_value)
    _persist_firmware_hashes()
    return JSONResponse({"ok": True, "version": version, "hash": hash_value})


def _persist_firmware_hashes() -> None:
    """Atomically persist the in-memory firmware hash whitelist to disk."""
    try:
        directory = os.path.dirname(_FIRMWARE_HASHES_PATH)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=directory, delete=False, suffix=".tmp"
        ) as fh:
            json.dump(attestation_verifier.list_hashes(), fh, indent=2, sort_keys=True)
            fh.write("\n")
            tmp_path = fh.name
        os.replace(tmp_path, _FIRMWARE_HASHES_PATH)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"failed to persist firmware hashes: {exc}") from exc


def _gradual_json(extra: dict | None = None) -> JSONResponse:
    body = {"ok": True, **(extra or {}), "status": _gradual.status_dict()}
    return JSONResponse(body)


def _verify_firmware_or_raise(firmware: dict[str, str]) -> bool:
    public_key_pem = ota_signing_public_key()
    if not public_key_pem:
        raise HTTPException(status_code=503, detail="OTA signing public key is not configured")
    try:
        verifier = FirmwareVerifier(public_key_pem)
    except FirmwareSignatureError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return verifier.verify(firmware["url"], firmware["sha256"], firmware["signature"])


def _device_list(value: object) -> list[str]:
    """Extract a list of non-empty device ids from a request payload."""
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _firmware_metadata(version: str, body: dict) -> dict[str, str]:
    url = str(body.get("url") or "").strip()
    sha256 = str(body.get("sha256") or "").strip()
    signature = str(body.get("signature") or "").strip()
    if not url and not sha256 and not signature:
        return {}
    if not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="firmware url must use https")
    if not _LOWER_HEX_SHA256.match(sha256):
        raise HTTPException(status_code=400, detail="firmware sha256 must be 64 lowercase hex chars")
    if not signature:
        raise HTTPException(status_code=400, detail="firmware signature is required")
    return {
        "release_id": str(body.get("release_id") or version),
        "version": version,
        "url": url,
        "sha256": sha256,
        "signature": signature,
        "force": str(body.get("force") or "0"),
    }
