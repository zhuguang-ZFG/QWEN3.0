"""Helper functions for device OTA routes."""

from __future__ import annotations

import json
import os
import re
import tempfile

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from config.env import ota_signing_public_key
from device_gateway.attestation import verifier as attestation_verifier
from device_ota.runtime import get_gradual
from device_ota.signature import FirmwareSignatureError, FirmwareVerifier

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FIRMWARE_HASHES_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "firmware_hashes.json")


def persist_firmware_hashes() -> None:
    """Atomically persist the in-memory firmware hash whitelist to disk."""
    try:
        directory = os.path.dirname(_FIRMWARE_HASHES_PATH)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False, suffix=".tmp") as fh:
            json.dump(attestation_verifier.list_hashes(), fh, indent=2, sort_keys=True)
            fh.write("\n")
            tmp_path = fh.name
        os.replace(tmp_path, _FIRMWARE_HASHES_PATH)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"failed to persist firmware hashes: {exc}") from exc


def gradual_json(extra: dict | None = None) -> JSONResponse:
    body = {"ok": True, **(extra or {}), "status": get_gradual().status_dict()}
    return JSONResponse(body)


def verify_firmware_or_raise(firmware: dict[str, str]) -> bool:
    public_key_pem = ota_signing_public_key()
    if not public_key_pem:
        raise HTTPException(status_code=503, detail="OTA signing public key is not configured")
    try:
        verifier = FirmwareVerifier(public_key_pem)
    except FirmwareSignatureError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return verifier.verify(firmware["url"], firmware["sha256"], firmware["signature"])


def device_list(value: object) -> list[str]:
    """Extract a list of non-empty device ids from a request payload."""
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def firmware_metadata(version: str, body: dict) -> dict[str, str]:
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
