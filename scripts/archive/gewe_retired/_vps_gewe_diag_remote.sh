#!/bin/bash
set -e
echo "=== probe qr ==="
cd /opt/lima-router && /usr/local/bin/python3.10 _vps_gewe_qr_probe.py || true
echo "=== devicelibrary log ==="
podman exec gewe sh -c 'for f in /root/gewe/base/log/devicelibrary.txt /root/temp/log/devicelibrary.txt; do [ -f "$f" ] && tail -n 25 "$f" && exit 0; done; find /root -name devicelibrary.txt 2>/dev/null | head -3' || true
echo "=== outbound ==="
curl -sI --max-time 8 https://short.weixin.qq.com/ | head -5 || echo weixin_fail
curl -sI --max-time 8 https://www.baidu.com/ | head -3 || echo baidu_fail
