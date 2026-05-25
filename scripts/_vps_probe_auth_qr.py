#!/usr/bin/env python3
import os
import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")

PY = r"""
import asyncio, json
from pathlib import Path

async def main():
    from gateway.platforms.weixin import (
        ILINK_BASE_URL, EP_GET_BOT_QR, EP_GET_CONFIG,
        _api_get, _api_post, _make_ssl_connector, QR_TIMEOUT_MS, CONFIG_TIMEOUT_MS,
    )
    import aiohttp

    data = json.loads(Path('/root/.hermes/weixin/accounts/1fe40ec2c808@im.bot.json').read_text())
    tok, base = data['token'], data.get('base_url', ILINK_BASE_URL)
    uid = data.get('user_id', '')

    async with aiohttp.ClientSession(trust_env=True, connector=_make_ssl_connector()) as s:
        for label, call in [
            ('getconfig_owner', lambda: _api_post(s, base_url=base, endpoint=EP_GET_CONFIG, payload={'ilink_user_id': uid}, token=tok, timeout_ms=CONFIG_TIMEOUT_MS)),
            ('getconfig_empty', lambda: _api_post(s, base_url=base, endpoint=EP_GET_CONFIG, payload={}, token=tok, timeout_ms=CONFIG_TIMEOUT_MS)),
        ]:
            try:
                r = await call()
                keys = sorted(r.keys()) if isinstance(r, dict) else r
                print(label, 'keys', keys[:25])
                if isinstance(r, dict):
                    for k in ('qrcode_img_content','qrcode','share_url','bot_qrcode','add_friend','ilink_bot_id','nickname','bot_name'):
                        if r.get(k):
                            print(' ', k, str(r[k])[:120])
            except Exception as e:
                print(label, 'ERR', e)

asyncio.run(main())
"""


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("47.112.162.80", username="root", key_filename=KEY, timeout=30)
    sftp = ssh.open_sftp()
    with sftp.file("/tmp/_probe_auth.py", "w") as f:
        f.write(PY)
    sftp.close()
    _, o, e = ssh.exec_command("python3.11 /tmp/_probe_auth.py 2>&1", timeout=60)
    print((o.read() + e.read()).decode(errors="replace"))
    ssh.close()


if __name__ == "__main__":
    main()
