#!/usr/bin/env python3
import time
import paramiko
import os

KEY = os.path.expanduser("~/.ssh/id_ed25519")
OC = (
    "bash -lc 'export OPENCLAW_STATE_DIR=/opt/lima-router/openclaw/state "
    "OPENCLAW_CONFIG_PATH=/opt/lima-router/openclaw/openclaw.json "
    "PATH=/root/.nvm/versions/node/v22.22.1/bin:$PATH && "
    "openclaw pairing list openclaw-weixin 2>&1'"
)


def main():
    s = paramiko.SSHClient()
    s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    s.connect("47.112.162.80", username="root", key_filename=KEY, timeout=60)

    def r(cmd, t=30):
        _i, o, e = s.exec_command(cmd, timeout=t)
        return (o.read() + e.read()).decode()

    for i in range(12):
        time.sleep(15)
        tail = r("tail -25 /opt/lima-router/data/openclaw_login_live.log 2>/dev/null")
        cred = r("find /opt/lima-router/openclaw/state/credentials -type f")
        proc = r("pgrep -c openclaw-channels 2>/dev/null || echo 0").strip()
        print(f"\n--- {(i+1)*15}s proc={proc} ---")
        print(cred)
        if proc == "0" and len(cred.splitlines()) > 1:
            break
        if any(x in tail for x in ("成功", "complete", "Connected", "account")):
            print("tail:", tail[-600:])
            break
    print("\nLOG tail:\n", r("tail -30 /opt/lima-router/data/openclaw_login_live.log"))
    print("\nPAIRING:\n", r(OC))
    print("\nGW:", r("systemctl is-active lima-openclaw; ss -tlnp | grep 18789"))
    s.close()


if __name__ == "__main__":
    main()
