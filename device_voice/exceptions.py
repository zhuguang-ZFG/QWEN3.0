"""Shared exceptions for the device_voice pipeline.

These exceptions make provider failures explicit and allow the WebSocket/HTTP
callers to decide whether to degrade gracefully (e.g. return an error frame)
instead of silently swallowing errors.
"""

from __future__ import annotations


class VoiceProviderError(RuntimeError):
    """Base class for device_voice provider failures."""


class AuthenticationError(VoiceProviderError):
    """Raised when a provider rejects credentials or they are missing."""


class ConfigurationError(VoiceProviderError):
    """Raised when required configuration is missing or invalid."""


class NetworkError(VoiceProviderError):
    """Raised when a provider request fails due to network issues."""


class RateLimitError(VoiceProviderError):
    """Raised when a provider throttles the request."""


class ModelUnavailableError(VoiceProviderError):
    """Raised when a local model cannot be loaded."""


__all__ = [
    "VoiceProviderError",
    "AuthenticationError",
    "ConfigurationError",
    "NetworkError",
    "RateLimitError",
    "ModelUnavailableError",
]
