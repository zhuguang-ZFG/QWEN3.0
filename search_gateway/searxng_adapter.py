"""SearXNG meta-search adapter for dev-search (PE-D-1)."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from .safety import is_public_http_url, redact_sensitive_query

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 300.0
_DEFAULT_COOLDOWN = 60.0
_DEFAULT_TIMEOUT = 12.0


def searxng_enabled() -> bool:
    return os.environ.get("SEARXNG_ENABLED", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _base_url() -> str:
    return os.environ.get("SEARXNG_BASE_URL", "http://127.0.0.1:8081").strip().rstrip("/")


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
class SearXNGAdapter:
    base_url: str
    cache_ttl: float = _DEFAULT_TTL
    cooldown_sec: float = _DEFAULT_COOLDOWN
    timeout: float = _DEFAULT_TIMEOUT
    _cache: dict[str, _CacheEntry] = field(default_factory=dict)
    _cooldown_until: float = 0.0

    @classmethod
    def from_env(cls) -> SearXNGAdapter:
        return cls(
            base_url=_base_url(),
            cache_ttl=_float_env("SEARXNG_CACHE_TTL", _DEFAULT_TTL),
            cooldown_sec=_float_env("SEARXNG_COOLDOWN_SEC", _DEFAULT_COOLDOWN),
            timeout=_float_env("SEARXNG_TIMEOUT", _DEFAULT_TIMEOUT),
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
        req = urllib.request.Request(url, headers={"User-Agent": "LiMa-SearXNG/1.0"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _build_query(self, query: str, *, domain: str | None) -> str:
        q = redact_sensitive_query(query)
        if domain:
            q = f"site:{domain.strip()} {q}"
        return q

    def _normalize(
        self, raw: dict, *, max_results: int, categories: str = "general"
    ) -> list[dict]:
        items = raw.get("results") if isinstance(raw, dict) else []
        if not isinstance(items, list):
            return []
        out: list[dict] = []
        for item in items[:max_results]:
            if not isinstance(item, dict):
                continue
            engine = str(item.get("engine") or "searxng")
            entry = {
                "title": str(item.get("title") or "Untitled")[:200],
                "url": str(item.get("url") or item.get("link") or "")[:500],
                "snippet": str(item.get("content") or item.get("snippet") or "")[:1000],
                "source": f"searxng:{engine}",
            }
            if categories == "videos":
                thumbnail = str(item.get("thumbnail") or item.get("img_src") or "")
                duration = str(item.get("duration") or item.get("length") or "")
                uploader = str(item.get("uploader") or item.get("author") or "")
                if thumbnail:
                    entry["thumbnail"] = thumbnail[:500]
                if duration:
                    entry["duration"] = duration[:20]
                if uploader:
                    entry["uploader"] = uploader[:100]
            out.append(entry)
        return out

    def search(
        self,
        query: str,
        *,
        domain: str | None = None,
        max_results: int = 5,
        categories: str = "general",
    ) -> dict:
        if self._in_cooldown():
            return {"ok": False, "error": "searxng_cooldown"}

        q = self._build_query(query, domain=domain)
        cache_key = f"search:{categories}:{q}:{max_results}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            cached = dict(cached)
            cached["cached"] = True
            return cached

        params = urllib.parse.urlencode(
            {"q": q, "format": "json", "language": "en", "categories": categories}
        )
        url = f"{self.base_url}/search?{params}"
        try:
            raw = self._http_get_json(url)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503):
                self._enter_cooldown()
            logger.warning("searxng search http error: %s", exc.code)
            return {"ok": False, "error": f"searxng_http_{exc.code}"}
        except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError) as exc:
            logger.warning("searxng search failed: %s", type(exc).__name__)
            return {"ok": False, "error": "searxng_unreachable"}

        results = self._normalize(raw, max_results=max_results, categories=categories)
        payload = {"ok": True, "results": results, "source": "searxng"}
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
        if not is_public_http_url(url):
            return {"ok": False, "error": "url_blocked"}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "LiMa-SearXNG/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read(120_000).decode("utf-8", errors="replace")
            return {"ok": True, "text": body, "source": "searxng_fetch"}
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            return {"ok": False, "error": str(exc)[:100]}
