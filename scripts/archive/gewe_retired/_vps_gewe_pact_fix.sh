#!/bin/bash
# Fix gewe device library: ensure pact/long services and port 4600
set -e
echo "=== container ==="
docker ps --filter name=gewe
echo "=== ports in container ==="
docker exec gewe ss -tlnp 2>/dev/null | head -25 || true
echo "=== supervisor ==="
docker exec gewe supervisorctl status 2>/dev/null || true
echo "=== restart pact/long/gewe ==="
docker exec gewe supervisorctl restart pact long gewe 2>/dev/null || true
sleep 20
docker exec gewe supervisorctl status 2>/dev/null || true
docker exec gewe ss -tlnp 2>/dev/null | grep -E '4600|2531' || true
echo "=== devicelibrary tail ==="
docker exec gewe tail -n 8 /root/gewe/base/log/devicelibrary.txt 2>/dev/null || true
echo "=== token + qr probe ==="
TOK=$(curl -sf -m 10 -X POST http://127.0.0.1:2531/v2/api/tools/getTokenId -H 'Content-Type: application/json' -d '{}')
echo "$TOK" | head -c 120
T=$(echo "$TOK" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',''))" 2>/dev/null || true)
if [ -n "$T" ]; then
  curl -sf -m 60 -X POST http://127.0.0.1:2531/v2/api/login/getLoginQrCode \
    -H "Content-Type: application/json" -H "X-GEWE-TOKEN: $T" \
    -d '{"appId":"","regionId":"330000","proxyIp":"","type":"ipad"}' | head -c 200
  echo
fi
