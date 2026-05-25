#!/bin/bash
set -e
echo "=== gewe status ==="
docker ps -a --filter name=gewe || podman ps -a --filter name=gewe
echo "=== ports ==="
ss -tlnp | grep -E '2531|2532' || true
echo "=== mysqld inside container ==="
podman exec gewe systemctl status mysqld --no-pager 2>&1 | head -25 || true
echo "=== try start mysqld ==="
podman exec gewe systemctl start mysqld 2>&1 || true
sleep 15
podman exec gewe systemctl status mysqld --no-pager 2>&1 | head -15 || true
echo "=== gewe process ==="
podman exec gewe ss -tlnp 2>/dev/null | head -20 || true
echo "=== token probe ==="
curl -s -m 10 -X POST http://127.0.0.1:2531/v2/api/tools/getTokenId -H 'Content-Type: application/json' -d '{}' || echo token_fail
