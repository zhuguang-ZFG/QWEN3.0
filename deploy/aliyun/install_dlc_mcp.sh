#!/bin/bash
# Install dlc-mcp systemd service on VPS.
# Prerequisites: dlc-drawing service already running, .env contains MCP_ENDPOINT.
# Usage: sudo bash install_dlc_mcp.sh

set -euo pipefail

SERVICE_FILE="/etc/systemd/system/dlc-mcp.service"
SOURCE_FILE="$(dirname "$0")/dlc-mcp.service"

if [ ! -f "$SOURCE_FILE" ]; then
    echo "ERROR: $SOURCE_FILE not found"
    exit 1
fi

# Check MCP_ENDPOINT in .env
if ! grep -q "^MCP_ENDPOINT=" /opt/lima-router/.env 2>/dev/null; then
    echo "WARNING: MCP_ENDPOINT not found in /opt/lima-router/.env"
    echo "  Add: MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=<JWT>"
    echo "  Get token from: https://xiaozhi.me → 智能体 → MCP 接入点"
fi

# Check DLC_API_URL in .env
if ! grep -q "^DLC_API_URL=" /opt/lima-router/.env 2>/dev/null; then
    echo "WARNING: DLC_API_URL not found in /opt/lima-router/.env"
    echo "  Add: DLC_API_URL=http://127.0.0.1:8080"
fi

echo "Installing dlc-mcp.service..."
cp "$SOURCE_FILE" "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable dlc-mcp
systemctl restart dlc-mcp

sleep 2
if systemctl is-active --quiet dlc-mcp; then
    echo "✓ dlc-mcp service is active"
else
    echo "✗ dlc-mcp service failed to start — check: journalctl -u dlc-mcp -n 20"
    exit 1
fi
