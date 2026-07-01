#!/usr/bin/env bash
# Install LiMa Router Pilot on Aliyun auxiliary node.
# Run this script on the target VPS as root.
set -euo pipefail

[[ $EUID -ne 0 ]] && { echo "Run as root"; exit 1; }

PILOT_DIR="/opt/lima-router-pilot"
SERVICE_NAME="lima-router-pilot.service"
USER_NAME="lima-pilot"
REPO_DIR="${PILOT_DIR}/repo"

# Absolute path to this script's directory, supports being called from repo copy.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { echo "==> $*"; }

log "Stopping legacy lima-router on this node to free :8080"
systemctl stop lima-router.service || true
systemctl disable lima-router.service || true

log "Creating pilot user"
if ! id -u "${USER_NAME}" &>/dev/null; then
    useradd --system --user-group --home-dir "${PILOT_DIR}" --create-home "${USER_NAME}"
fi

log "Creating directories"
mkdir -p "${PILOT_DIR}" "${REPO_DIR}"

log "Using repository at ${REPO_DIR}"
if [[ ! -f "${REPO_DIR}/server.py" ]]; then
    echo "ERROR: ${REPO_DIR}/server.py not found. Run this script after syncing the repo to ${REPO_DIR}." >&2
    exit 1
fi

log "Setting up Python virtual environment"
python3.10 -m venv "${PILOT_DIR}/venv"
"${PILOT_DIR}/venv/bin/pip" install --upgrade pip
"${PILOT_DIR}/venv/bin/pip" install -r "${REPO_DIR}/requirements_server.txt"

log "Creating .env from legacy lima-router (merge, not overwrite)"
ENV_FILE="${PILOT_DIR}/.env"
LEGACY_ENV="/opt/lima-router/.env"

if [[ -f "${LEGACY_ENV}" ]]; then
    TS=$(date +%Y%m%d_%H%M%S)
    cp "${LEGACY_ENV}" "${ENV_FILE}.merged.${TS}"
    cp "${LEGACY_ENV}" "${ENV_FILE}"
else
    echo "WARNING: ${LEGACY_ENV} not found; creating minimal template" >&2
    cat > "${ENV_FILE}" <<'EOF'
# LiMa Router Pilot — minimal template
LIMA_API_KEY=replace-me
LIMA_ADMIN_TOKEN=replace-me
EOF
fi

# Append auxiliary-node overrides (do not overwrite existing keys).
{
    echo ""
    echo "# --- Aliyun pilot auxiliary-node overrides ---"
    echo "LIMA_NODE_ROLE=free_backend_only"
    echo "LIMA_SESSION_MEMORY_ENABLED=0"
    echo "LIMA_DEVICE_GATEWAY_ENABLED=0"
    echo "LIMA_MQTT_CLIENT_ENABLED=0"
    echo "LIMA_CONTEXT_RETRIEVAL_ENABLED=0"
    echo "LIMA_PROMETHEUS_ENABLED=1"
    echo "LIMA_ALERT_EVALUATOR_ENABLED=0"
    echo "LIMA_STRUCTURED_LOGGING_ENABLED=1"
    echo "LIMA_DEVICE_MEMORY_STORE=memory"
    echo "LIMA_DEVICE_LEDGER_STORE=memory"
    echo "LIMA_DEVICE_TASK_STORE=memory"
    echo "LIMA_RUNTIME_ENV=production"
    echo "LIMA_ALLOW_ANONYMOUS=1"
} >> "${ENV_FILE}"

chmod 600 "${ENV_FILE}"

log "Installing systemd service"
cp "${REPO_DIR}/deploy/aliyun/${SERVICE_NAME}" "/etc/systemd/system/${SERVICE_NAME}"
chmod 644 "/etc/systemd/system/${SERVICE_NAME}"

log "Setting ownership"
chown -R "${USER_NAME}:${USER_NAME}" "${PILOT_DIR}"

log "Reloading systemd and enabling service"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

log "Starting service"
if systemctl is-active --quiet "${SERVICE_NAME}"; then
    systemctl restart "${SERVICE_NAME}"
else
    systemctl start "${SERVICE_NAME}"
fi

log "Waiting for service to become active"
sleep 2
for _ in {1..30}; do
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        break
    fi
    sleep 1
done

if ! systemctl is-active --quiet "${SERVICE_NAME}"; then
    echo "ERROR: Service ${SERVICE_NAME} is not active." >&2
    systemctl status --no-pager "${SERVICE_NAME}" >&2 || true
    exit 1
fi

log "Service status"
systemctl status --no-pager "${SERVICE_NAME}"

log "Health check"
if curl -sf http://127.0.0.1:8080/health >/dev/null; then
    log "Pilot /health OK"
else
    echo "ERROR: Pilot /health failed" >&2
    exit 1
fi

log "Installation complete"
