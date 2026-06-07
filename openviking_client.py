"""Thin sync wrapper for OpenViking HTTP API (localhost:1933).

OpenViking is an optional dependency. If the server is unreachable,
all methods return safe defaults (empty strings, False).

Environment:
    OPENVIKING_URL: Override default http://localhost:1933
    LIMA_OPENVIKING_ENABLED: Set to "1" to enable (default: "0")
"""
import logging
import os
from urllib.request import urlopen, Request
from urllib.error import URLError

import json

_log = logging.getLogger(__name__)

_DEFAULT_URL = "http://localhost:1933"
_TIMEOUT = 5  # seconds — context retrieval must be fast


class OpenVikingClient:
    """Sync HTTP client for OpenViking server."""

    def __init__(self, base_url: str = "", timeout: int = _TIMEOUT) -> None:
        self.base_url = (
            base_url
            or os.environ.get("OPENVIKING_URL", "")
            or _DEFAULT_URL
        ).rstrip("/")
        self._timeout = timeout

    def is_available(self) -> bool:
        """Check if OpenViking server is reachable."""
        try:
            self._get("/health")
            return True
        except Exception:
            return False

    def find(self, query: str, top_k: int = 5) -> list[dict]:
        """Semantic search across all Viking resources.

        Returns list of {"uri": str, "content": str, "score": float}.
        Returns empty list on any error.
        """
        try:
            data = self._post("/api/v1/find", {"query": query, "top_k": top_k})
            return data.get("results", [])
        except Exception as exc:
            _log.debug("openviking find failed: %s", exc)
            return []

    def read(self, uri: str, layer: str = "L1") -> str:
        """Read a specific Viking URI at the given layer (L0/L1/L2).

        Returns the text content, or empty string on error.
        """
        try:
            data = self._post("/api/v1/read", {"uri": uri, "layer": layer})
            return data.get("content", "")
        except Exception as exc:
            _log.debug("openviking read failed: %s", exc)
            return ""

    def format_context(self, results: list[dict], max_chars: int = 1500) -> str:
        """Format retrieval results into injectable context text."""
        if not results:
            return ""
        lines = ["[OpenViking Context]"]
        total = 0
        for r in results:
            uri = r.get("uri", "unknown")
            content = r.get("content", "")
            entry = f"- {uri}: {content[:200]}"
            if total + len(entry) > max_chars:
                break
            lines.append(entry)
            total += len(entry)
        return "\n".join(lines)

    # ── Internal HTTP helpers ──────────────────────────────────────────

    def _get(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        req = Request(url, method="GET")
        with urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read())

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8")
        req = Request(url, data=data, method="POST", headers={
            "Content-Type": "application/json",
        })
        with urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read())


# ── Singleton accessor ────────────────────────────────────────────────────

_client: OpenVikingClient | None = None


def get_openviking_client() -> OpenVikingClient | None:
    """Return singleton client if enabled, else None.

    Controlled by LIMA_OPENVIKING_ENABLED env var (default "0").
    """
    global _client
    if os.environ.get("LIMA_OPENVIKING_ENABLED", "0") != "1":
        return None
    if _client is None:
        _client = OpenVikingClient()
    return _client
