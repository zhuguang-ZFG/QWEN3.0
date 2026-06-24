import pytest

from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device, seed_binding
from device_logic.db import connect
from routes.device_app_assets import router as assets_router


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_client, _store = make_client(tmp_path, monkeypatch)
    test_client.app.include_router(assets_router)
    seed_account_and_device()
    seed_binding()
    return test_client


ASSET_SVG = "M10 10 L90 90 L10 90 Z"


def _create_asset(client, account_id="a-owner", **kwargs):
    payload = {
        "title": kwargs.get("title", "test-asset"),
        "category": kwargs.get("category", "svg"),
        "content": kwargs.get("content", ASSET_SVG),
        "difficulty": kwargs.get("difficulty", "easy"),
        "tags": kwargs.get("tags", ["demo"]),
    }
    if "previewUrl" in kwargs:
        payload["previewUrl"] = kwargs["previewUrl"]
    return client.post("/device/v1/app/assets", headers=headers(account_id), json=payload)


def test_list_assets_requires_auth(client):
    assert client.get("/device/v1/app/assets").status_code == 401


def test_create_and_list_assets(client):
    create = _create_asset(client, title="Star", category="svg", tags=["shape"])
    assert create.status_code == 200, create.text
    data = create.json()
    assert data["code"] == 0
    assert data["data"]["title"] == "Star"

    listed = client.get("/device/v1/app/assets", headers=headers("a-owner"))
    assert listed.status_code == 200, listed.text
    assets = listed.json()["data"]["assets"]
    assert len(assets) == 1
    assert assets[0]["title"] == "Star"
    assert assets[0]["tags"] == ["shape"]


def test_list_assets_filter_category_and_tag(client):
    _create_asset(client, title="Text A", category="text", content="hello", tags=["greeting"])
    _create_asset(client, title="Shape A", category="svg", tags=["shape"])
    _create_asset(client, title="Shape B", category="svg", tags=["shape", "star"])

    by_category = client.get("/device/v1/app/assets?category=text", headers=headers("a-owner"))
    assert by_category.json()["data"]["total"] == 1

    by_tag = client.get("/device/v1/app/assets?tag=star", headers=headers("a-owner"))
    assert by_tag.json()["data"]["total"] == 1

    paged = client.get("/device/v1/app/assets?limit=1&offset=1", headers=headers("a-owner"))
    assert paged.json()["data"]["limit"] == 1
    assert paged.json()["data"]["offset"] == 1


def test_get_asset_increments_use_count(client):
    create = _create_asset(client, title="Counter")
    asset_id = create.json()["data"]["assetId"]

    first = client.get(f"/device/v1/app/assets/{asset_id}", headers=headers("a-owner"))
    assert first.status_code == 200, first.text
    first_count = first.json()["data"]["useCount"]

    second = client.get(f"/device/v1/app/assets/{asset_id}", headers=headers("a-owner"))
    assert second.json()["data"]["useCount"] == first_count + 1


def test_get_asset_404(client):
    resp = client.get("/device/v1/app/assets/not-exist", headers=headers("a-owner"))
    assert resp.status_code == 404


def test_create_asset_validation(client):
    resp = client.post("/device/v1/app/assets", headers=headers("a-owner"), json={"title": "Only title"})
    assert resp.status_code == 400
    assert "title, category and content are required" in resp.json()["message"]

    resp = client.post(
        "/device/v1/app/assets",
        headers=headers("a-owner"),
        json={"title": "Bad", "category": "unknown", "content": "x"},
    )
    assert resp.status_code == 400
    assert "invalid category" in resp.json()["message"]


def test_render_asset_creates_task(client):
    create = _create_asset(client, title="Render SVG", category="svg", content=ASSET_SVG)
    asset_id = create.json()["data"]["assetId"]

    resp = client.post(
        f"/device/v1/app/assets/{asset_id}/render",
        headers=headers("a-owner"),
        json={"deviceId": "dev-1"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["assetId"] == asset_id
    assert "taskId" in data

    with connect() as conn:
        row = conn.execute("SELECT * FROM v2_task WHERE id=?", (data["taskId"],)).fetchone()
    assert row is not None
    assert row["device_id"] == "dev-1"


def test_render_text_asset(client):
    create = _create_asset(client, title="Render Text", category="text", content="hi")
    asset_id = create.json()["data"]["assetId"]

    resp = client.post(
        f"/device/v1/app/assets/{asset_id}/render",
        headers=headers("a-owner"),
        json={"deviceId": "dev-1"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["taskId"]


def test_render_asset_requires_device_access(client):
    create = _create_asset(client, title="Private")
    asset_id = create.json()["data"]["assetId"]

    resp = client.post(
        f"/device/v1/app/assets/{asset_id}/render",
        headers=headers("a-other"),
        json={"deviceId": "dev-1"},
    )
    assert resp.status_code == 403


def test_render_asset_404(client):
    resp = client.post(
        "/device/v1/app/assets/missing-id/render",
        headers=headers("a-owner"),
        json={"deviceId": "dev-1"},
    )
    assert resp.status_code == 404


def test_render_asset_requires_device_id(client):
    create = _create_asset(client, title="No device")
    asset_id = create.json()["data"]["assetId"]

    resp = client.post(f"/device/v1/app/assets/{asset_id}/render", headers=headers("a-owner"), json={})
    assert resp.status_code == 400
    assert "deviceId is required" in resp.json()["message"]
