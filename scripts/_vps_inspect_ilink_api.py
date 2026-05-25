#!/usr/bin/env python3
"""Inspect iLink API fields for active bot on VPS."""
import json
import os

import paramiko

KEY = os.path.expanduser("~/.ssh/id_ed25519")

PY = r"""
import asyncio, json
from pathlib import Path

async def main():
    from gateway.platforms.weixin import (
        ILINK_BASE_URL, EP_GET_BOT_QR, _api_get, _make_ssl_connector,
        _get_config, CONFIG_TIMEOUT_MS, check_weixin_requirements,
    )
    import aiohttp
    home = Path('/root/.hermes/weixin/accounts')
    acc = sorted([p for p in home.glob('*.json') if 'context' not in p.name and 'sync' not in p.name])[0]
    data = json.loads(acc.read_text())
    aid, tok, base = acc.stem, data['token'], data.get('base_url', ILINK_BASE_URL)
    print('account', aid)
    async with aiohttp.ClientSession(trust_env=True, connector=_make_ssl_connector()) as s:
        cfg = await _get_config(s, base_url=base, token=tok, timeout_ms=CONFIG_TIMEOUT_MS)
        keys = sorted(cfg.keys()) if isinstance(cfg, dict) else []
        print('getconfig keys', keys[:30])
        for k in ('share_url', 'qrcode', 'qrcode_img_content', 'bot_qr', 'add_friend_url'):
            if isinstance(cfg, dict) and cfg.get(k):
                print(k, str(cfg[k])[:120])
        qr = await _api_get(s, base_url=ILINK_BASE_URL, endpoint=f'{EP_GET_BOT_QR}?bot_type=3', timeout_ms=15000)
        print('anonymous get_bot_qr keys', sorted(qr.keys()) if isinstance(qr, dict) else qr)
        if isinstance(qr, dict):
            print('anon qrcode prefix', str(qr.get('qrcode_img_content') or qr.get('qrcode') or '')[:100])

asyncio.run(main())
"""

def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("47.112.162.80", username="root", key_filename=KEY, timeout=30)
    sftp = ssh.open_sftp()
    with sftp.file("/tmp/_inspect_ilink.py", "w") as f:
        f.write(PY)
    sftp.close()
    _, o, e = ssh.exec_command(
        "cd /opt/lima-router && python3.11 /tmp/_inspect_ilink.py 2>&1", timeout=60
    )
    print((o.read() + e.read()).decode(errors="replace"))
    ssh.close()


if __name__ == "__main__":
    main()
