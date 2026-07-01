"""SFTP/rsync/tar file deployment helpers for unified VPS deploy."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import paramiko

from config import deploy_config
from scripts.deploy_common import configure_ssh_host_keys
from scripts.deploy_unified_common import DeployTarget


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
    """Build SSH options for external SSH clients from the same config as paramiko."""
    opts = [
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "ConnectTimeout=30",
        "-o",
        "ServerAliveInterval=15",
    ]
    resolved_key = key_file or deploy_config.expanded_key_path()
    if os.path.exists(resolved_key):
        opts += ["-i", resolved_key]
    known_hosts = known_hosts_file or deploy_config.expanded_known_hosts()
    if known_hosts and os.path.exists(known_hosts):
        opts += ["-o", f"UserKnownHostsFile={known_hosts}"]
    return opts


def _ssh_base_cmd(target: DeployTarget, *, known_hosts_file: str | None = None) -> list[str]:
    return [
        "ssh",
        *_ssh_options(target.key_path, known_hosts_file),
        f"{target.user}@{target.host}",
    ]


def _filter_existing_files(files: list[str], project_root: Path) -> tuple[list[str], list[str]]:
    """Split file list into existing and skipped."""
    existing: list[str] = []
    skipped: list[str] = []
    for f in files:
        if (project_root / f).exists():
            existing.append(f)
        else:
            skipped.append(f)
    return existing, skipped


def _deploy_with_rsync(files: list[str], target: DeployTarget) -> dict:
    """Deploy files with rsync over SSH; much faster than one-at-a-time SFTP."""
    project_root = Path(__file__).resolve().parent.parent
    existing, skipped = _filter_existing_files(files, project_root)
    if not existing:
        return {"uploaded": 0, "failed": [], "skipped": skipped}

    ssh_cmd = " ".join(["ssh", *_ssh_options(target.key_path, deploy_config.expanded_known_hosts())])

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
            f"{target.user}@{target.host}:{target.remote_path}/",
        ]
        print(f"rsync: uploading {len(existing)} files via SSH...")
        proc = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=600)
        if proc.returncode != 0:
            err = proc.stderr[-800:] if proc.stderr else proc.stdout[-800:]
            raise RuntimeError(f"rsync failed (exit {proc.returncode}): {err}")
        return {"uploaded": len(existing), "failed": [], "skipped": skipped}
    finally:
        try:
            os.unlink(list_path)
        except OSError:
            pass


def _deploy_with_tar(files: list[str], target: DeployTarget) -> dict:
    """Deploy files as a tar archive over scp/ssh; avoids many small file overhead."""
    project_root = Path(__file__).resolve().parent.parent
    existing, skipped = _filter_existing_files(files, project_root)
    if not existing:
        return {"uploaded": 0, "failed": [], "skipped": skipped}

    ssh_opts = _ssh_options(target.key_path, deploy_config.expanded_known_hosts())
    archive_name = f"lima-deploy-{os.getpid()}-{tempfile.gettempprefix()}.tar.gz"
    archive_local = Path(tempfile.gettempdir()) / archive_name
    archive_remote = f"/tmp/{archive_name}"

    try:
        print(f"tar: packing {len(existing)} files...")
        with tarfile.open(archive_local, "w:gz") as tar:
            for f in existing:
                tar.add(project_root / f, arcname=f)

        scp_cmd = ["scp", *ssh_opts, str(archive_local), f"{target.user}@{target.host}:{archive_remote}"]
        print(f"tar: uploading archive ({archive_local.stat().st_size / 1024 / 1024:.2f} MB)...")
        proc = subprocess.run(scp_cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=600)
        if proc.returncode != 0:
            err = proc.stderr[-800:] if proc.stderr else proc.stdout[-800:]
            raise RuntimeError(f"scp failed (exit {proc.returncode}): {err}")

        ssh_cmd = _ssh_base_cmd(target, known_hosts_file=deploy_config.expanded_known_hosts())
        extract_cmd = f"mkdir -p {target.remote_path} && tar -xzf {archive_remote} -C {target.remote_path} && rm -f {archive_remote}"
        print("tar: extracting archive on remote...")
        proc = subprocess.run(
            [*ssh_cmd, extract_cmd],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=300,
        )
        if proc.returncode != 0:
            err = proc.stderr[-800:] if proc.stderr else proc.stdout[-800:]
            raise RuntimeError(f"remote extract failed (exit {proc.returncode}): {err}")

        return {"uploaded": len(existing), "failed": [], "skipped": skipped}
    finally:
        try:
            archive_local.unlink(missing_ok=True)
        except OSError:
            pass


def _deploy_with_sftp(files: list[str], target: DeployTarget) -> dict:
    """Original one-at-a-time SFTP fallback."""
    project_root = Path(__file__).resolve().parent.parent
    results = {"uploaded": 0, "failed": [], "skipped": []}

    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    configure_ssh_host_keys(ssh)
    try:
        ssh.connect(target.host, username=target.user, key_filename=target.key_path, timeout=15)
    except paramiko.SSHException:
        if not target.password:
            raise
        ssh.connect(target.host, username=target.user, password=target.password, timeout=15)

    sftp = ssh.open_sftp()
    try:
        for f in files:
            local = project_root / f
            if not local.exists():
                results["skipped"].append(f)
                continue
            remote = f"{target.remote_path}/{f}"
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


def deploy_files(files: list[str], *, target: DeployTarget, dry_run: bool = False) -> dict:
    """Deploy a list of files to a VPS target via tar/scp, rsync, or SFTP."""
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

    use_tar = deploy_config.deploy_use_tar()
    if use_tar:
        try:
            return _deploy_with_tar(files, target)
        except Exception as e:
            print(f"tar/scp upload failed, falling back to SFTP: {e}", file=sys.stderr)

    use_rsync = deploy_config.deploy_use_rsync()
    if use_rsync and _rsync_available():
        try:
            return _deploy_with_rsync(files, target)
        except Exception as e:
            print(f"rsync upload failed, falling back to SFTP: {e}", file=sys.stderr)

    return _deploy_with_sftp(files, target)
