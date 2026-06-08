#!/usr/bin/env bash
set -euo pipefail

# Install Playwright + Chromium for LiMa Provider Probe browser service.
# Target: JD Cloud VPS (Ubuntu/Debian)

echo "=== LiMa Probe: Playwright + Browser Service Installer ==="

# 1. System dependencies for Chromium
echo "[1/4] Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq \
    libnss3 libnspr4 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 \
    fonts-liberation fonts-noto-color-emoji

# 2. Install Python packages
echo "[2/4] Installing Python packages..."
pip3 install --break-system-packages --quiet playwright fastapi uvicorn pydantic httpx

# 3. Install Chromium (Playwright-managed)
echo "[3/4] Installing Chromium browser..."
python3 -m playwright install chromium

# 4. Create install dir and set up systemd
echo "[4/4] Setting up systemd service..."
INSTALL_DIR="/opt/lima-probe"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

mkdir -p "${INSTALL_DIR}"
cp "${REPO_ROOT}/provider_probe/browser_service.py" "${INSTALL_DIR}/browser_service.py"
cp "${SCRIPT_DIR}/lima-probe-browser.service" /etc/systemd/system/lima-probe-browser.service

systemctl daemon-reload
systemctl enable lima-probe-browser.service
systemctl restart lima-probe-browser.service
sleep 2
systemctl status lima-probe-browser.service --no-pager || true

echo ""
echo "=== Install Complete ==="
echo "Service:  systemctl status lima-probe-browser"
echo "Health:   curl http://127.0.0.1:8092/health"
echo "Test:     curl -X POST http://127.0.0.1:8092/render -H 'Content-Type: application/json' -d '{\"url\":\"https://example.com\"}'"
