"""[DEPRECATED v3.1] Tests for retired XiaoZhi v1 compatibility layer.
Kept for reference only; do not extend."""

from .helpers import _client, _headers, _json, _seed_base, _token


import routes.xiaozhi_v1_compat as compat


def test_account_delete_soft_deletes_account_and_unbinds_devices(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    data = _json(client.post("/api/v1/auth/account/delete", headers=_headers("a-owner")))

    assert data["accountId"] == "a-owner"
    assert data["deletedAt"]
    with compat._connect() as conn:
        account = conn.execute("SELECT * FROM v2_account WHERE id='a-owner'").fetchone()
        binding = conn.execute("SELECT * FROM v2_device_binding WHERE id='b-owner'").fetchone()
    assert account["status"] == "deleted"
    assert account["nickname"] == "deleted_user"
    assert account["deleted_at"] == data["deletedAt"]
    assert binding["status"] == "unbound"
    assert binding["unbound_at"]


def test_delete_voiceprint_disables_record_and_clears_member_link(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    data = _json(client.delete("/api/v1/voiceprints/vp-1", headers=_headers("a-owner")))

    assert data["voiceprintId"] == "vp-1"
    assert data["status"] == "disabled"
    with compat._connect() as conn:
        voiceprint = conn.execute("SELECT * FROM v2_voiceprint WHERE id='vp-1'").fetchone()
        member = conn.execute("SELECT * FROM v2_member WHERE id='m-1'").fetchone()
    assert voiceprint["status"] == "disabled"
    assert member["voiceprint_id"] is None


def test_update_device_and_list_self_checks(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    device = _json(
        client.put(
            "/api/v1/devices/d-1",
            headers=_headers("a-owner"),
            json={
                "model": "esp32c3_mini",
                "firmwareVer": "1.2.3",
                "hardwareVer": "rev-b",
                "metadata": {"workArea": "A5"},
            },
        )
    )
    assert device["model"] == "esp32c3_mini"
    assert device["firmwareVer"] == "1.2.3"
    assert '"workArea": "A5"' in device["metadata"]

    with compat._connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_self_check_event
            (id, device_id, check_type, result, details, duration_ms, triggered_by, created_at)
            VALUES ('sc-old', 'd-1', 'startup', 'pass', '{}', 10, 'system', '2026-01-01T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO v2_self_check_event
            (id, device_id, check_type, result, details, duration_ms, triggered_by, created_at)
            VALUES ('sc-new', 'd-1', 'manual', 'warning', '{"motor":"warm"}', 25, 'api', '2026-01-02T00:00:00Z')
            """
        )
        conn.commit()

    checks = _json(client.get("/api/v1/devices/d-1/self-checks?limit=1", headers=_headers("a-owner")))
    assert [row["id"] for row in checks] == ["sc-new"]
    assert checks[0]["checkType"] == "manual"
    assert checks[0]["durationMs"] == 25


def test_transfer_accept_changes_owner_binding(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    transfer = _json(
        client.post(
            "/api/v1/devices/d-1/transfer",
            headers=_headers("a-owner"),
            json={"toPhone": "10002", "reason": "family handoff"},
        )
    )
    assert transfer["deviceId"] == "d-1"
    assert transfer["fromAccountId"] == "a-owner"
    assert transfer["toAccountId"] == "a-target"
    assert transfer["status"] == "pending"
    assert transfer["expiresAt"]

    pending = _json(client.get("/api/v1/transfers/pending", headers=_headers("a-target")))
    assert [row["id"] for row in pending] == [transfer["id"]]

    accepted = _json(client.post(f"/api/v1/transfers/{transfer['id']}/accept", headers=_headers("a-target")))
    assert accepted["status"] == "accepted"
    with compat._connect() as conn:
        owner = conn.execute(
            """
            SELECT account_id FROM v2_device_binding
            WHERE device_id='d-1' AND bind_mode='owner' AND status='active'
            """
        ).fetchone()
        old_owner = conn.execute("SELECT status FROM v2_device_binding WHERE id='b-owner'").fetchone()
    assert owner["account_id"] == "a-target"
    assert old_owner["status"] == "unbound"


def test_cancel_transfer_and_upsert_supplies(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    transfer = _json(
        client.post(
            "/api/v1/devices/d-1/transfer",
            headers=_headers("a-owner"),
            json={"toAccountId": "a-target"},
        )
    )
    cancelled = _json(client.post(f"/api/v1/transfers/{transfer['id']}/cancel", headers=_headers("a-owner")))
    assert cancelled["status"] == "cancelled"

    updated = _json(
        client.put(
            "/api/v1/devices/d-1/supplies",
            headers=_headers("a-owner"),
            json={
                "pen": {"level": 0.2, "status": "low"},
                "supplies": [{"supplyType": "paper", "level": 0.9, "status": "normal"}],
            },
        )
    )
    assert {(row["supplyType"], row["level"], row["status"]) for row in updated} == {
        ("pen", 0.2, "low"),
        ("paper", 0.9, "normal"),
    }

    supplies = _json(client.get("/api/v1/devices/d-1/supplies", headers=_headers("a-owner")))
    assert [row["supplyType"] for row in supplies] == ["paper", "pen"]
