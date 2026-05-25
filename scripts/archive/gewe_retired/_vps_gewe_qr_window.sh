#!/bin/bash
# Catch brief window when pact binds :4600
for round in $(seq 1 60); do
  docker exec gewe supervisorctl restart pact 2>/dev/null || true
  for w in $(seq 1 25); do
    if docker exec gewe ss -tlnp 2>/dev/null | grep -q ':4600'; then
      echo "4600_up round=$round wait=${w}s"
      TOK=$(curl -sf -m 8 -X POST http://127.0.0.1:2531/v2/api/tools/getTokenId -H 'Content-Type: application/json' -d '{}')
      T=$(echo "$TOK" | /usr/local/bin/python3.10 -c "import sys,json; print(json.load(sys.stdin).get('data',''))" 2>/dev/null)
      QR=$(curl -sf -m 60 -X POST http://127.0.0.1:2531/v2/api/login/getLoginQrCode \
        -H "Content-Type: application/json" -H "X-GEWE-TOKEN: $T" \
        -d '{"appId":"","regionId":"330000","proxyIp":"","type":"ipad"}')
      echo "$QR" | head -c 200
      echo
      if echo "$QR" | grep -q '"ret":200'; then
        echo qr_window_ok
        exit 0
      fi
    fi
    sleep 1
  done
  sleep 2
done
echo qr_window_fail
exit 1
