"""Tests for routes/route_registry.py."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI

from routes import route_registry as rr


@pytest.fixture
def deps():
    return rr.RouteRegistryDeps(
        model_id="lima-test",
        model_created=123,
        stats={},
        stats_lock=threading.Lock(),
        backend_enabled={},
        loaded_modules={},
        client_ip=lambda _req: "127.0.0.1",
        detect_ide=lambda _msgs: "",
        elapsed_ms=lambda _t: 1,
        vision_route=MagicMock(),
        stream_vision_response=MagicMock(),
        record_request=MagicMock(),
        handle_chat=MagicMock(),
    )


def test_try_include_success():
    app = FastAPI()
    app.include_router = MagicMock()
    loaded = {}
    mod_name = "test_fake_router_module_abc"
    fake_router = MagicMock()
    fake_mod = SimpleNamespace(router=fake_router)
    with patch.dict("sys.modules", {mod_name: fake_mod}):
        assert rr._try_include(app, loaded, mod_name, "fake") is True
    assert loaded["fake"] is True
    app.include_router.assert_called_once_with(fake_router)


def test_try_include_missing_module():
    app = FastAPI()
    app.include_router = MagicMock()
    loaded = {}
    assert rr._try_include(app, loaded, "nonexistent_module_xyz", "missing") is False
    assert loaded["missing"] is False


@patch("importlib.import_module", side_effect=ImportError("bad"))
def test_try_include_import_error(mock_import):
    app = FastAPI()
    app.include_router = MagicMock()
    loaded = {}
    mod_name = "test_bad_router_module_abc"
    assert rr._try_include(app, loaded, mod_name, "bad") is False
    assert loaded["bad"] is False


def test_register_all_routes_returns_aliases(deps):
    app = FastAPI()
    with patch.object(rr, "_register_core_routes") as mock_core, patch.object(rr, "_register_optional_routes") as mock_opt, patch.object(rr, "mark_retired_modules"):
        chat_mod = SimpleNamespace(chat_completions=MagicMock())
        sys_mod = SimpleNamespace(list_models=MagicMock(), health=MagicMock(), live_key=MagicMock(), router_status=MagicMock())
        mock_core.return_value = (chat_mod, sys_mod)
        result = rr.register_all_routes(app, deps)
        assert result.chat_completions is chat_mod.chat_completions
        assert result.list_models is sys_mod.list_models
