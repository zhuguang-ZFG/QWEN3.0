"""ESP-IDF environment helpers for firmware verification."""

from __future__ import annotations

import os
import re
import sys
from glob import glob
from pathlib import Path
from typing import Mapping, Sequence

IDF_TOOL_PATH_GLOBS = (
    ("xtensa-esp-elf-gdb", "*", "xtensa-esp-elf-gdb", "bin"),
    ("riscv32-esp-elf-gdb", "*", "riscv32-esp-elf-gdb", "bin"),
    ("xtensa-esp-elf", "*", "xtensa-esp-elf", "bin"),
    ("riscv32-esp-elf", "*", "riscv32-esp-elf", "bin"),
    ("esp32ulp-elf", "*", "esp32ulp-elf", "bin"),
    ("cmake", "*", "bin"),
    ("openocd-esp32", "*", "openocd-esp32", "bin"),
    ("ninja", "*"),
    ("idf-exe", "*"),
    ("ccache", "*", "*"),
    ("dfu-util", "*", "*"),
)


def idf_version_prefix(idf_path: Path) -> str | None:
    version_file = idf_path / "tools" / "cmake" / "version.cmake"
    if not version_file.exists():
        return None
    text = version_file.read_text(encoding="utf-8")
    major_match = re.search(r"set\(IDF_VERSION_MAJOR\s+(\d+)\)", text)
    minor_match = re.search(r"set\(IDF_VERSION_MINOR\s+(\d+)\)", text)
    if major_match is None or minor_match is None:
        return None
    return f"{major_match.group(1)}.{minor_match.group(1)}"


def venv_python_path(venv_root: Path) -> Path:
    if sys.platform == "win32":
        return venv_root / "Scripts" / "python.exe"
    return venv_root / "bin" / "python"


def idf_python_env_path(idf_path: Path, env: Mapping[str, str] | None = None) -> Path | None:
    explicit_env = (env or {}).get("IDF_PYTHON_ENV_PATH", "").strip()
    if explicit_env and venv_python_path(Path(explicit_env)).exists():
        return Path(explicit_env)
    tools_path = (env or {}).get("IDF_TOOLS_PATH", "").strip()
    version_prefix = idf_version_prefix(idf_path)
    if not tools_path or version_prefix is None:
        return None
    for candidate_root in sorted((Path(tools_path) / "python_env").glob(f"idf{version_prefix}_py*_env")):
        version_marker = candidate_root / "idf_version.txt"
        if (
            venv_python_path(candidate_root).exists()
            and version_marker.exists()
            and version_marker.read_text(encoding="utf-8").strip() == version_prefix
        ):
            return candidate_root
    return None


def idf_python_executable(idf_path: Path, env: Mapping[str, str] | None = None) -> str:
    idf_python_env = idf_python_env_path(idf_path, env)
    if idf_python_env is not None:
        return str(venv_python_path(idf_python_env))
    return sys.executable


def clean_idf_env(env: Mapping[str, str] | None) -> dict[str, str]:
    cleaned = dict(os.environ if env is None else env)
    for key in list(cleaned):
        if key == "MSYSTEM" or key == "CHERE_INVOKING" or key.startswith("MSYSTEM_") or key.startswith("MINGW_"):
            cleaned.pop(key, None)
    idf_path = Path(cleaned["IDF_PATH"]) if cleaned.get("IDF_PATH", "").strip() else None
    if idf_path is not None:
        idf_python_env = idf_python_env_path(idf_path, cleaned)
        if idf_python_env is not None:
            cleaned["IDF_PYTHON_ENV_PATH"] = str(idf_python_env)
            cleaned["PATH"] = merge_path(cleaned.get("PATH", ""), [str(venv_python_path(idf_python_env).parent)])
        version_prefix = idf_version_prefix(idf_path)
        if version_prefix is not None:
            cleaned["ESP_IDF_VERSION"] = version_prefix
    if cleaned.get("IDF_TOOLS_PATH", "").strip():
        tools_path = Path(cleaned["IDF_TOOLS_PATH"])
        cleaned["PATH"] = merge_path(cleaned.get("PATH", ""), idf_tool_paths(tools_path))
        esp_rom_elf_dir = latest_matching_path(tools_path / "tools" / "esp-rom-elfs" / "*")
        if esp_rom_elf_dir is not None:
            cleaned.setdefault("ESP_ROM_ELF_DIR", str(esp_rom_elf_dir))
        openocd_scripts = latest_matching_path(
            tools_path / "tools" / "openocd-esp32" / "*" / "openocd-esp32" / "share" / "openocd" / "scripts"
        )
        if openocd_scripts is not None:
            cleaned.setdefault("OPENOCD_SCRIPTS", str(openocd_scripts))
    return cleaned


def idf_tool_paths(tools_path: Path) -> list[str]:
    paths: list[str] = []
    for pattern in IDF_TOOL_PATH_GLOBS:
        for candidate in sorted((tools_path / "tools").glob(str(Path(*pattern)))):
            if candidate.exists():
                paths.append(str(candidate))
    return paths


def merge_path(existing_path: str, paths: Sequence[str]) -> str:
    seen: set[str] = set()
    merged: list[str] = []
    for item in [*paths, *existing_path.split(os.pathsep)]:
        if item and item not in seen:
            seen.add(item)
            merged.append(item)
    return os.pathsep.join(merged)


def latest_matching_path(pattern: Path) -> Path | None:
    candidates = [Path(candidate) for candidate in glob(str(pattern)) if Path(candidate).exists()]
    if not candidates:
        return None
    return sorted(candidates)[-1]
