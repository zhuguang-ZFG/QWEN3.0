"""Tests for routes/device_gateway_dispatch.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket

from device_gateway.protocol import ProtocolError
from device_gateway.sessions import DeviceSession
from routes import device_gateway_dispatch as dispatch


@pytest.fixture
def websocket():
    ws = MagicMock(spec=WebSocket)
    ws.scope = {}
    ws.query_params = MagicMock()
    ws.query_params.get.return_value = ""
    ws.headers = {}
    return ws


# ── extract_ws_token ─────────────────────────────────────────────────────


def test_extract_ws_token_from_header(websocket):
    websocket.headers["authorization"] = "Bearer header-token"
    assert dispatch.extract_ws_token(websocket) == "header-token"


def test_extract_ws_token_from_ticket(websocket, monkeypatch):
    monkeypatch.setattr(
        dispatch,
        "consume_device_ws_ticket",
        lambda t: ("dev-1", "ticket-token") if t == "abc" else None,
    )
    websocket.query_params.get.side_effect = lambda key, default="": "abc" if key == "ticket" else default
    assert dispatch.extract_ws_token(websocket) == "ticket-token"
    assert websocket.scope["state"]["ticket_device_id"] == "dev-1"


def test_extract_ws_token_ignores_query_param(websocket):
    websocket.query_params.get.side_effect = lambda key, default="": "query-token" if key == "token" else default
    assert dispatch.extract_ws_token(websocket) == ""


def test_extract_ws_token_missing(websocket):
    assert dispatch.extract_ws_token(websocket) == ""


# ── ticket_device_id ─────────────────────────────────────────────────────


def test_ticket_device_id_returns_bound_value(websocket):
    websocket.scope["state"] = {"ticket_device_id": "dev-1"}
    assert dispatch.ticket_device_id(websocket) == "dev-1"


def test_ticket_device_id_returns_none_when_missing(websocket):
    assert dispatch.ticket_device_id(websocket) is None


# ── send_ws_error ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_ws_error(websocket):
    websocket.send_json = AsyncMock()
    err = ProtocolError("E_TEST", "test error", "r1")
    await dispatch.send_ws_error(websocket, err)
    websocket.send_json.assert_awaited_once()
    payload = websocket.send_json.await_args.args[0]
    assert payload["type"] == "error"
    assert payload["code"] == "E_TEST"


# ── requeue_session_outstanding ──────────────────────────────────────────


def test_requeue_session_outstanding_no_tasks():
    session = MagicMock(spec=DeviceSession)
    session.device_id = "dev-1"
    session.take_outstanding_tasks.return_value = []
    with patch.object(dispatch, "pending_count", return_value=3) as mock_count:
        assert dispatch.requeue_session_outstanding(session) == 3
    mock_count.assert_called_once_with("dev-1")


def test_requeue_session_outstanding_with_tasks():
    session = MagicMock(spec=DeviceSession)
    session.device_id = "dev-1"
    session.take_outstanding_tasks.return_value = [{"task_id": "t1"}]
    with patch.object(dispatch, "requeue_pending_tasks", return_value=5) as mock_requeue:
        assert dispatch.requeue_session_outstanding(session) == 5
    mock_requeue.assert_called_once_with("dev-1", [{"task_id": "t1"}])


# ── dispatch_task_to_session ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_task_to_session_success():
    session = MagicMock(spec=DeviceSession)
    session.device_id = "dev-1"
    session.send_json = AsyncMock()
    task = {"task_id": "t1"}
    with (
        patch.object(dispatch, "registry") as mock_registry,
        patch.object(dispatch, "mark_task_dispatched") as mock_mark,
    ):
        result = await dispatch.dispatch_task_to_session(session, task)
    assert result is True
    session.send_json.assert_awaited_once_with(task)
    session.mark_task_dispatched.assert_called_once_with(task)
    mock_mark.assert_called_once_with("t1")


@pytest.mark.asyncio
async def test_dispatch_task_to_session_send_failure():
    session = MagicMock(spec=DeviceSession)
    session.device_id = "dev-1"
    session.websocket = MagicMock()
    session.send_json = AsyncMock(side_effect=RuntimeError("boom"))
    task = {"task_id": "t1"}
    with (
        patch.object(dispatch, "registry") as mock_registry,
        patch.object(dispatch, "requeue_session_outstanding") as mock_requeue,
    ):
        result = await dispatch.dispatch_task_to_session(session, task)
    assert result is False
    mock_registry.unregister.assert_called_once_with("dev-1", session.websocket)
    mock_requeue.assert_called_once_with(session, [task])


# ── drain_pending_tasks ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_drain_pending_tasks_success():
    session = MagicMock(spec=DeviceSession)
    session.device_id = "dev-1"
    session.send_json = AsyncMock()
    with (
        patch.object(dispatch, "pop_pending_tasks", side_effect=[[{"task_id": "t1"}], []]) as mock_pop,
        patch.object(dispatch, "mark_task_dispatched") as mock_mark,
    ):
        result = await dispatch.drain_pending_tasks(session)
    assert result is True
    mock_pop.assert_any_call("dev-1")
    session.send_json.assert_awaited_once_with({"task_id": "t1"})


@pytest.mark.asyncio
async def test_drain_pending_tasks_send_failure():
    session = MagicMock(spec=DeviceSession)
    session.device_id = "dev-1"
    session.websocket = MagicMock()
    session.send_json = AsyncMock(side_effect=[RuntimeError("boom")])
    with (
        patch.object(dispatch, "pop_pending_tasks", return_value=[{"task_id": "t1"}, {"task_id": "t2"}]),
        patch.object(dispatch, "registry") as mock_registry,
        patch.object(dispatch, "requeue_session_outstanding") as mock_requeue,
    ):
        result = await dispatch.drain_pending_tasks(session)
    assert result is False
    mock_registry.unregister.assert_called_once_with("dev-1", session.websocket)
    mock_requeue.assert_called_once_with(session, [{"task_id": "t1"}, {"task_id": "t2"}])


# ── notify_local_session_task_available ──────────────────────────────────


@pytest.mark.asyncio
async def test_notify_local_session_task_available():
    session = MagicMock(spec=DeviceSession)
    session.device_id = "dev-1"
    with (
        patch.object(dispatch.registry, "get", return_value=session),
        patch.object(dispatch, "drain_pending_tasks", return_value=True) as mock_drain,
    ):
        await dispatch.notify_local_session_task_available("dev-1")
    mock_drain.assert_awaited_once_with(session)


@pytest.mark.asyncio
async def test_notify_local_session_task_available_no_session():
    with patch.object(dispatch.registry, "get", return_value=None) as mock_get:
        await dispatch.notify_local_session_task_available("dev-1")
    mock_get.assert_called_once_with("dev-1")


@pytest.mark.asyncio
async def test_notify_local_session_task_available_swallows_exception():
    with (
        patch.object(dispatch.registry, "get", side_effect=RuntimeError("boom")),
        patch.object(dispatch._log, "exception") as mock_log,
    ):
        await dispatch.notify_local_session_task_available("dev-1")
    mock_log.assert_called_once()


# ── publish_task_available_safe ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_task_available_safe():
    with patch.object(dispatch, "publish_task_available", new_callable=AsyncMock) as mock_pub:
        await dispatch.publish_task_available_safe("dev-1", "t1")
    mock_pub.assert_awaited_once_with("dev-1")


@pytest.mark.asyncio
async def test_publish_task_available_safe_logs_failure():
    with (
        patch.object(dispatch, "publish_task_available", new_callable=AsyncMock, side_effect=RuntimeError("boom")),
        patch.object(dispatch._log, "warning") as mock_log,
    ):
        await dispatch.publish_task_available_safe("dev-1", "t1")
    mock_log.assert_called_once()
