"""Pytest MonkeyPatch wrapper that syncs os.environ changes to config singletons."""

from __future__ import annotations

import os
from typing import Any

from tests._env_sync_maps import (
    _brand_map,
    _device_map,
    _digital_human_map,
    _flags_map,
    _gemini_map,
    _integrations_map,
    _ota_map,
    _outcome_map,
    _security_map,
    _session_memory_map,
    _upload_map,
    _voice_map,
    _voiceprint_map,
)
from tests._env_sync_runtime_maps import (
    _backend_ops_map,
    _db_map,
    _embedding_map,
    _fleet_map,
    _paths_map,
)
from tests._env_sync_observability_maps import _observability_map
from tests._env_sync_voice_maps import _voice_providers_map


class _EnvSyncMonkeyPatch:
    """Wrapper that forwards to pytest's MonkeyPatch and syncs env changes to singletons."""

    def __init__(self, mp: Any) -> None:
        self._mp = mp
        self._originals: list[tuple[Any, str, Any]] = []

    def _capture(self, obj: Any, attr: str) -> None:
        for o, a, _ in self._originals:
            if o is obj and a == attr:
                return
        self._originals.append((obj, attr, getattr(obj, attr)))

    def _set(self, obj: Any, attr: str, value: Any) -> None:
        self._capture(obj, attr)
        setattr(obj, attr, value)

    def setenv(self, name: str, value: str, prepend: bool | None = None) -> None:
        self._mp.setenv(name, value, prepend)
        self._sync(name, value)

    def delenv(self, name: str, raising: bool = True) -> None:
        self._mp.delenv(name, raising)
        self._sync(name, None)

    def _sync(self, name: str, value: str | None) -> None:
        """Mirror legacy monkeypatch.setenv calls onto config singletons (P1-2)."""
        from config import backend_config, settings

        if name == "LIMA_JWT_SECRET" and not os.environ.get("LIMA_UPLOAD_TOKEN_SECRET"):
            self._set(settings.SECURITY, "jwt_secret", value or "")
            self._set(settings.UPLOAD, "token_secret", value or settings.UPLOAD.token_secret)
            return
        if name == "GOOGLE_AI_KEY":
            self._set(backend_config, "GOOGLE_AI_KEY", value or "")
            return
        if name == "GITEE_AI_TOKEN":
            self._set(backend_config, "GITEE_AI_TOKEN", value or "")
            return
        if name == "GITEE_AI_BASE_URL":
            self._set(
                backend_config,
                "GITEE_AI_BASE_URL",
                (value or "").strip() or "https://ai.gitee.com/v1",
            )
            return
        if name == "GITEE_AI_ENABLED":
            self._set(
                backend_config,
                "GITEE_AI_ENABLED",
                (value or "").strip().lower() in {"1", "true", "yes", "on"},
            )
            return
        if name in {"DASHSCOPE_API_KEY", "ALIYUN_API_KEY"}:
            val = (value or "").strip()
            self._set(settings.VOICE_PROVIDERS.dashscope_asr, "api_key", val)
            self._set(settings.VOICE_PROVIDERS.dashscope_tts, "api_key", val)
            return

        mapping = self._env_sync_map(settings)
        if name in mapping:
            obj, attr, converter = mapping[name]
            self._set(obj, attr, converter(value))

    def _env_sync_map(self, settings: Any) -> dict[str, tuple[Any, str, Any]]:
        """Return (singleton, attribute, converter) for each supported env var."""
        result: dict[str, tuple[Any, str, Any]] = {}
        for mapping in (
            _security_map,
            _device_map,
            _db_map,
            _fleet_map,
            _session_memory_map,
            _backend_ops_map,
            _embedding_map,
            _brand_map,
            _paths_map,
            _flags_map,
            _digital_human_map,
            _voice_map,
            _voiceprint_map,
            _voice_providers_map,
            _gemini_map,
            _outcome_map,
            _ota_map,
            _upload_map,
            _integrations_map,
            _observability_map,
        ):
            result.update(mapping(settings))
        return result

    def undo(self) -> None:
        for obj, attr, orig in self._originals:
            setattr(obj, attr, orig)
        self._originals.clear()
        self._mp.undo()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mp, name)
