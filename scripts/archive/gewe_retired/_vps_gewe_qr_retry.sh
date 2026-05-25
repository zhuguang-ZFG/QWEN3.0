#!/bin/bash
bash /opt/lima-router/_vps_gewe_bootstrap.sh 2>/dev/null || true
sleep 5
for i in $(seq 1 40); do
  TOK=$(curl -sf -m 10 -X POST http://127.0.0.1:2531/v2/api/tools/getTokenId -H 'Content-Type: application/json' -d '{}' 2>/dev/null)
  if [ -z "$TOK" ]; then
    echo wait_token_$i
    sleep 3
    continue
  fi
  T=$(echo "$TOK" | /usr/local/bin/python3.10 -c "import sys,json; print(json.load(sys.stdin).get('data',''))")
  QR=$(curl -sf -m 90 -X POST http://127.0.0.1:2531/v2/api/login/getLoginQrCode \
    -H "Content-Type: application/json" -H "X-GEWE-TOKEN: $T" \
    -d '{"appId":"","regionId":"330000","proxyIp":"","type":"ipad"}')
  echo "try_$i" "$QR" | head -c 300
  echo
  if echo "$QR" | grep -q '"ret":200'; then
    echo qr_success
    exit 0
  fi
  sleep 3
done
echo qr_give_up
exit 1
