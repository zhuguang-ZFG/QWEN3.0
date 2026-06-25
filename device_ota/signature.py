"""Firmware signature verification using Ed25519."""

from __future__ import annotations

import base64
import logging
from typing import cast

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_log = logging.getLogger(__name__)


class FirmwareSignatureError(Exception):
    """Raised when the configured signing key is missing or unusable."""


class FirmwareVerifier:
    """Verifies Ed25519 signatures over ``firmware_url + firmware_sha256``."""

    def __init__(self, public_key_pem: str | None) -> None:
        if not public_key_pem:
            raise FirmwareSignatureError("OTA signing public key is not configured")
        try:
            key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        except Exception as exc:
            raise FirmwareSignatureError(f"OTA signing public key is invalid: {type(exc).__name__}") from exc
        if not isinstance(key, Ed25519PublicKey):
            raise FirmwareSignatureError("OTA signing public key must be an Ed25519 key")
        self._public_key = cast(Ed25519PublicKey, key)

    def verify(self, firmware_url: str, firmware_sha256: str, signature: str) -> bool:
        """Return True when ``signature`` is a valid base64 Ed25519 signature."""
        message = (firmware_url + firmware_sha256).encode("utf-8")
        try:
            sig_bytes = base64.b64decode(signature, validate=True)
        except Exception as exc:
            _log.warning("OTA signature base64 decode failed: %s", type(exc).__name__)
            return False

        try:
            self._public_key.verify(sig_bytes, message)
        except InvalidSignature:
            return False
        except Exception as exc:
            _log.warning("OTA signature verify raised %s", type(exc).__name__)
            return False
        return True
