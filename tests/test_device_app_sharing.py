from device_app_helpers import headers, seed_account_and_device, seed_binding
from device_app_sharing_helpers import accept_share, client, seed_guest
from device_logic.db import connect


def test_create_share(client):
    seed_account_and_device()
    seed_binding()
    response = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "view"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["deviceId"] == "dev-1"
    assert data["permission"] == "view"
    assert data["status"] == "pending"
    assert data["shareToken"]
    assert data["expiresAt"]


def test_list_shares(client):
    seed_account_and_device()
    seed_binding()
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "control"},
    )
    assert create.status_code == 200

    response = client.get("/device/v1/app/devices/dev-1/shares", headers=headers("a-owner"))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["count"] == 1
    assert data["shares"][0]["permission"] == "control"


def test_non_owner_cannot_create_share(client):
    seed_account_and_device()
    seed_binding()
    seed_guest()
    response = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-guest"),
        json={"permission": "view"},
    )
    assert response.status_code == 403


def test_accept_share_creates_guest_binding(client):
    seed_account_and_device()
    seed_binding()
    seed_guest()
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "view"},
    )
    token = create.json()["shareToken"]

    accept = client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))
    assert accept.status_code == 200, accept.text
    assert accept.json()["device"]["deviceId"] == "dev-1"
    assert accept.json()["share"]["status"] == "accepted"

    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM v2_device_binding WHERE device_id=? AND account_id=?",
            ("dev-1", "a-guest"),
        ).fetchone()
        assert row is not None
        assert row["bind_mode"] == "shared"
        assert row["status"] == "active"


def test_guest_can_view_device(client):
    seed_account_and_device()
    seed_binding()
    seed_guest()
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "view"},
    )
    token = create.json()["shareToken"]
    client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))

    detail = client.get("/device/v1/app/devices/dev-1", headers=headers("a-guest"))
    assert detail.status_code == 200, detail.text
    assert detail.json()["deviceId"] == "dev-1"


def test_guest_cannot_control_with_view_share(client):
    seed_account_and_device()
    seed_binding()
    seed_guest()
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "view"},
    )
    token = create.json()["shareToken"]
    client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))

    response = client.put(
        "/device/v1/app/devices/dev-1",
        headers=headers("a-guest"),
        json={"firmwareVer": "2.0.0"},
    )
    assert response.status_code == 403


def test_guest_can_control_with_control_share(client):
    seed_account_and_device()
    seed_binding()
    seed_guest()
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "control"},
    )
    token = create.json()["shareToken"]
    client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))

    response = client.put(
        "/device/v1/app/devices/dev-1",
        headers=headers("a-guest"),
        json={"firmwareVer": "2.0.0"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["firmwareVer"] == "2.0.0"


def test_revoke_share_deactivates_binding(client):
    seed_account_and_device()
    seed_binding()
    seed_guest()
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "view"},
    )
    token = create.json()["shareToken"]
    client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))

    revoke = client.post(
        "/device/v1/app/devices/dev-1/share/revoke",
        headers=headers("a-owner"),
        json={"shareToken": token},
    )
    assert revoke.status_code == 200, revoke.text
    assert revoke.json()["status"] == "revoked"

    detail = client.get("/device/v1/app/devices/dev-1", headers=headers("a-guest"))
    assert detail.status_code == 403

    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM v2_device_binding WHERE device_id=? AND account_id=?",
            ("dev-1", "a-guest"),
        ).fetchone()
        assert row["status"] == "unbound"


def test_expired_share_cannot_be_accepted(client):
    seed_account_and_device()
    seed_binding()
    seed_guest()
    past = "2020-01-01T00:00:00Z"
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "view", "expiresAt": past},
    )
    assert create.status_code == 200
    token = create.json()["shareToken"]

    accept = client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))
    assert accept.status_code == 400
    assert accept.json()["message"] == "share token expired"


def test_accept_share_requires_pending_status(client):
    seed_account_and_device()
    seed_binding()
    seed_guest()
    create = client.post(
        "/device/v1/app/devices/dev-1/share",
        headers=headers("a-owner"),
        json={"permission": "view"},
    )
    token = create.json()["shareToken"]
    client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))

    second = client.post(f"/device/v1/app/shares/{token}/accept", headers=headers("a-guest"))
    assert second.status_code == 404
