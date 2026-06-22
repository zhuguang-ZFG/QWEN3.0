"""SFTP/rsync/tar file deployment helpers for unified VPS deploy."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
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
    if key_file and os.path.exists(os.path.expanduser(key_file)):
        opts += ["-i", os.path.expanduser(key_file)]
    known_hosts = known_hosts_file or os.path.expanduser("~/.ssh/known_hosts")
    if known_hosts and os.path.exists(os.path.expanduser(known_hosts)):
        opts += ["-o", f"UserKnownHostsFile={os.path.expanduser(known_hosts)}"]
    return opts


def _ssh_base_cmd(key_file: str | None, known_hosts_file: str | None) -> list[str]:
    return ["ssh", *_ssh_options(key_file, known_hosts_file), f"root@{SERVER}"]


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


def _deploy_with_rsync(files: list[str]) -> dict:
    """Deploy files with rsync over SSH; much faster than one-at-a-time SFTP."""
    project_root = Path(__file__).resolve().parent.parent
    existing, skipped = _filter_existing_files(files, project_root)
    if not existing:
        return {"uploaded": 0, "failed": [], "skipped": skipped}

    ssh_cmd = " ".join(["ssh", *_ssh_options(KEY, os.environ.get("LIMA_DEPLOY_KNOWN_HOSTS"))])

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


def _deploy_with_tar(files: list[str]) -> dict:
    """Deploy files as a tar archive over scp/ssh; avoids many small file overhead."""
    project_root = Path(__file__).resolve().parent.parent
    existing, skipped = _filter_existing_files(files, project_root)
    if not existing:
        return {"uploaded": 0, "failed": [], "skipped": skipped}

    ssh_opts = _ssh_options(KEY, os.environ.get("LIMA_DEPLOY_KNOWN_HOSTS"))
    archive_name = f"lima-deploy-{os.getpid()}-{tempfile.gettempprefix()}.tar.gz"
    archive_local = Path(tempfile.gettempdir()) / archive_name
    archive_remote = f"/tmp/{archive_name}"

    try:
        print(f"tar: packing {len(existing)} files...")
        with tarfile.open(archive_local, "w:gz") as tar:
            for f in existing:
                tar.add(project_root / f, arcname=f)

        scp_cmd = ["scp", *ssh_opts, str(archive_local), f"root@{SERVER}:{archive_remote}"]
        print(f"tar: uploading archive ({archive_local.stat().st_size / 1024 / 1024:.2f} MB)...")
        proc = subprocess.run(scp_cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=600)
        if proc.returncode != 0:
            err = proc.stderr[-800:] if proc.stderr else proc.stdout[-800:]
            raise RuntimeError(f"scp failed (exit {proc.returncode}): {err}")

        ssh_cmd = _ssh_base_cmd(KEY, os.environ.get("LIMA_DEPLOY_KNOWN_HOSTS"))
        extract_cmd = f"mkdir -p {REMOTE} && tar -xzf {archive_remote} -C {REMOTE} && rm -f {archive_remote}"
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


def _deploy_with_sftp(files: list[str]) -> dict:
    """Original one-at-a-time SFTP fallback."""
    project_root = Path(__file__).resolve().parent.parent
    results = {"uploaded": 0, "failed": [], "skipped": []}

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


def deploy_files(files: list[str], *, dry_run: bool = False) -> dict:
    """Deploy a list of files to VPS via tar/scp, rsync, or SFTP."""
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

    use_tar = os.environ.get("LIMA_DEPLOY_USE_TAR", "").strip().lower() in {"1", "true", "yes"}
    if use_tar:
        try:
            return _deploy_with_tar(files)
        except Exception as e:
            print(f"tar/scp upload failed, falling back to SFTP: {e}", file=sys.stderr)

    use_rsync = os.environ.get("LIMA_DEPLOY_USE_RSYNC", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if use_rsync and _rsync_available():
        try:
            return _deploy_with_rsync(files)
        except Exception as e:
            print(f"rsync upload failed, falling back to SFTP: {e}", file=sys.stderr)

    return _deploy_with_sftp(files)
