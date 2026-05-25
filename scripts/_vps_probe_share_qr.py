#!/usr/bin/env python3
"""Probe whether share QR matches active bot on VPS."""
import os

import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")

PY = r"""
import asyncio, json, re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

async def main():
    from gateway.platforms.weixin import (
        ILINK_BASE_URL, EP_GET_BOT_QR, EP_GET_QR_STATUS,
        _api_get, _make_ssl_connector, QR_TIMEOUT_MS,
    )
    import aiohttp

    acc_path = Path('/root/.hermes/weixin/accounts/1fe40ec2c808@im.bot.json')
    active = acc_path.stem
    cache = json.loads(Path('/opt/lima-router/data/weixin_share_qr.json').read_text())
    share = cache.get('share_url', '')
    print('active_bot', active)
    print('cache_account', cache.get('account_id'))
    print('share_url', share[:100])

    m = re.search(r'qrcode=([a-f0-9]+)', share)
    qrcode = m.group(1) if m else ''
    print('share_qrcode_token', qrcode[:32] if qrcode else 'none')

    async with aiohttp.ClientSession(trust_env=True, connector=_make_ssl_connector()) as s:
        st = await _api_get(
            s, base_url=ILINK_BASE_URL,
            endpoint=f'{EP_GET_QR_STATUS}?qrcode={qrcode}',
            timeout_ms=QR_TIMEOUT_MS,
        )
        print('status_for_share_qr', {k: st.get(k) for k in ('status','ilink_bot_id','errmsg','ret','errcode')})

        qr = await _api_get(
            s, base_url=ILINK_BASE_URL,
            endpoint=f'{EP_GET_BOT_QR}?bot_type=3',
            timeout_ms=QR_TIMEOUT_MS,
        )
        q2 = str(qr.get('qrcode') or '')
        print('fresh_anon_qrcode', q2[:32])
        url2 = str(qr.get('qrcode_img_content') or '')[:100]
        print('fresh_anon_url', url2)

asyncio.run(main())
"""


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("47.112.162.80", username="root", key_filename=KEY, timeout=30)
    sftp = ssh.open_sftp()
    with sftp.file("/tmp/_probe_share.py", "w") as f:
        f.write(PY)
    sftp.close()
    _, o, e = ssh.exec_command("python3.11 /tmp/_probe_share.py 2>&1", timeout=60)
    print((o.read() + e.read()).decode(errors="replace"))
    ssh.close()


if __name__ == "__main__":
    main()
