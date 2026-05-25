#!/bin/bash
podman exec gewe ls -la /root/gewe 2>/dev/null | head -15
podman exec gewe ls -la /root/temp 2>/dev/null | head -15
podman exec gewe sh -c 'find /root -maxdepth 5 \( -name "*.ini" -o -name "*.yaml" -o -name "*.yml" -o -name "*.json" -o -name "*.properties" -o -name "*.conf" \) 2>/dev/null | head -50'
podman exec gewe sh -c 'grep -r "protocol\|device\|token\|api" /root/gewe/base/conf 2>/dev/null | head -30 || true'
podman exec gewe sh -c 'ls -la /root/gewe/base/conf 2>/dev/null || ls -la /etc/gewe 2>/dev/null || true'
