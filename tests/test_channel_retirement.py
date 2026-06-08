from fastapi.testclient import TestClient

import channel_retirement
import server


def test_mark_retired_modules_sets_telegram_false():
    loaded = {"telegram": True}

    channel_retirement.mark_retired_modules(loaded)

    assert loaded["telegram"] is False


def test_telegram_routes_are_not_registered():
    paths = {getattr(route, "path", "") for route in server.app.routes}

    assert not any(path.startswith("/telegram") for path in paths)
    assert server._loaded_modules.get("telegram") is False


def test_telegram_webhook_is_gone():
    response = TestClient(server.app).post("/telegram/webhook", json={"message": {"text": "/start"}})

    assert response.status_code == 404
