"""Firmware remote attestation verifier for device gateway (F5)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
from dataclasses import dataclass
from typing import Any

_log = logging.getLogger(__name__)

_DEFAULT_HASH_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "firmware_hashes.json")
_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

ACTION_FULL_ACCESS = "full_access"
ACTION_READ_ONLY = "read_only"
ACTION_QUARANTINE = "quarantine"


@dataclass(frozen=True)
class AttestationResult:
    """Result of a firmware attestation check."""

    action: str  # full_access | read_only | quarantine
    version: str
    expected_hash: str
    actual_hash: str
    reason: str


class AttestationVerifier:
    """Thread-safe verifier of known-good firmware hashes."""

    def __init__(self, path: str | None = None) -> None:
        self._path = path or _DEFAULT_HASH_PATH
        self._hashes: dict[str, str] = {}
        self._lock = threading.RLock()

    def reload_hashes(self, path: str | None = None) -> None:
        """Load version -> sha256:... mappings from JSON file."""
        target = path or self._path
        if not target:
            return
        try:
            with open(target, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            _log.warning("firmware hash whitelist not found: %s", target)
            with self._lock:
                self._hashes = {}
            return
        except json.JSONDecodeError as exc:
            _log.warning("firmware hash whitelist malformed: %s", exc)
            with self._lock:
                self._hashes = {}
            return
        if not isinstance(data, dict):
            _log.warning("firmware hash whitelist must be a JSON object")
            with self._lock:
                self._hashes = {}
            return
        normalized: dict[str, str] = {}
        for version, raw_hash in data.items():
            h = str(raw_hash).strip().lower()
            if not _HASH_PATTERN.match(h):
                _log.warning("ignoring invalid firmware hash for %r", version)
                continue
            normalized[str(version).strip()] = h
        with self._lock:
            self._hashes = normalized

    def verify(
        self,
        device_id: str,
        firmware_hash: str,
        firmware_version: str,
    ) -> AttestationResult:
        """Return an attestation decision for the reported firmware."""
        actual = self._normalize_hash(firmware_hash)
        version = (firmware_version or "").strip()
        with self._lock:
            expected = self._hashes.get(version, "")
        if not version or not expected:
            return AttestationResult(
                action=ACTION_QUARANTINE,
                version=version,
                expected_hash=expected,
                actual_hash=actual,
                reason="unknown firmware version",
            )
        if actual != expected:
            return AttestationResult(
                action=ACTION_READ_ONLY,
                version=version,
                expected_hash=expected,
                actual_hash=actual,
                reason="firmware hash mismatch",
            )
        return AttestationResult(
            action=ACTION_FULL_ACCESS,
            version=version,
            expected_hash=expected,
            actual_hash=actual,
            reason="firmware attestation passed",
        )

    def list_hashes(self) -> dict[str, str]:
        """Return a snapshot of registered version -> hash mappings."""
        with self._lock:
            return dict(self._hashes)

    def register(self, version: str, hash_value: str) -> None:
        """Register a new known-good firmware hash in memory."""
        normalized = self._normalize_hash(hash_value)
        if not normalized:
            raise ValueError("hash must be sha256:64 lowercase hex chars")
        with self._lock:
            self._hashes[version.strip()] = normalized

    @staticmethod
    def _normalize_hash(value: str) -> str:
        value = (value or "").strip().lower()
        if _HASH_PATTERN.match(value):
            return value
        return ""


def compute_firmware_hash(firmware_bytes: bytes) -> str:
    """Compute sha256:... hash of raw firmware bytes."""
    digest = hashlib.sha256(firmware_bytes).hexdigest()
    return f"sha256:{digest}"


def _load_default_hashes() -> AttestationVerifier:
    instance = AttestationVerifier()
    try:
        instance.reload_hashes()
    except Exception as exc:  # noqa: BLE001 — guard startup against unexpected IO issues
        _log.warning("failed to load firmware hashes at startup: %s", exc)
    return instance


verifier: AttestationVerifier = _load_default_hashes()
