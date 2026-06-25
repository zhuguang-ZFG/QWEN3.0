"""LiMa sync and async SDK clients."""

from __future__ import annotations

from typing import Any, AsyncIterator, Iterator

import httpx

from lima_sdk._base import _BaseAsyncResource, _BaseResource, _bearer_headers, _raise_for_status, _request_kwargs
from lima_sdk._streaming import iter_sse_chunks


class _ChatCompletions(_BaseResource):
    def create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | Iterator[dict[str, Any]]:
        body: dict[str, Any] = {"model": model, "messages": messages, "stream": stream}
        body.update(kwargs)
        response = self._post("/v1/chat/completions", json=body)
        if stream:
            _raise_for_status(response)
            return iter_sse_chunks(response)
        _raise_for_status(response)
        return response.json()


class _AsyncChatCompletions(_BaseAsyncResource):
    async def create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
        body: dict[str, Any] = {"model": model, "messages": messages, "stream": stream}
        body.update(kwargs)
        response = await self._post("/v1/chat/completions", json=body)
        if stream:
            _raise_for_status(response)
            return self._async_sse_iter(response)
        _raise_for_status(response)
        return response.json()

    async def _async_sse_iter(self, response: httpx.Response) -> AsyncIterator[dict[str, Any]]:
        for chunk in iter_sse_chunks(response):
            yield chunk


class _Images(_BaseResource):
    def generate(
        self,
        *,
        model: str,
        prompt: str,
        size: str = "1024x1024",
        n: int = 1,
        **kwargs: Any,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"model": model, "prompt": prompt, "size": size, "n": n}
        body.update(kwargs)
        response = self._post("/v1/images/generations", json=body)
        _raise_for_status(response)
        return response.json()


class _AsyncImages(_BaseAsyncResource):
    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        size: str = "1024x1024",
        n: int = 1,
        **kwargs: Any,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"model": model, "prompt": prompt, "size": size, "n": n}
        body.update(kwargs)
        response = await self._post("/v1/images/generations", json=body)
        _raise_for_status(response)
        return response.json()


class _Devices(_BaseResource):
    def list(self) -> dict[str, Any]:
        response = self._get("/device/v1/app/devices")
        _raise_for_status(response)
        return response.json()

    def get(self, device_id: str) -> dict[str, Any]:
        response = self._get(f"/device/v1/app/devices/{device_id}")
        _raise_for_status(response)
        return response.json()

    def status(self, device_id: str) -> dict[str, Any]:
        response = self._get(f"/device/v1/app/devices/{device_id}/status")
        _raise_for_status(response)
        return response.json()

    def create_task(self, device_id: str, **body: Any) -> dict[str, Any]:
        response = self._post(f"/device/v1/app/devices/{device_id}/tasks", json=body)
        _raise_for_status(response)
        return response.json()

    def list_tasks(self, device_id: str, **params: Any) -> dict[str, Any]:
        response = self._get("/device/v1/app/tasks", params={"device_id": device_id, **params})
        _raise_for_status(response)
        return response.json()

    def get_task(self, task_id: str) -> dict[str, Any]:
        response = self._get(f"/device/v1/app/tasks/{task_id}")
        _raise_for_status(response)
        return response.json()


class _AsyncDevices(_BaseAsyncResource):
    async def list(self) -> dict[str, Any]:
        response = await self._get("/device/v1/app/devices")
        _raise_for_status(response)
        return response.json()

    async def get(self, device_id: str) -> dict[str, Any]:
        response = await self._get(f"/device/v1/app/devices/{device_id}")
        _raise_for_status(response)
        return response.json()

    async def status(self, device_id: str) -> dict[str, Any]:
        response = await self._get(f"/device/v1/app/devices/{device_id}/status")
        _raise_for_status(response)
        return response.json()

    async def create_task(self, device_id: str, **body: Any) -> dict[str, Any]:
        response = await self._post(f"/device/v1/app/devices/{device_id}/tasks", json=body)
        _raise_for_status(response)
        return response.json()

    async def list_tasks(self, device_id: str, **params: Any) -> dict[str, Any]:
        response = await self._get("/device/v1/app/tasks", params={"device_id": device_id, **params})
        _raise_for_status(response)
        return response.json()

    async def get_task(self, task_id: str) -> dict[str, Any]:
        response = await self._get(f"/device/v1/app/tasks/{task_id}")
        _raise_for_status(response)
        return response.json()


class _Assets(_BaseResource):
    def list(self, **params: Any) -> dict[str, Any]:
        response = self._get("/device/v1/app/assets", params=params)
        _raise_for_status(response)
        return response.json()

    def create(self, **body: Any) -> dict[str, Any]:
        response = self._post("/device/v1/app/assets", json=body)
        _raise_for_status(response)
        return response.json()


class _AsyncAssets(_BaseAsyncResource):
    async def list(self, **params: Any) -> dict[str, Any]:
        response = await self._get("/device/v1/app/assets", params=params)
        _raise_for_status(response)
        return response.json()

    async def create(self, **body: Any) -> dict[str, Any]:
        response = await self._post("/device/v1/app/assets", json=body)
        _raise_for_status(response)
        return response.json()


class LiMaClient:
    """Synchronous LiMa API client."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://chat.donglicao.com",
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        client_kwargs: dict[str, Any] = {
            "base_url": self.base_url,
            "timeout": timeout,
            "headers": _bearer_headers(api_key),
        }
        if transport is not None:
            client_kwargs["transport"] = transport
        self._http = httpx.Client(**client_kwargs)
        self.chat = _ChatCompletions(self)
        self.images = _Images(self)
        self.devices = _Devices(self)
        self.assets = _Assets(self)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        return self._http.request(method, path, **_request_kwargs(json=json, params=params))

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "LiMaClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class AsyncLiMaClient:
    """Asynchronous LiMa API client."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://chat.donglicao.com",
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        client_kwargs: dict[str, Any] = {
            "base_url": self.base_url,
            "timeout": timeout,
            "headers": _bearer_headers(api_key),
        }
        if transport is not None:
            client_kwargs["transport"] = transport
        self._http = httpx.AsyncClient(**client_kwargs)
        self.chat = _AsyncChatCompletions(self)
        self.images = _AsyncImages(self)
        self.devices = _AsyncDevices(self)
        self.assets = _AsyncAssets(self)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        return await self._http.request(method, path, **_request_kwargs(json=json, params=params))

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "AsyncLiMaClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
