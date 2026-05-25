#!/usr/bin/env python3
"""Deep guest no-reply diag on VPS."""
import os

import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")


def run(cmd: str, t: int = 120) -> str:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("47.112.162.80", username="root", key_filename=KEY, timeout=30)
    _, o, e = ssh.exec_command(cmd, timeout=t)
    return (o.read() + e.read()).decode(errors="replace").strip()


def main() -> None:
    q = [
        ("inbound_all", "journalctl -u lima-weixin-ilink --since '6 hours ago' --no-pager | grep 'inbound from='"),
        ("send_fail", "journalctl -u lima-weixin-ilink --since '6 hours ago' --no-pager | grep -iE 'send_message|send failed|replied ok=False|HTTP 4|empty reply|skip duplicate' | tail -30"),
        ("recent40", "journalctl -u lima-weixin-ilink --since '2 hours ago' --no-pager | tail -45"),
        ("share", "cat /opt/lima-router/data/weixin_share_qr.json"),
        ("probe_qr", "python3.11 /tmp/_probe_guest_qr.py 2>&1"),
        ("ctx_tokens", "cat /root/.hermes/weixin/accounts/1fe40ec2c808@im.bot.context-tokens.json 2>/dev/null | head -c 800"),
    ]
    py = r'''
import asyncio, json, re
from pathlib import Path

async def main():
    from gateway.platforms.weixin import (
        ILINK_BASE_URL, EP_GET_QR_STATUS, _api_get, _make_ssl_connector, QR_TIMEOUT_MS,
    )
    import aiohttp
    cache = json.loads(Path("/opt/lima-router/data/weixin_share_qr.json").read_text())
    url = cache.get("share_url", "")
    m = re.search(r"qrcode=([a-f0-9]+)", url)
    qc = m.group(1) if m else ""
    active = "1fe40ec2c808@im.bot"
    print("cached_url", url[:90])
    print("qrcode", qc)
    async with aiohttp.ClientSession(trust_env=True, connector=_make_ssl_connector()) as s:
        if qc:
            st = await _api_get(s, ILINK_BASE_URL, f"{EP_GET_QR_STATUS}?qrcode={qc}", QR_TIMEOUT_MS)
            print("status", {k: st.get(k) for k in ("status","ilink_bot_id","errmsg","ret","errcode")})
    # live poll 5s - any msgs from non-owner?
    from gateway.platforms.weixin import _get_updates, _load_sync_buf
    acc = Path("/root/.hermes/weixin/accounts/1fe40ec2c808@im.bot.json")
    d = json.loads(acc.read_text())
    tok, base = d["token"], d.get("base_url", ILINK_BASE_URL)
    buf = _load_sync_buf("/root/.hermes", active)
    async with aiohttp.ClientSession(trust_env=True, connector=_make_ssl_connector()) as s:
        r = await _get_updates(s, base_url=base, token=tok, sync_buf=buf, timeout_ms=5000)
        msgs = r.get("msgs") or []
        print("poll_msgs", len(msgs), "errcode", r.get("errcode"), "ret", r.get("ret"))
        owners = set()
        for m in msgs[:20]:
            fid = str(m.get("from_user_id") or "")[:20]
            txt = ""
            for it in m.get("item_list") or []:
                if it.get("text_item"):
                    txt = str(it["text_item"].get("text") or "")[:30]
            print(" msg", fid, txt)

asyncio.run(main())
'''
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("47.112.162.80", username="root", key_filename=KEY, timeout=30)
    sftp = ssh.open_sftp()
    with sftp.file("/tmp/_probe_guest_qr.py", "w") as f:
        f.write(py)
    sftp.close()
    ssh.close()

    for name, cmd in q:
        print(f"\n=== {name} ===")
        print(run(cmd) or "(empty)")


if __name__ == "__main__":
    main()
