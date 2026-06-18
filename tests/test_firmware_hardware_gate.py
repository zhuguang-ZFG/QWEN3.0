from __future__ import annotations

import shutil
import subprocess
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


def test_build_gate_blocks_when_idf_path_source_tree_is_missing(workspace_tmp: Path, monkeypatch) -> None:
    _write_protocol_file(workspace_tmp, _valid_protocol_source())
    monkeypatch.setattr(
        gate, "find_idf_py", lambda path_env=None: r"C:\Users\zhugu\.espressif\tools\idf-exe\1.0.3\idf.py.exe"
    )

    result = gate.prepare_idf_gate(workspace_tmp, target="esp32s3", env={})

    assert result.status == "blocked"
    assert "IDF_PATH" in result.message
    assert "ESP-IDF source tree" in result.message


def test_build_gate_accepts_valid_idf_path_source_tree(workspace_tmp: Path, monkeypatch) -> None:
    firmware_dir = workspace_tmp / "u8-xiaozhi"
    idf_source = workspace_tmp / "esp-idf"
    _write_protocol_file(firmware_dir, _valid_protocol_source())
    (idf_source / "tools" / "cmake").mkdir(parents=True)
    (idf_source / "tools" / "idf.py").write_text("# fake idf", encoding="utf-8")
    (idf_source / "tools" / "cmake" / "project.cmake").write_text("# fake project", encoding="utf-8")
    monkeypatch.setattr(gate, "find_idf_py", lambda path_env=None: str(idf_source / "tools" / "idf.py"))

    result = gate.prepare_idf_gate(firmware_dir, target="esp32s3", env={"IDF_PATH": str(idf_source)})

    assert result.status == "pass"
    assert str(idf_source) in result.message


def test_run_idf_build_blocks_when_idf_python_env_is_broken(workspace_tmp: Path, monkeypatch) -> None:
    firmware_dir = workspace_tmp / "u8-xiaozhi"
    idf_source = workspace_tmp / "esp-idf"
    _write_protocol_file(firmware_dir, _valid_protocol_source())
    (idf_source / "tools" / "cmake").mkdir(parents=True)
    (idf_source / "tools" / "idf.py").write_text("# fake idf", encoding="utf-8")
    (idf_source / "tools" / "cmake" / "project.cmake").write_text("# fake project", encoding="utf-8")

    def fake_run(*args, **kwargs):
        del args, kwargs
        return subprocess.CompletedProcess(
            args=["idf.py", "--version"],
            returncode=1,
            stdout="ModuleNotFoundError: No module named 'esp_idf_monitor'\n",
        )

    monkeypatch.setattr(gate.subprocess, "run", fake_run)

    results = gate.run_idf_build(
        firmware_dir,
        target="esp32s3",
        flash=False,
        port=None,
        env={"IDF_PATH": str(idf_source)},
    )

    assert results == [
        gate.CheckResult(
            name="esp_idf_python_env",
            status="blocked",
            message="ESP-IDF Python environment is not ready: ModuleNotFoundError: No module named 'esp_idf_monitor'",
        )
    ]


def test_run_idf_build_uses_idf_source_tree_tool_entrypoint(workspace_tmp: Path, monkeypatch) -> None:
    firmware_dir = workspace_tmp / "u8-xiaozhi"
    idf_source = workspace_tmp / "esp-idf"
    _write_protocol_file(firmware_dir, _valid_protocol_source())
    (idf_source / "tools" / "cmake").mkdir(parents=True)
    (idf_source / "tools" / "idf.py").write_text("# fake idf", encoding="utf-8")
    (idf_source / "tools" / "cmake" / "project.cmake").write_text("# fake project", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        del kwargs
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="ESP-IDF v5.5.4\n")

    monkeypatch.setattr(gate.subprocess, "run", fake_run)

    results = gate.run_idf_build(
        firmware_dir,
        target="esp32s3",
        flash=False,
        port=None,
        env={"IDF_PATH": str(idf_source)},
    )

    idf_entrypoint = str(idf_source / "tools" / "idf.py")
    assert calls == [
        [gate.sys.executable, idf_entrypoint, "--version"],
        [gate.sys.executable, idf_entrypoint, "set-target", "esp32s3"],
        [gate.sys.executable, idf_entrypoint, "build"],
    ]
    assert [result.status for result in results] == ["pass", "pass"]


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
