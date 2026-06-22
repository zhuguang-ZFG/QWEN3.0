"""Device Gateway cross-process task notifications."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from collections.abc import Awaitable, Callable
from typing import Any, Protocol


TaskAvailableCallback = Callable[[str], Awaitable[None]]


class DeviceTaskNotifier(Protocol):
    backend_name: str
    shared_across_processes: bool

    async def publish_task_available(self, device_id: str) -> None: ...

    async def start(self, callback: TaskAvailableCallback) -> None: ...

    async def stop(self) -> None: ...


class LocalDeviceTaskNotifier:
    backend_name = "local"
    shared_across_processes = False

    async def publish_task_available(self, device_id: str) -> None:
        return None

    async def start(self, callback: TaskAvailableCallback) -> None:
        return None

    async def stop(self) -> None:
        return None


class RedisDeviceTaskNotifier:
    backend_name = "redis"
    shared_across_processes = True

    def __init__(self, redis_url: str, *, channel: str = "lima:device:task_available") -> None:
        try:
            import redis.asyncio as redis_async
        except ImportError as exc:
            raise RuntimeError("redis package is required for Redis device notifications") from exc
        self._redis = redis_async.from_url(redis_url, decode_responses=True)
        self._channel = channel
        self._task: asyncio.Task[None] | None = None
        self._pubsub: Any | None = None

    async def publish_task_available(self, device_id: str) -> None:
        await self._redis.publish(self._channel, json.dumps({"device_id": device_id}, separators=(",", ":")))

    async def start(self, callback: TaskAvailableCallback) -> None:
        if self._task is not None and not self._task.done():
            return
        self._pubsub = self._redis.pubsub()
        pubsub = self._pubsub
        assert pubsub is not None
        await pubsub.subscribe(self._channel)
        self._task = asyncio.create_task(self._listen(callback))

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._task = None
        if self._pubsub is not None:
            try:
                await self._pubsub.unsubscribe(self._channel)
            except Exception as exc:
                _log("notifier_unsubscribe_error", str(exc))
            try:
                await self._pubsub.close()
            except Exception as exc:
                _log("notifier_pubsub_close_error", str(exc))
        self._pubsub = None
        try:
            await self._redis.aclose()
        except Exception as exc:
            _log("notifier_redis_close_error", str(exc))

    async def _listen(self, callback: TaskAvailableCallback) -> None:
        assert self._pubsub is not None
        self._alive = True
        while True:
            try:
                message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=30.0)
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                _log("notifier_listen_error", str(exc))
                await asyncio.sleep(1)
                continue

            if not message or message.get("type") != "message":
                continue
            device_id = _device_id_from_message(message.get("data"))
            if device_id:
                try:
                    await callback(device_id)
                except Exception as exc:
                    _log("notifier_callback_error", str(exc))

    @property
    def listener_alive(self) -> bool:
        if self._task is None or self._task.done():
            return False
        return getattr(self, "_alive", False)


def _device_id_from_message(data: Any) -> str:
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="replace")
    if not isinstance(data, str):
        return ""
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return ""
    device_id = payload.get("device_id") if isinstance(payload, dict) else None
    return device_id.strip() if isinstance(device_id, str) else ""


def _log(event: str, detail: str) -> None:
    import logging

    logging.getLogger("device_gateway.notifier").warning("%s: %s", event, detail[:200])


task_notifier: DeviceTaskNotifier = LocalDeviceTaskNotifier()


def notifier_health() -> dict[str, Any]:
    result = {
        "backend": getattr(task_notifier, "backend_name", task_notifier.__class__.__name__),
        "shared_across_processes": bool(getattr(task_notifier, "shared_across_processes", False)),
    }
    if hasattr(task_notifier, "listener_alive"):
        result["listener_alive"] = task_notifier.listener_alive  # type: ignore[union-attr]
    return result


async def publish_task_available(device_id: str) -> None:
    await task_notifier.publish_task_available(device_id)


async def start_task_notifier(callback: TaskAvailableCallback) -> None:
    await task_notifier.start(callback)


async def stop_task_notifier() -> None:
    await task_notifier.stop()


def configure_notifier_from_env() -> None:
    global task_notifier
    backend = os.environ.get("LIMA_DEVICE_SESSION_BUS", "").strip().lower()
    redis_url = os.environ.get("LIMA_DEVICE_REDIS_URL", "").strip()
    if backend == "redis" or (backend == "" and redis_url):
        if not redis_url:
            raise RuntimeError("LIMA_DEVICE_REDIS_URL is required when LIMA_DEVICE_SESSION_BUS=redis")
        task_notifier = RedisDeviceTaskNotifier(redis_url)
    else:
        task_notifier = LocalDeviceTaskNotifier()
