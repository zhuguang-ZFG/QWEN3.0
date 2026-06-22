"""SFTP/rsync file deployment helpers for unified VPS deploy."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from scripts.deploy_common import REMOTE, KEY, SERVER, configure_ssh_host_keys
import paramiko


def ensure_remote_dir(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    """Create a remote directory tree using SFTP only."""
    normalized = remote_dir.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    current = "/" if normalized.startswith("/") else ""

    for part in parts:
        current = f"{current.rstrip('/')}/{part}" if current else part
        try:
            sftp.stat(current)
        except (FileNotFoundError, OSError):
            try:
                sftp.mkdir(current)
            except OSError:
                sftp.stat(current)


def _rsync_available() -> bool:
    return shutil.which("rsync") is not None


def _ssh_options(key_file: str | None, known_hosts_file: str | None) -> list[str]:
    """Build SSH options for rsync from the same env/config used by paramiko."""
    opts = ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes"]
    if key_file and os.path.exists(os.path.expanduser(key_file)):
        opts += ["-i", os.path.expanduser(key_file)]
    known_hosts = known_hosts_file or os.path.expanduser("~/.ssh/known_hosts")
    if known_hosts and os.path.exists(os.path.expanduser(known_hosts)):
        opts += ["-o", f"UserKnownHostsFile={os.path.expanduser(known_hosts)}"]
    return opts


def _deploy_with_rsync(files: list[str]) -> dict:
    """Deploy files with rsync over SSH; much faster than one-at-a-time SFTP."""
    project_root = Path(__file__).resolve().parent.parent
    results = {"uploaded": 0, "failed": [], "skipped": []}

    existing = []
    for f in files:
        local = project_root / f
        if local.exists():
            existing.append(f)
        else:
            results["skipped"].append(f)

    if not existing:
        return results

    ssh_cmd_parts = ["ssh", *_ssh_options(KEY, os.environ.get("LIMA_DEPLOY_KNOWN_HOSTS"))]
    ssh_cmd = " ".join(ssh_cmd_parts)

    with tempfile.NamedTemporaryFile(mode="w", prefix="lima-deploy-files-", suffix=".txt", delete=False) as list_file:
        for f in existing:
            list_file.write(f"{f}\n")
        list_path = list_file.name

    try:
        cmd = [
            "rsync",
            "-avz",
            "--delete-delay",
            "--files-from",
            list_path,
            "-e",
            ssh_cmd,
            f"{project_root}/",
            f"root@{SERVER}:{REMOTE}/",
        ]
        print(f"rsync: uploading {len(existing)} files via SSH...")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            # Surface enough detail to debug without leaking secrets.
            err = proc.stderr[-800:] if proc.stderr else proc.stdout[-800:]
            raise RuntimeError(f"rsync failed (exit {proc.returncode}): {err}")
        results["uploaded"] = len(existing)
    finally:
        try:
            os.unlink(list_path)
        except OSError:
            pass

    return results


def deploy_files(files: list[str], *, dry_run: bool = False) -> dict:
    """Deploy a list of files to VPS via SFTP or rsync."""
    project_root = Path(__file__).resolve().parent.parent
    results = {"uploaded": 0, "failed": [], "skipped": []}

    if dry_run:
        for f in files:
            local = project_root / f
            if local.exists():
                print(f"  WOULD UPLOAD: {f}")
                results["uploaded"] += 1
            else:
                print(f"  SKIP (not found): {f}")
                results["skipped"].append(f)
        return results

    use_rsync = os.environ.get("LIMA_DEPLOY_USE_RSYNC", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if use_rsync and _rsync_available():
        try:
            return _deploy_with_rsync(files)
        except Exception as e:
            print(f"rsync upload failed, falling back to SFTP: {e}")

    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    configure_ssh_host_keys(ssh)
    password = os.environ.get("LIMA_DEPLOY_PASS")
    try:
        ssh.connect(SERVER, username="root", key_filename=KEY, timeout=15)
    except paramiko.SSHException:
        if not password:
            raise
        ssh.connect(SERVER, username="root", password=password, timeout=15)

    sftp = ssh.open_sftp()
    try:
        for f in files:
            local = project_root / f
            if not local.exists():
                results["skipped"].append(f)
                continue
            remote = f"{REMOTE}/{f}"
            try:
                remote_dir = os.path.dirname(remote)
                ensure_remote_dir(sftp, remote_dir)
                sftp.put(str(local), remote)
                results["uploaded"] += 1
            except Exception as e:
                results["failed"].append(f"{f}: {e}")
    finally:
        sftp.close()
        ssh.close()
    return results
