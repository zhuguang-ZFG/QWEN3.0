"""SFTP/rsync/tar file deployment helpers for unified VPS deploy."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import paramiko

from config import deploy_config
from scripts.deploy_unified_common import DeployTarget
from scripts.deploy_unified_restart import _connect_ssh


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

    ssh = _connect_ssh(target)

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


def _safe_remote_rel(raw: str) -> str | None:
    """Normalize a raw path for remote use; return None if unsafe."""
    rel = raw.replace("\\", "/").lstrip("/")
    if not rel or rel.startswith("../") or "/../" in rel or ":" in rel or rel.startswith(".."):
        return None
    return rel


def _build_rm_command(remote: str, parent: str, stem: str) -> str:
    """Build rm command for a remote file and its __pycache__ companions."""
    remote_q = shlex.quote(remote)
    parent_q = shlex.quote(parent)
    stem_q = shlex.quote(stem)
    return (
        f"rm -f -- {remote_q} "
        f"{parent_q}/__pycache__/{stem_q}.cpython-*.pyc "
        f"{parent_q}/__pycache__/{stem_q}.pyc "
        f"2>/dev/null; "
        f"if [ -e {remote_q} ]; then echo FAIL; else echo OK; fi"
    )


def remove_remote_files(paths: list[str], *, target: DeployTarget, dry_run: bool = False) -> dict:
    """Delete relative paths under target.remote_path (plus matching .pyc under __pycache__).

    Used when local files were deleted and upload-only deploy would leave orphans.
    Paths must be relative (no absolute / drive / .. segments).
    """
    results: dict = {"removed": 0, "failed": [], "skipped": []}
    if not paths:
        return results

    safe: list[str] = []
    for raw in paths:
        rel = _safe_remote_rel(raw)
        if rel is None:
            results["failed"].append(f"{raw}: unsafe path")
            continue
        safe.append(rel)

    if dry_run:
        for rel in safe:
            print(f"  WOULD REMOVE: {target.remote_path}/{rel}")
            results["removed"] += 1
        return results

    ssh = _connect_ssh(target)
    try:
        root = target.remote_path.rstrip("/")
        for rel in safe:
            remote = f"{root}/{rel}"
            parent = os.path.dirname(remote)
            base = os.path.basename(remote)
            stem = base.rsplit(".", 1)[0] if "." in base else base
            cmd = _build_rm_command(remote, parent, stem)
            _, stdout, stderr = ssh.exec_command(cmd, timeout=30)
            out = stdout.read().decode("utf-8", "replace").strip()
            err = stderr.read().decode("utf-8", "replace").strip()
            if out.endswith("OK") or out == "OK":
                results["removed"] += 1
                print(f"  REMOVED: {rel}")
            else:
                results["failed"].append(f"{rel}: {out or err or 'still exists'}")
    finally:
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
