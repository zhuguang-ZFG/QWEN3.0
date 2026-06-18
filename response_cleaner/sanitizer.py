"""Streaming identity sanitizer with cross-chunk holdback."""

from response_cleaner.core import clean_response
from response_cleaner.identity import _looks_like_self_identity, apply_identity_cleaning


class StreamIdentitySanitizer:
    """Hold back trailing bytes so cross-chunk identity leaks can be cleaned."""

    HOLD_BACK = 96

    def __init__(self, backend: str = ""):
        self._backend = backend
        self._buffer = ""

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        self._buffer += chunk
        if len(self._buffer) <= self.HOLD_BACK:
            return ""
        emit_raw = self._buffer[: -self.HOLD_BACK]
        self._buffer = self._buffer[-self.HOLD_BACK :]
        return self._clean_emit(emit_raw)

    def flush(self) -> str:
        if not self._buffer:
            return ""
        out = self._clean_emit(self._buffer)
        self._buffer = ""
        return out

    def _clean_emit(self, text: str) -> str:
        cleaned = clean_response(text, self._backend)
        if cleaned:
            return cleaned
        if _looks_like_self_identity(text):
            from identity_guard import filter_identity_leak

            return filter_identity_leak(apply_identity_cleaning(text))
        return text
