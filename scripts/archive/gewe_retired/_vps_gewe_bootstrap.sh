#!/bin/bash
set -e
podman exec gewe systemctl start mysqld 2>/dev/null || true
sleep 10
podman exec gewe systemctl restart nginx 2>/dev/null || true
# supervisor-managed gewe app
podman exec gewe supervisorctl status 2>/dev/null || true
podman exec gewe supervisorctl restart all 2>/dev/null || true
for i in $(seq 1 30); do
  if curl -sf -m 5 -X POST http://127.0.0.1:2531/v2/api/tools/getTokenId -H 'Content-Type: application/json' -d '{}' >/tmp/gewe_token.json 2>/dev/null; then
    echo token_ready
    cat /tmp/gewe_token.json
    exit 0
  fi
  echo wait_$i
  sleep 5
done
echo token_timeout
exit 1
