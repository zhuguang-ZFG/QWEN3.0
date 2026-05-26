#!/usr/bin/env python3
"""VPS smoke for radar P2-16 (/uuid, eval summary imports, health)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

_REMOTE_SMOKE = """\
import sys
sys.path.insert(0, "/opt/lima-router")
from channel_gateway.public_apis_lookup import fetch_uuid
from eval_slice_summary import latest_scores_path, summarize_eval_json
from pathlib import Path
import routes.telegram_eval_tools as te
import routes.telegram_diag_tools as td

u = fetch_uuid("2")
ok_uuid = u.get("ok") and u["text"].count("-") >= 8
p = latest_scores_path(Path("/opt/lima-router/data"), full=False)
ok_eval = True
if p:
    ok_eval = "Eval" in summarize_eval_json(p)
ok_import = hasattr(te, "cmd_evalreport") and hasattr(td, "cmd_oldllm")
print("uuid_ok", ok_uuid, u.get("text", "")[:60].replace("\\n", " "))
print("eval_ok", ok_eval, p)
print("import_ok", ok_import)
print("smoke_ok" if ok_uuid and ok_import else "smoke_FAILED")
"""


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    remote_py = f"{REMOTE}/scripts/_smoke_radar_p2_16_remote.py"
    sftp = ssh.open_sftp()
    with sftp.file(remote_py, "w") as fh:
        fh.write(_REMOTE_SMOKE)
    sftp.close()

    health = ssh.exec_command("curl -sf http://127.0.0.1:8080/health | head -c 80")[1].read().decode()
    _stdin, stdout, stderr = ssh.exec_command(
        f"/usr/local/bin/python3.10 {remote_py}",
        timeout=90,
    )
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if err:
        print(err, file=sys.stderr)
    print("health:", health.strip())
    print(out)
    ok = "smoke_ok" in out and health.strip()
    if ok:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import deploy_common

        deploy_common.notify_smoke_success(
            ssh, "radar_p2_16", detail=out.replace("\n", " | ")[:200]
        )
    ssh.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
