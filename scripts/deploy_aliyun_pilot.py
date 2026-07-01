"""Deploy LiMa Router Pilot to the Aliyun auxiliary node.

This script runs locally and pushes the current repository to the Aliyun VPS,
then executes the install script on the remote host.

Example:
    python scripts/deploy_aliyun_pilot.py

Environment:
    LIMA_ALIYUN_SERVER      Aliyun VPS IP (default 47.112.162.80)
    LIMA_ALIYUN_PASSWORD    SSH password (key auth preferred)
    LIMA_DEPLOY_KEY_PATH    SSH private key path
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from dotenv import load_dotenv

# Load local .env so LIMA_DEPLOY_KEY_PATH and friends are available.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Allow importing project modules when running the script directly.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.deploy_config import (
    ALIYUN_PASSWORD,
    ALIYUN_SERVER,
    DEPLOY_KEY_PATH,
    expanded_key_path,
)

_log = logging.getLogger(__name__)

PILOT_DIR = "/opt/lima-router-pilot"
INSTALL_SCRIPT = "deploy/aliyun/install_aliyun_pilot.sh"


_TARBALL_EXCLUDES: set[str] = {
    ".git",
    ".venv",
    ".venv310",
    ".venv314",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".lima-data",
    "chroma_db",
    "data",
    "logs",
    "docs/archive",
    "reference",
    "esp32S_XYZ",
    "chat-web",
    "donglicao-site-v2",
    ".tmp_aliyun_pilot.tar.gz",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ssh_base_args(password: str) -> list[str]:
    args = [
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "BatchMode=no",
    ]
    key_path = expanded_key_path()
    if key_path and Path(key_path).exists():
        args += ["-i", key_path]
    return args


def _ssh_cmd(host: str, command: str, password: str) -> None:
    base = _ssh_base_args(password)
    cmd = ["ssh"] + base + [f"root@{host}", command]
    _log.info("Running on %s: %s", host, command)
    subprocess.run(cmd, check=True)


def _scp_to_host(host: str, local_path: Path, remote_path: str, password: str) -> None:
    base = _ssh_base_args(password)
    cmd = ["scp"] + base + [str(local_path), f"root@{host}:{remote_path}"]
    _log.info("Copying %s -> root@%s:%s", local_path, host, remote_path)
    subprocess.run(cmd, check=True)


def _should_include(path: Path, root: Path, excludes: set[str]) -> bool:
    rel = path.relative_to(root)
    for part in rel.parts:
        if part in excludes or part.startswith(".venv"):
            return False
    return True


def _add_path_to_tar(tar: tarfile.TarFile, path: Path, root: Path) -> None:
    try:
        is_file = path.is_file()
        is_dir = path.is_dir()
    except (OSError, PermissionError):
        return
    if is_file:
        tar.add(path, arcname=path.relative_to(root))
        return
    if is_dir:
        try:
            has_children = any(path.iterdir())
        except (OSError, PermissionError):
            return
        if not has_children:
            tar.add(path, arcname=path.relative_to(root))


def _create_tarball(root: Path, excludes: set[str]) -> Path:
    """Create a gzipped tarball of the repository and return its path."""
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tarball_path = Path(tmp.name)

    try:
        _log.info("Creating local tarball of repository")
        with tarfile.open(tarball_path, "w:gz") as tar:
            for item in root.rglob("*"):
                if not _should_include(item, root, excludes):
                    continue
                _add_path_to_tar(tar, item, root)
        return tarball_path
    except Exception:
        if tarball_path.exists():
            tarball_path.unlink()
        raise


def _extract_remote(host: str, password: str, remote_tarball: str) -> None:
    """Extract the tarball on the remote host and clean it up."""
    _log.info("Extracting tarball on remote host")
    _ssh_cmd(
        host,
        f"rm -rf {PILOT_DIR}/repo && mkdir -p {PILOT_DIR}/repo && "
        f"tar -xzf {remote_tarball} -C {PILOT_DIR}/repo && "
        f"rm -f {remote_tarball}",
        password,
    )


def _sync_repo(host: str, password: str) -> None:
    """Push repository source to the pilot directory on Aliyun via tar+scp."""
    root = _repo_root()
    tarball_path = _create_tarball(root, _TARBALL_EXCLUDES)
    try:
        remote_tarball = f"{PILOT_DIR}/repo.tar.gz"
        _scp_to_host(host, tarball_path, remote_tarball, password)
        _extract_remote(host, password, remote_tarball)
    finally:
        if tarball_path.exists():
            tarball_path.unlink()


def deploy(host: str, password: str) -> None:
    _log.info("Deploying LiMa Router Pilot to %s", host)

    # Ensure remote pilot directory exists.
    _ssh_cmd(host, f"mkdir -p {PILOT_DIR}", password)

    # Sync code.
    _sync_repo(host, password)

    # Run install script on remote host.
    install_remote = f"{PILOT_DIR}/repo/{INSTALL_SCRIPT}"
    _ssh_cmd(host, f"bash {install_remote}", password)

    _log.info("Deployment complete")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deploy LiMa Router Pilot to Aliyun")
    parser.add_argument("--host", default=ALIYUN_SERVER, help="Aliyun VPS IP")
    parser.add_argument("--password", default=ALIYUN_PASSWORD, help="SSH password")
    parser.add_argument("--dry-run", action="store_true", help="Print commands but do not execute")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

    if args.dry_run:
        print(f"Would deploy to {args.host}")
        return 0

    password = args.password or os.environ.get("LIMA_ALIYUN_PASSWORD", "")
    if not password and not Path(expanded_key_path()).exists():
        _log.error("No SSH password or deploy key provided")
        return 1

    deploy(args.host, password)
    return 0


if __name__ == "__main__":
    sys.exit(main())
