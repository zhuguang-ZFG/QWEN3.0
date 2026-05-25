#!/bin/bash
set -e
echo "=== pact log ==="
docker exec gewe tail -n 40 /root/gewe/base/pact.log 2>/dev/null || true
echo "=== long log ==="
docker exec gewe tail -n 20 /root/gewe/base/long.log 2>/dev/null || true
echo "=== listen 4600 ==="
docker exec gewe ss -tlnp 2>/dev/null | grep 4600 || echo "no_4600"
echo "=== restart pact only, wait ==="
docker exec gewe supervisorctl restart pact 2>/dev/null || true
for w in $(seq 1 30); do
  if docker exec gewe ss -tlnp 2>/dev/null | grep -q 4600; then
    echo "port_4600_up after ${w}s"
    break
  fi
  sleep 2
done
docker exec gewe ss -tlnp 2>/dev/null | grep -E '4600|2531' || true
echo "=== curl createapp inside container ==="
docker exec gewe curl -sf -m 5 http://127.0.0.1:4600/ 2>&1 | head -c 100 || echo curl_4600_fail
TOK=$(curl -sf -m 10 -X POST http://127.0.0.1:2531/v2/api/tools/getTokenId -H 'Content-Type: application/json' -d '{}')
T=$(echo "$TOK" | /usr/local/bin/python3.10 -c "import sys,json; print(json.load(sys.stdin).get('data',''))" 2>/dev/null)
QR=$(curl -sf -m 90 -X POST http://127.0.0.1:2531/v2/api/login/getLoginQrCode \
  -H "Content-Type: application/json" -H "X-GEWE-TOKEN: $T" \
  -d '{"appId":"","regionId":"330000","proxyIp":"","type":"ipad"}')
echo "$QR" | head -c 250
echo
echo "$QR" | grep -q '"ret":200' && echo pact_fix_qr_ok
