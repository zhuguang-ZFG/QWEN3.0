#!/bin/bash
podman exec gewe sh -c 'find /root/gewe -type f \( -name "*.yml" -o -name "*.yaml" -o -name "*.properties" -o -name "*.json" -o -name "*.ini" -o -name "*.conf" \) 2>/dev/null | head -80'
podman exec gewe sh -c 'grep -r "device\|token\|http\|api" /root/gewe/base/conf 2>/dev/null | head -40'
podman exec gewe sh -c 'ls -laR /root/gewe/base/conf 2>/dev/null | head -40'
podman exec gewe sh -c 'grep -r "scheme\|deviceApi\|DeviceApi\|apiUrl\|baseUrl" /root/gewe 2>/dev/null | head -30'
