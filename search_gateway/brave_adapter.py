"""Brave Search API adapter for LiMa dev-search (PE-D tier, default off)."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from search_gateway.safety import redact_sensitive_query

_log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 12.0
_DEFAULT_TTL = 300.0
_DEFAULT_COOLDOWN = 60.0


def brave_search_enabled() -> bool:
    if os.environ.get("BRAVE_SEARCH_ENABLED", "0").strip().lower() not in {"1", "true", "yes"}:
        return False
    return bool(_api_key())


def _api_key() -> str:
    return (
        os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
        or os.environ.get("BRAVE_API_KEY", "").strip()
    )


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass
class _CacheEntry:
    expires: float
    payload: dict


@dataclass
class BraveSearchAdapter:
    api_key: str
    cache_ttl: float = _DEFAULT_TTL
    cooldown_sec: float = _DEFAULT_COOLDOWN
    timeout: float = _DEFAULT_TIMEOUT
    _cache: dict[str, _CacheEntry] = field(default_factory=dict)
    _cooldown_until: float = 0.0

    @classmethod
    def from_env(cls) -> BraveSearchAdapter:
        return cls(
            api_key=_api_key(),
            cache_ttl=_float_env("BRAVE_SEARCH_CACHE_TTL", _DEFAULT_TTL),
            cooldown_sec=_float_env("BRAVE_SEARCH_COOLDOWN_SEC", _DEFAULT_COOLDOWN),
            timeout=_float_env("BRAVE_SEARCH_TIMEOUT", _DEFAULT_TIMEOUT),
        )

    def _cache_get(self, key: str) -> dict | None:
        entry = self._cache.get(key)
        if not entry:
            return None
        if time.monotonic() >= entry.expires:
            del self._cache[key]
            return None
        return entry.payload

    def _cache_set(self, key: str, payload: dict) -> None:
        self._cache[key] = _CacheEntry(time.monotonic() + self.cache_ttl, payload)

    def _in_cooldown(self) -> bool:
        return time.monotonic() < self._cooldown_until

    def _enter_cooldown(self) -> None:
        self._cooldown_until = time.monotonic() + self.cooldown_sec

    def _http_get_json(self, url: str) -> dict:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "LiMa-BraveSearch/1.0",
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key,
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _build_query(self, query: str, *, domain: str | None) -> str:
        q = redact_sensitive_query(query)
        if domain:
            q = f"site:{domain.strip()} {q}"
        return q

    def _normalize(self, raw: dict, *, max_results: int) -> list[dict]:
        web = raw.get("web") if isinstance(raw, dict) else {}
        items = web.get("results") if isinstance(web, dict) else []
        results: list[dict] = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            results.append(
                {
                    "title": str(item.get("title") or "")[:200],
                    "url": url,
                    "snippet": str(item.get("description") or "")[:500],
                    "source": "brave:web",
                }
            )
            if len(results) >= max_results:
                break
        return results

    def search(self, query: str, *, domain: str | None = None, max_results: int = 5) -> dict:
        if not self.api_key:
            return {"ok": False, "error": "brave_api_key_missing"}
        q = self._build_query(query, domain=domain)
        if not q:
            return {"ok": False, "error": "empty_query"}
        cache_key = f"search:{q}:{max_results}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        if self._in_cooldown():
            return {"ok": False, "error": "brave_cooldown"}

        params = urllib.parse.urlencode({"q": q, "count": max(1, min(max_results, 20))})
        url = f"https://api.search.brave.com/res/v1/web/search?{params}"
        try:
            raw = self._http_get_json(url)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503):
                self._enter_cooldown()
            _log.warning("brave search HTTP %s", exc.code)
            return {"ok": False, "error": f"brave_http_{exc.code}"}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            _log.warning("brave search failed: %s", type(exc).__name__)
            return {"ok": False, "error": type(exc).__name__}

        results = self._normalize(raw, max_results=max_results)
        payload = {"ok": True, "results": results, "source": "brave"}
        self._cache_set(cache_key, payload)
        return payload

    def batch_search(
        self, queries: list[str], *, domain: str | None = None, max_results: int = 5
    ) -> dict:
        merged: list[dict] = []
        for query in queries:
            one = self.search(query, domain=domain, max_results=max_results)
            if not one.get("ok"):
                return one
            merged.extend(one.get("results") or [])
        return {"ok": True, "results": merged[: max_results * max(1, len(queries))]}

    def extract_url(self, url: str) -> dict:
        from search_gateway.safety import is_public_http_url

        if not is_public_http_url(url):
            return {"ok": False, "error": "url_blocked"}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "LiMa-BraveSearch/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read(120_000).decode("utf-8", errors="replace")
            return {"ok": True, "text": body, "source": "brave_fetch"}
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            return {"ok": False, "error": str(exc)[:100]}
