"""Shared helpers for device task template tests."""

from device_logic.db import connect


def template_id(response) -> str:
    return response.json()["data"]["templateId"]


def seed_second_device(device_id: str = "dev-2", device_sn: str = "SN-APP-02") -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO v2_device (id, device_sn, model, firmware_ver, hardware_ver) VALUES (?, ?, 'esp32s3_xyz', '1.0.0', 'rev-a')",
            (device_id, device_sn),
        )
        conn.execute(
            "INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status) VALUES (?, ?, ?, 'owner', 'active')",
            (f"b-{device_id}", device_id, "a-owner"),
        )
        conn.commit()
