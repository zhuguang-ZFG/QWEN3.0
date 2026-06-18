from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest

from scripts import firmware_hardware_gate as gate


@pytest.fixture
def workspace_tmp() -> Path:
    path = Path.cwd() / ".test-tmp" / f"firmware-gate-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _write_protocol_file(firmware_dir: Path, text: str) -> Path:
    protocol_file = firmware_dir / "main" / "protocols" / "websocket_protocol.cc"
    protocol_file.parent.mkdir(parents=True)
    protocol_file.write_text(text, encoding="utf-8")
    return protocol_file


def _valid_protocol_source() -> str:
    return """
#define LIMA_PROTOCOL_VERSION "lima-device-v1"
url = "wss://chat.donglicao.com/device/v1/ws";
cJSON_AddStringToObject(root, "protocol", LIMA_PROTOCOL_VERSION);
strcmp(type->valuestring, "hello_ack") == 0
strcmp(type->valuestring, "voice_status") == 0
strcmp(type->valuestring, "audio_reply") == 0
"""


def test_static_contract_checks_accept_lima_only_firmware(workspace_tmp: Path) -> None:
    firmware_dir = workspace_tmp / "u8-xiaozhi"
    _write_protocol_file(firmware_dir, _valid_protocol_source())

    results = gate.static_contract_checks(firmware_dir)

    assert {result.status for result in results} == {"pass"}


def test_static_contract_checks_reject_insecure_or_legacy_firmware(workspace_tmp: Path) -> None:
    firmware_dir = workspace_tmp / "u8-xiaozhi"
    _write_protocol_file(
        firmware_dir,
        _valid_protocol_source()
        + """
url = "ws://chat.donglicao.com/device/v1/ws";
CONFIG_LIMA_DIRECT_MODE
Original xiaozhi-server protocol
""",
    )

    results = gate.static_contract_checks(firmware_dir)

    failures = [result for result in results if result.status == "fail"]
    assert [result.name for result in failures] == ["firmware_forbidden_legacy_contract"]


def test_find_idf_py_reports_missing_path() -> None:
    assert gate.find_idf_py(path_env="") is None


def test_build_idf_commands_are_explicit_and_shell_free(workspace_tmp: Path) -> None:
    commands = gate.build_idf_commands(workspace_tmp, target="esp32s3", flash=True, port="COM4")

    assert commands == [
        ["idf.py", "set-target", "esp32s3"],
        ["idf.py", "build"],
        ["idf.py", "-p", "COM4", "flash"],
    ]


def test_build_gate_blocks_when_esp_idf_is_missing(workspace_tmp: Path) -> None:
    _write_protocol_file(workspace_tmp, _valid_protocol_source())

    result = gate.prepare_idf_gate(workspace_tmp, target="esp32s3", path_env="")

    assert result.status == "blocked"
    assert "ESP-IDF idf.py not found" in result.message


def test_cli_defaults_to_static_checks_without_claiming_hardware(workspace_tmp: Path, capsys) -> None:
    firmware_dir = workspace_tmp / "u8-xiaozhi"
    _write_protocol_file(firmware_dir, _valid_protocol_source())

    code = gate.main(["--firmware-dir", str(firmware_dir)], env={"PATH": ""})

    captured = capsys.readouterr().out
    assert code == 0
    assert "PASS firmware_required_lima_contract" in captured
    assert "SKIP esp_idf_build" in captured
    assert "SKIP hardware_smoke" in captured


def test_cli_build_uses_injected_env_path(workspace_tmp: Path, capsys) -> None:
    firmware_dir = workspace_tmp / "u8-xiaozhi"
    _write_protocol_file(firmware_dir, _valid_protocol_source())

    code = gate.main(["--firmware-dir", str(firmware_dir), "--build"], env={"PATH": ""})

    captured = capsys.readouterr().out
    assert code == 2
    assert "BLOCKED esp_idf_build" in captured
    assert "ESP-IDF idf.py not found" in captured


def test_cli_hardware_smoke_requires_real_credentials(workspace_tmp: Path, capsys) -> None:
    firmware_dir = workspace_tmp / "u8-xiaozhi"
    _write_protocol_file(firmware_dir, _valid_protocol_source())

    code = gate.main(["--firmware-dir", str(firmware_dir), "--hardware-smoke"], env={"PATH": ""})

    captured = capsys.readouterr().out
    assert code == 2
    assert "BLOCKED hardware_smoke" in captured
    assert "LIMA_HARDWARE_DEVICE_ID" in captured
    assert "LIMA_HARDWARE_DEVICE_TOKEN" in captured
