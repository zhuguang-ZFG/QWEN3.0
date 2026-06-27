#!/usr/bin/env bash
set -euo pipefail

# Deploy the full LiMa Provider Probe platform to JD Cloud VPS.
# Installs: browser service, discovery scheduler, result push, systemd timers.
# Total steps: 7
#
# Usage: bash deploy/jdcloud/deploy_probe_platform.sh

echo "=== LiMa Provider Probe - Full Platform Deploy ==="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
INSTALL_DIR="/opt/lima-probe"

# 1. Create directory structure and service user
echo "[1/7] Creating directory structure and service user..."
mkdir -p "${INSTALL_DIR}/provider_probe/discovery"
mkdir -p "${INSTALL_DIR}/provider_probe/reverse"
mkdir -p "${INSTALL_DIR}/provider_probe/verify"
mkdir -p "${INSTALL_DIR}/provider_probe/integrate"
mkdir -p "${INSTALL_DIR}/data"
mkdir -p "${INSTALL_DIR}/scripts"

if ! id -u lima-probe &>/dev/null; then
    useradd --system --no-create-home --home-dir "${INSTALL_DIR}" lima-probe
fi
chown -R lima-probe:lima-probe "${INSTALL_DIR}/data"
# Create an empty env file for the ingress token. The operator must populate
# LIMA_PROBE_INGRESS_TOKEN before the push service is started.
touch "${INSTALL_DIR}/.probe-ingress.env"
chown lima-probe:lima-probe "${INSTALL_DIR}/.probe-ingress.env"
chmod 600 "${INSTALL_DIR}/.probe-ingress.env"

# 2. Copy Python modules
echo "[2/7] Copying Python modules..."
PROBE_SRC="${REPO_ROOT}/packages/provider-probe-offline/provider_probe"
cp -r "${PROBE_SRC}/"* "${INSTALL_DIR}/provider_probe/"
touch "${INSTALL_DIR}/provider_probe/__init__.py"
chown -R lima-probe:lima-probe "${INSTALL_DIR}/provider_probe"

# 3. Install Python dependencies
echo "[3/7] Installing Python dependencies..."
pip3 install --break-system-packages --quiet httpx fastapi uvicorn pydantic

# 4. Install Playwright browser (optional - skip if already installed)
echo "[4/7] Setting up browser service..."
if ! command -v playwright &>/dev/null; then
    pip3 install --break-system-packages --quiet playwright
    python3 -m playwright install chromium
fi
cp "${SCRIPT_DIR}/lima-probe-browser.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable lima-probe-browser.service
systemctl restart lima-probe-browser.service || true

# 5. Set up discovery scheduler
echo "[5/7] Setting up discovery scheduler..."
cp "${SCRIPT_DIR}/lima-probe.service" /etc/systemd/system/
cp "${SCRIPT_DIR}/lima-probe.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable lima-probe.timer
systemctl start lima-probe.timer

# 6. Set up result push to main VPS
echo "[6/7] Setting up result push to main VPS..."
cp "${SCRIPT_DIR}/push_probe_results.py" "${INSTALL_DIR}/scripts/"
cp "${SCRIPT_DIR}/push_probe_results_utils.py" "${INSTALL_DIR}/scripts/"
chown -R lima-probe:lima-probe "${INSTALL_DIR}/scripts"
chmod 755 "${INSTALL_DIR}/scripts"
chmod +x "${INSTALL_DIR}/scripts/push_probe_results.py"
cp "${SCRIPT_DIR}/lima-probe-push.service" /etc/systemd/system/
cp "${SCRIPT_DIR}/lima-probe-push.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable lima-probe-push.timer
systemctl start lima-probe-push.timer

# 7. Verify
echo "[7/7] Verifying deployment..."
sleep 2

echo ""
echo "=== Browser Service ==="
systemctl status lima-probe-browser.service --no-pager -l || true
echo ""
echo "=== Discovery Timer ==="
systemctl status lima-probe.timer --no-pager || true
echo ""
echo "=== Push Timer ==="
systemctl status lima-probe-push.timer --no-pager || true

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Services:"
echo "  Browser:     http://127.0.0.1:8092/health"
echo "  Discovery:   systemctl start lima-probe.service  (manual run)"
echo "  Timer:       systemctl status lima-probe.timer   (daily at random time)"
echo "  Push:        systemctl status lima-probe-push.timer  (every 5 min)"
echo ""
echo "Manual test:"
echo "  curl http://127.0.0.1:8092/health"
echo "  systemctl start lima-probe.service"
echo "  systemctl start lima-probe-push.service"
echo "  journalctl -u lima-probe-push.service -f"
