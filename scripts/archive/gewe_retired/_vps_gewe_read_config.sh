#!/bin/bash
docker exec gewe cat /root/gewe/base/app.config 2>/dev/null || true
echo "---"
docker exec gewe head -n 50 /root/gewe/base/pact.log 2>/dev/null || true
