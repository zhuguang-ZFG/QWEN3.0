#!/bin/bash
set -e
GEWE_DIR=/opt/gewechat
mkdir -p "$GEWE_DIR/data"
echo "=== stop old gewe ==="
docker stop gewe 2>/dev/null || podman stop gewe 2>/dev/null || true
docker rm gewe 2>/dev/null || podman rm gewe 2>/dev/null || true
echo "=== pull official gewe ==="
docker pull registry.cn-hangzhou.aliyuncs.com/gewe/gewe:latest
docker tag registry.cn-hangzhou.aliyuncs.com/gewe/gewe:latest gewe
echo "=== run official gewe ==="
docker run -itd -v "$GEWE_DIR/data:/root/temp" -p 2531:2531 -p 2532:2532 \
  --privileged=true --restart=always --name=gewe gewe /usr/sbin/init
echo "=== wait services ==="
sleep 25
ss -tlnp | grep -E '2531|2532' || true
curl -sf -X POST http://127.0.0.1:2531/v2/api/tools/getTokenId -H 'Content-Type: application/json' -d '{}' || true
echo done
