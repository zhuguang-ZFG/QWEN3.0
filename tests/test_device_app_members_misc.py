from device_logic.db import connect
from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device, seed_binding


def _create_and_assert_member(client, device_id: str, name: str, role: str) -> dict:
    """Create a device member and assert basic fields."""
    created = client.post(
        "/device/v1/app/members",
        headers=headers("a-owner"),
        json={"deviceId": device_id, "name": name, "role": role},
    )
    assert created.status_code == 200, created.text
    member = created.json()
    assert member["deviceId"] == device_id
    assert member["name"] == name
    return member


def _enroll_and_assert_voiceprint(
    client, device_id: str, member_id: str, audio_id: str, source_name: str, introduce: str
) -> dict:
    """Enroll a voiceprint and assert returned fields."""
    enrolled = client.post(
        "/device/v1/app/voiceprints/enroll",
        headers=headers("a-owner"),
        json={
            "deviceId": device_id,
            "memberId": member_id,
            "audioId": audio_id,
            "sourceName": source_name,
            "introduce": introduce,
        },
    )
    assert enrolled.status_code == 200, enrolled.text
    vp = enrolled.json()
    assert vp["memberId"] == member_id
    assert vp["status"] == "verifying"
    assert vp["audioId"] == audio_id
    assert vp["sourceName"] == source_name
    assert vp["introduce"] == introduce
    return vp


def _list_and_assert_voiceprints(
    client, device_id: str, expected_source: str, expected_audio: str, expected_intro: str
) -> None:
    """List voiceprints and assert the first entry matches expectations."""
    listed = client.get(f"/device/v1/app/devices/{device_id}/voiceprints", headers=headers("a-owner"))
    assert listed.status_code == 200, listed.text
    data = listed.json()
    assert data["count"] == 1
    assert data["voiceprints"][0]["sourceName"] == expected_source
    assert data["voiceprints"][0]["audioId"] == expected_audio
    assert data["voiceprints"][0]["introduce"] == expected_intro


def test_device_app_member_and_voiceprint_flow(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()

    member = _create_and_assert_member(client, "dev-1", "child-1", "child")

    listed = client.get("/device/v1/app/devices/dev-1/members", headers=headers("a-owner"))
    assert listed.status_code == 200, listed.text
    assert listed.json()["members"][0]["memberId"] == member["memberId"]

    vp = _enroll_and_assert_voiceprint(client, "dev-1", member["memberId"], "audio-1", "child-1", "intro")
    _list_and_assert_voiceprints(client, "dev-1", "child-1", "audio-1", "intro")

    updated = client.put(
        f"/device/v1/app/voiceprints/{vp['voiceprintId']}",
        headers=headers("a-owner"),
        json={"sourceName": "updated", "introduce": "new-intro", "audioId": "audio-2"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["sourceName"] == "updated"
    assert updated.json()["introduce"] == "new-intro"
    assert updated.json()["audioId"] == "audio-2"

    denied = client.put(
        f"/device/v1/app/voiceprints/{vp['voiceprintId']}",
        headers=headers("a-other"),
        json={"sourceName": "hacker"},
    )
    assert denied.status_code == 403

    deleted = client.delete(f"/device/v1/app/voiceprints/{vp['voiceprintId']}", headers=headers("a-owner"))
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"voiceprintId": vp["voiceprintId"], "status": "disabled"}


def test_device_app_transfer_self_check_and_supplies_flow(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device(device_id="d-1", device_sn="SN-MISC-01")
    seed_binding(device_id="d-1", account_id="a-owner")

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_self_check_event
            (id, device_id, check_type, result, details, duration_ms, triggered_by, created_at)
            VALUES ('sc-new', 'd-1', 'manual', 'warning', '{"motor":"warm"}', 25, 'api', '2026-01-02T00:00:00Z')
            """
        )
        conn.commit()

    transfer = client.post(
        "/device/v1/app/devices/d-1/transfer",
        headers=headers("a-owner"),
        json={"toPhone": "13002", "reason": "family handoff"},
    )
    assert transfer.status_code == 200, transfer.text
    transfer_data = transfer.json()
    assert transfer_data["toAccountId"] == "a-other"
    assert transfer_data["status"] == "pending"

    pending = client.get("/device/v1/app/transfers/pending", headers=headers("a-other"))
    assert pending.status_code == 200, pending.text
    assert pending.json()["transfers"][0]["id"] == transfer_data["id"]

    accepted = client.post(f"/device/v1/app/transfers/{transfer_data['id']}/accept", headers=headers("a-other"))
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"

    updated = client.put(
        "/device/v1/app/devices/d-1/supplies",
        headers=headers("a-other"),
        json={
            "pen": {"level": 0.2, "status": "low"},
            "supplies": [{"supplyType": "paper", "level": 0.9, "status": "normal"}],
        },
    )
    assert updated.status_code == 200, updated.text
    assert {(row["supplyType"], row["level"], row["status"]) for row in updated.json()} == {
        ("pen", 0.2, "low"),
        ("paper", 0.9, "normal"),
    }

    supplies = client.get("/device/v1/app/devices/d-1/supplies", headers=headers("a-other"))
    assert supplies.status_code == 200, supplies.text
    assert [row["supplyType"] for row in supplies.json()["supplies"]] == ["paper", "pen"]

    checks = client.get("/device/v1/app/devices/d-1/self-checks?limit=1", headers=headers("a-other"))
    assert checks.status_code == 200, checks.text
    assert checks.json()["selfChecks"][0]["id"] == "sc-new"
