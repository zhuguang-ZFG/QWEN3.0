#!/bin/bash
docker exec gewe sh -c 'grep -r 4600 /root/gewe 2>/dev/null | head -15'
docker exec gewe sh -c 'find /root/gewe -name "*.yml" -o -name "*.yaml" -o -name "*.properties" 2>/dev/null | head -20'
docker exec gewe tail -n 12 /root/gewe/base/log/devicelibrary.txt 2>/dev/null
