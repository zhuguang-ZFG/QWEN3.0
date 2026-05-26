#!/usr/bin/env python3
"""Sync GITEE_TOKEN from local git remote oauth2 to VPS .env (never logs token)."""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy_common import KEY, REMOTE, SERVER
from gitee_mirror import gitee_token_from_git_remotes


def main() -> int:
    token = (
        os.environ.get("GITEE_TOKEN", "").strip()
        or os.environ.get("GITEE_ACCESS_TOKEN", "").strip()
        or gitee_token_from_git_remotes(ROOT)
    )
    if not token:
        print("SKIP: no GITEE_TOKEN locally or in git remote", file=sys.stderr)
        return 2
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    env_path = f"{REMOTE}/.env"
    tmp_remote = f"{REMOTE}/.gitee_token_once"
    helper_remote = f"{REMOTE}/scripts/_provision_gitee_token_once.py"

    helper_src = textwrap.dedent(
        f"""
        from pathlib import Path

        env_path = Path({env_path!r})
        token = Path({tmp_remote!r}).read_text(encoding="utf-8").strip()
        key = "GITEE_TOKEN"
        lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.is_file() else []
        out = []
        found = False
        for line in lines:
            if line.startswith(key + "="):
                out.append(key + "=" + token)
                found = True
            else:
                out.append(line)
        if not found:
            out.append(key + "=" + token)
        env_path.write_text("\\n".join(out) + "\\n", encoding="utf-8")
        print("provision_gitee_token_ok")
        """
    ).strip()

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    sftp = ssh.open_sftp()
    _run(ssh, f"mkdir -p {REMOTE}/scripts")
    with sftp.file(tmp_remote, "w") as fh:
        fh.write(token)
    sftp.chmod(tmp_remote, 0o600)
    with sftp.file(helper_remote, "w") as fh:
        fh.write(helper_src)
    sftp.close()

    code, out = _run(ssh, f"/usr/local/bin/python3.10 {helper_remote}", timeout=60)
    _run(ssh, f"rm -f {tmp_remote} {helper_remote}", timeout=15)
    ssh.close()

    if code != 0 or "provision_gitee_token_ok" not in out:
        print(f"provision_gitee_token_FAIL code={code} {out[:200]}", file=sys.stderr)
        return 1
    print("provision_gitee_token_ok")
    return 0


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 60) -> tuple[int, str]:
    _i, o, e = ssh.exec_command(cmd, timeout=timeout)
    text = (o.read() + e.read()).decode("utf-8", errors="replace").strip()
    return o.channel.recv_exit_status(), text


if __name__ == "__main__":
    raise SystemExit(main())
