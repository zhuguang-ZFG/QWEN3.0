#!/usr/bin/env python3
"""Upload latest full eval JSON to VPS for /evalreport full."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Explicit JSON path (default: newest coding_backend_scores_full_*.json)",
    )
    args = parser.parse_args()

    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    if args.json:
        local_json = args.json
    else:
        candidates = sorted(
            (base / "data").glob("coding_backend_scores_full_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            sys.exit("no local coding_backend_scores_full_*.json")
        local_json = candidates[0]

    if not local_json.is_file():
        sys.exit(f"missing {local_json}")

    helpers = [
        base / "eval_slice_summary.py",
        base / "scripts" / "run_eval_report.py",
        base / "scripts" / "run_eval_full_and_report.py",
    ]

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)
    _stdin, stdout, _stderr = ssh.exec_command(f"mkdir -p {REMOTE}/data {REMOTE}/scripts")
    stdout.read()

    sftp = ssh.open_sftp()
    remote_json = f"{REMOTE}/data/{local_json.name}"
    sftp.put(str(local_json), remote_json)
    print(f"uploaded data/{local_json.name}")

    for helper in helpers:
        if not helper.is_file():
            continue
        rel = helper.relative_to(base).as_posix()
        sftp.put(str(helper), f"{REMOTE}/{rel}")
        print(f"uploaded {rel}")
    sftp.close()

    remote_py = f"{REMOTE}/scripts/_verify_eval_full_remote.py"
    verify_src = f'''import sys
sys.path.insert(0, "{REMOTE}")
from pathlib import Path
from eval_slice_summary import latest_scores_path, summarize_eval_json

p = latest_scores_path(Path("{REMOTE}/data"), full=True)
assert p and p.name == "{local_json.name}", (p, "{local_json.name}")
text = summarize_eval_json(p, top_n=5)
assert "Eval" in text and "scnet" in text
print("eval_full_vps_ok", p.name)
print(text.splitlines()[0])
print(text.splitlines()[1])
'''
    sftp = ssh.open_sftp()
    with sftp.file(remote_py, "w") as fh:
        fh.write(verify_src)
    sftp.close()

    _stdin, stdout, stderr = ssh.exec_command(
        f"/usr/local/bin/python3.10 {remote_py}",
        timeout=60,
    )
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if err:
        print(err, file=sys.stderr)
    print(out)
    ok = "eval_full_vps_ok" in out
    if ok:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import deploy_common

        deploy_common.notify_smoke_success(
            ssh, "eval_full_json", detail=out.replace("\n", " | ")[:200]
        )
    ssh.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
