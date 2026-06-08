#!/usr/bin/env bash
set -euo pipefail

# Deploy the full LiMa Provider Probe platform to JD Cloud VPS.
# Installs: browser service, discovery scheduler, systemd timers.
#
# Usage: bash deploy/jdcloud/deploy_probe_platform.sh

echo "=== LiMa Provider Probe - Full Platform Deploy ==="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
INSTALL_DIR="/opt/lima-probe"

# 1. Create directory structure
echo "[1/6] Creating directory structure..."
mkdir -p "${INSTALL_DIR}/provider_probe/discovery"
mkdir -p "${INSTALL_DIR}/provider_probe/reverse"
mkdir -p "${INSTALL_DIR}/provider_probe/verify"
mkdir -p "${INSTALL_DIR}/provider_probe/integrate"
mkdir -p "${INSTALL_DIR}/data"

# 2. Copy Python modules
echo "[2/6] Copying Python modules..."
cp -r "${REPO_ROOT}/provider_probe/"* "${INSTALL_DIR}/provider_probe/"
touch "${INSTALL_DIR}/provider_probe/__init__.py"

# 3. Install Python dependencies
echo "[3/6] Installing Python dependencies..."
pip3 install --break-system-packages --quiet httpx fastapi uvicorn pydantic

# 4. Install Playwright browser (optional - skip if already installed)
echo "[4/6] Setting up browser service..."
if ! command -v playwright &>/dev/null; then
    pip3 install --break-system-packages --quiet playwright
    python3 -m playwright install chromium
fi
cp "${SCRIPT_DIR}/lima-probe-browser.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable lima-probe-browser.service
systemctl restart lima-probe-browser.service || true

# 5. Set up discovery scheduler
echo "[5/6] Setting up discovery scheduler..."
cp "${SCRIPT_DIR}/lima-probe.service" /etc/systemd/system/
cp "${SCRIPT_DIR}/lima-probe.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable lima-probe.timer
systemctl start lima-probe.timer

# 6. Verify
echo "[6/6] Verifying deployment..."
sleep 2

echo ""
echo "=== Browser Service ==="
systemctl status lima-probe-browser.service --no-pager -l || true
echo ""
echo "=== Discovery Timer ==="
systemctl status lima-probe.timer --no-pager || true

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Services:"
echo "  Browser:     http://127.0.0.1:8092/health"
echo "  Discovery:   systemctl start lima-probe.service  (manual run)"
echo "  Timer:       systemctl status lima-probe.timer   (daily at random time)"
echo ""
echo "Manual test:"
echo "  curl http://127.0.0.1:8092/health"
echo "  systemctl start lima-probe.service"
echo "  journalctl -u lima-probe.service -f"
