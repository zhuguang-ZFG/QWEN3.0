"""Firmware and real-device verification gate for LiMa U8 firmware."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

PROTOCOL_FILE = Path("main/protocols/websocket_protocol.cc")
DEFAULT_FIRMWARE_DIR = Path("esp32S_XYZ/firmware/u8-xiaozhi")
DEFAULT_HOST = "chat.donglicao.com"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    message: str


def _result(name: str, status: str, message: str) -> CheckResult:
    return CheckResult(name=name, status=status, message=message)


def _protocol_path(firmware_dir: Path) -> Path:
    return firmware_dir / PROTOCOL_FILE


def static_contract_checks(firmware_dir: Path) -> list[CheckResult]:
    protocol_path = _protocol_path(firmware_dir)
    if not protocol_path.exists():
        return [_result("firmware_required_lima_contract", "fail", f"missing {protocol_path}")]

    text = protocol_path.read_text(encoding="utf-8")
    results = [_required_lima_contract(text), _forbidden_legacy_contract(text)]
    return results


def _required_lima_contract(text: str) -> CheckResult:
    required = [
        '#define LIMA_PROTOCOL_VERSION "lima-device-v1"',
        'url = "wss://chat.donglicao.com/device/v1/ws";',
        'cJSON_AddStringToObject(root, "protocol", LIMA_PROTOCOL_VERSION);',
        'strcmp(type->valuestring, "hello_ack") == 0',
        'strcmp(type->valuestring, "voice_status") == 0',
        'strcmp(type->valuestring, "audio_reply") == 0',
    ]
    missing = [item for item in required if item not in text]
    if missing:
        return _result("firmware_required_lima_contract", "fail", "missing: " + "; ".join(missing))
    return _result("firmware_required_lima_contract", "pass", "LiMa WSS and protocol v1 defaults are present")


def _forbidden_legacy_contract(text: str) -> CheckResult:
    forbidden = [
        'url = "ws://chat.donglicao.com/device/v1/ws";',
        "CONFIG_LIMA_DIRECT_MODE",
        "Original xiaozhi-server protocol",
        "Original xiaozhi-server hello parsing",
    ]
    found = [item for item in forbidden if item in text]
    if found:
        return _result("firmware_forbidden_legacy_contract", "fail", "found: " + "; ".join(found))
    return _result("firmware_forbidden_legacy_contract", "pass", "legacy/insecure firmware contract is absent")


def find_idf_py(path_env: str | None = None) -> str | None:
    return shutil.which("idf.py", path=path_env)


def build_idf_commands(
    firmware_dir: Path,
    *,
    target: str,
    flash: bool = False,
    port: str | None = None,
) -> list[list[str]]:
    del firmware_dir
    commands = [["idf.py", "set-target", target], ["idf.py", "build"]]
    if flash:
        flash_cmd = ["idf.py"]
        if port:
            flash_cmd.extend(["-p", port])
        flash_cmd.append("flash")
        commands.append(flash_cmd)
    return commands


def _valid_idf_source_tree(path: Path) -> bool:
    return (path / "idf.py").exists() and (path / "tools" / "cmake" / "project.cmake").exists()


def _resolve_idf_path(idf_py: str, env: Mapping[str, str] | None = None) -> Path | None:
    idf_path = (env or {}).get("IDF_PATH", "").strip()
    if idf_path:
        return Path(idf_path)
    idf_py_path = Path(idf_py)
    parent = idf_py_path.parent
    if _valid_idf_source_tree(parent):
        return parent
    return None


def prepare_idf_gate(
    firmware_dir: Path,
    *,
    target: str,
    path_env: str | None = None,
    env: Mapping[str, str] | None = None,
) -> CheckResult:
    if not _protocol_path(firmware_dir).exists():
        return _result("esp_idf_build", "blocked", f"firmware directory is missing {_protocol_path(firmware_dir)}")
    idf_py = find_idf_py(path_env=path_env)
    if idf_py is None:
        return _result("esp_idf_build", "blocked", "ESP-IDF idf.py not found on PATH")
    idf_path = _resolve_idf_path(idf_py, env)
    if idf_path is None or not _valid_idf_source_tree(idf_path):
        return _result("esp_idf_build", "blocked", "IDF_PATH must point to a valid ESP-IDF source tree")
    return _result("esp_idf_build", "pass", f"ESP-IDF available for target {target}: {idf_path}")


def run_idf_build(
    firmware_dir: Path,
    *,
    target: str,
    flash: bool,
    port: str | None,
    env: Mapping[str, str] | None = None,
) -> list[CheckResult]:
    path_env = None if env is None else env.get("PATH", "")
    preflight = prepare_idf_gate(firmware_dir, target=target, path_env=path_env, env=env)
    if preflight.status != "pass":
        return [preflight]
    results: list[CheckResult] = []
    for command in build_idf_commands(firmware_dir, target=target, flash=flash, port=port):
        completed = subprocess.run(command, cwd=firmware_dir, env=env, check=False)  # noqa: S603
        name = "esp_idf_" + command[-1].replace("-", "_")
        if completed.returncode != 0:
            return results + [_result(name, "fail", f"{' '.join(command)} exited {completed.returncode}")]
        results.append(_result(name, "pass", " ".join(command)))
    return results


def hardware_preflight(env: Mapping[str, str], device_id: str | None, token: str | None) -> CheckResult:
    resolved_device = (device_id or env.get("LIMA_HARDWARE_DEVICE_ID", "")).strip()
    resolved_token = (token or env.get("LIMA_HARDWARE_DEVICE_TOKEN", "")).strip()
    if not resolved_device or not resolved_token:
        return _result(
            "hardware_smoke",
            "blocked",
            "requires LIMA_HARDWARE_DEVICE_ID and LIMA_HARDWARE_DEVICE_TOKEN or matching CLI flags",
        )
    return _result("hardware_smoke", "pass", f"credentials available for device {resolved_device}")


async def run_hardware_smoke(host: str, device_id: str, token: str) -> CheckResult:
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError("Install websockets to run hardware smoke") from exc

    ws_url = f"wss://{host}/device/v1/ws?authorization=Bearer {token}"
    hello = {
        "type": "hello",
        "protocol": "lima-device-v1",
        "device_id": device_id,
        "fw_rev": "firmware-hardware-gate",
        "capabilities": ["audio", "run_path", "device_info", "self_check"],
    }
    async with websockets.connect(ws_url, additional_headers={"User-Agent": "LiMaFirmwareGate/1.0"}) as ws:
        await ws.send(json.dumps(hello, ensure_ascii=False, separators=(",", ":")))
        raw = await asyncio.wait_for(ws.recv(), timeout=15)
    ack = json.loads(raw)
    if ack.get("type") != "hello_ack":
        return _result("hardware_smoke", "fail", f"expected hello_ack, got {ack.get('type')}")
    return _result("hardware_smoke", "pass", "real /device/v1/ws hello_ack received")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LiMa firmware and hardware verification gate")
    parser.add_argument("--firmware-dir", default=str(DEFAULT_FIRMWARE_DIR))
    parser.add_argument("--target", default="esp32s3")
    parser.add_argument("--build", action="store_true", help="Run ESP-IDF build after static checks")
    parser.add_argument("--flash", action="store_true", help="Run idf.py flash after build")
    parser.add_argument("--port", default=None, help="Serial port for --flash")
    parser.add_argument("--hardware-smoke", action="store_true", help="Run real /device/v1/ws hello smoke")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--device-id", default=None)
    parser.add_argument("--device-token", default=None)
    return parser


def _print_results(results: Sequence[CheckResult]) -> None:
    for item in results:
        print(f"{item.status.upper()} {item.name} - {item.message}")


def _exit_code(results: Sequence[CheckResult]) -> int:
    statuses = {item.status for item in results}
    if "fail" in statuses:
        return 1
    if "blocked" in statuses:
        return 2
    return 0


def _resolve_hardware_credentials(
    env: Mapping[str, str],
    device_id: str | None,
    token: str | None,
) -> tuple[str, str]:
    return (
        (device_id or env.get("LIMA_HARDWARE_DEVICE_ID", "")).strip(),
        (token or env.get("LIMA_HARDWARE_DEVICE_TOKEN", "")).strip(),
    )


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    run_env = os.environ if env is None else env
    firmware_dir = Path(args.firmware_dir)
    results = static_contract_checks(firmware_dir)

    if args.build or args.flash:
        results.extend(run_idf_build(firmware_dir, target=args.target, flash=args.flash, port=args.port, env=run_env))
    else:
        results.append(_result("esp_idf_build", "skip", "not requested; pass --build to compile firmware"))

    if args.hardware_smoke:
        preflight = hardware_preflight(run_env, args.device_id, args.device_token)
        if preflight.status == "pass":
            device_id, token = _resolve_hardware_credentials(run_env, args.device_id, args.device_token)
            results.append(asyncio.run(run_hardware_smoke(args.host, device_id, token)))
        else:
            results.append(preflight)
    else:
        results.append(_result("hardware_smoke", "skip", "not requested; pass --hardware-smoke with real credentials"))

    _print_results(results)
    return _exit_code(results)


if __name__ == "__main__":
    sys.exit(main())
