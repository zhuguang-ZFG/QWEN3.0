"""Shared request helpers for sync and async clients."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from lima_sdk.exceptions import LiMaAPIError

if TYPE_CHECKING:
    from lima_sdk.client import AsyncLiMaClient, LiMaClient


def _bearer_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    status = response.status_code
    try:
        body = response.json()
    except Exception:
        body = {}
    message = body.get("message") or body.get("error", {}).get("message") or response.reason_phrase
    code = body.get("code") or body.get("error", {}).get("type")
    raise LiMaAPIError(
        str(message),
        status_code=status,
        code=str(code) if code else None,
        response_body=body,
    )


def _request_kwargs(json: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if json is not None:
        kwargs["json"] = json
    if params is not None:
        kwargs["params"] = params
    return kwargs


class _BaseResource:
    """Base class for sync resource namespaces."""

    def __init__(self, client: "LiMaClient") -> None:  # type: ignore[name-defined]
        self._client = client

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> httpx.Response:
        return self._client._request("GET", path, params=params)

    def _post(self, path: str, *, json: dict[str, Any] | None = None) -> httpx.Response:
        return self._client._request("POST", path, json=json)

    def _delete(self, path: str) -> httpx.Response:
        return self._client._request("DELETE", path)


class _BaseAsyncResource:
    """Base class for async resource namespaces."""

    def __init__(self, client: "AsyncLiMaClient") -> None:  # type: ignore[name-defined]
        self._client = client

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> httpx.Response:
        return await self._client._request("GET", path, params=params)

    async def _post(self, path: str, *, json: dict[str, Any] | None = None) -> httpx.Response:
        return await self._client._request("POST", path, json=json)

    async def _delete(self, path: str) -> httpx.Response:
        return await self._client._request("DELETE", path)
