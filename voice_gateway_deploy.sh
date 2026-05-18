#!/usr/bin/env bash
set -euo pipefail

# Voice Gateway Deployment Script for LiMa AI
# Deploys voice_gateway.py as a systemd service on the target server

SERVICE_NAME="lima-voice"
INSTALL_DIR="/opt/lima-voice"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
NGINX_CONF="/etc/nginx/sites-available/chat.donglicao.com"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_FILE="${SCRIPT_DIR}/voice_gateway.py"

echo "=== LiMa Voice Gateway Deployment ==="

# 1. Install dependencies
echo "[1/5] Installing Python dependencies..."
pip3.10 install --quiet edge-tts fastapi uvicorn websockets httpx python-multipart

# 2. Create install directory and copy files
echo "[2/5] Copying files to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"
cp "${SOURCE_FILE}" "${INSTALL_DIR}/voice_gateway.py"
chmod 644 "${INSTALL_DIR}/voice_gateway.py"

# 3. Create systemd service
echo "[3/5] Creating systemd service..."
cat > "${SERVICE_FILE}" << 'EOF'
[Unit]
Description=LiMa Voice Gateway
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/lima-voice
ExecStart=/usr/bin/python3.10 /opt/lima-voice/voice_gateway.py
Restart=always
RestartSec=5
Environment=SILICONFLOW_API_KEY=
Environment=GROQ_API_KEY=
Environment=LIMA_ROUTER_URL=http://127.0.0.1:8090/v1/chat/completions

[Install]
WantedBy=multi-user.target
EOF

echo "    [!] Edit ${SERVICE_FILE} to set SILICONFLOW_API_KEY and GROQ_API_KEY"

# 4. Enable and start service
echo "[4/5] Enabling and starting service..."
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
systemctl restart "${SERVICE_NAME}.service"
sleep 2
systemctl status "${SERVICE_NAME}.service" --no-pager || true

# 5. Add nginx WebSocket proxy
echo "[5/5] Configuring nginx..."
if [ -f "${NGINX_CONF}" ]; then
    if ! grep -q "location /ws/voice" "${NGINX_CONF}"; then
        # Insert WebSocket proxy location before the last closing brace
        NGINX_BLOCK='
    # Voice Gateway WebSocket
    location /ws/voice {
        proxy_pass http://127.0.0.1:8091;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # Voice Gateway health check
    location /voice/health {
        proxy_pass http://127.0.0.1:8091/health;
    }
'
        # Insert before the last } in the file
        sed -i "\$i\\${NGINX_BLOCK}" "${NGINX_CONF}"
        nginx -t && systemctl reload nginx
        echo "    Nginx configured and reloaded."
    else
        echo "    Nginx location already exists, skipping."
    fi
else
    echo "    [!] Nginx config not found at ${NGINX_CONF}"
    echo "    Add manually:"
    echo "      location /ws/voice { proxy_pass http://127.0.0.1:8091; ... }"
fi

echo ""
echo "=== Deployment Complete ==="
echo "Service: systemctl status ${SERVICE_NAME}"
echo "Logs:    journalctl -u ${SERVICE_NAME} -f"
echo "Health:  curl http://127.0.0.1:8091/health"
