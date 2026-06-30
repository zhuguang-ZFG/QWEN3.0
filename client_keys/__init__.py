"""Client API key management for LiMa.

Exports the small public surface used by access_guard and admin routes.
"""

from __future__ import annotations

from config.settings import DB

from client_keys.models import ClientKey
from client_keys.quota import QuotaTracker
from client_keys.storage import ClientKeyStorage, ClientKeyStorageError, _mask_key


class _ClientKeysService:
    """Module-level singleton wrapping storage and quota tracker."""

    def __init__(self) -> None:
        self._storage: ClientKeyStorage | None = None
        self._quota: QuotaTracker | None = None

    def storage(self) -> ClientKeyStorage:
        if self._storage is None:
            self._storage = ClientKeyStorage(DB.client_keys_db)
        return self._storage

    def quota(self) -> QuotaTracker:
        if self._quota is None:
            self._quota = QuotaTracker(DB.client_keys_db)
        return self._quota

    def reset(self, db_path: str) -> None:
        """Replace backends (used by tests)."""
        self._storage = ClientKeyStorage(db_path)
        self._quota = QuotaTracker(db_path)


_service = _ClientKeysService()


def storage() -> ClientKeyStorage:
    return _service.storage()


def quota() -> QuotaTracker:
    return _service.quota()


def reset_for_tests(db_path: str) -> None:
    _service.reset(db_path)


def has_client_keys() -> bool:
    try:
        return bool(storage().list_all())
    except ClientKeyStorageError:
        return False


def find_client_key(key_value: str) -> ClientKey | None:
    return storage().get_by_value(key_value)


def try_consume_quota(key: ClientKey) -> tuple[bool, str]:
    return quota().try_consume_quota(key)


def check_key_quota(key: ClientKey) -> bool:
    return quota().check_key_quota(key)


def get_usage_summary(key_value: str) -> dict:
    return quota().usage_summary(key_value)


def check_allowed_urls(key: ClientKey, request_path: str) -> bool:
    allowed = key.allowed_urls
    if allowed is None or allowed == []:
        return False
    if "*" in allowed:
        return True
    return request_path in allowed


__all__ = [
    "ClientKey",
    "ClientKeyStorage",
    "ClientKeyStorageError",
    "QuotaTracker",
    "check_allowed_urls",
    "check_key_quota",
    "find_client_key",
    "get_usage_summary",
    "has_client_keys",
    "reset_for_tests",
    "storage",
    "try_consume_quota",
]
