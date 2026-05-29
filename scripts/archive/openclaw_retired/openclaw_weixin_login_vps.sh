#!/bin/bash
# Run on VPS after lima-openclaw is active. Prints WeChat QR for openclaw-weixin.
set -euo pipefail
export OPENCLAW_STATE_DIR=/opt/lima-router/openclaw/state
export OPENCLAW_CONFIG_PATH=/opt/lima-router/openclaw/openclaw.json
export PATH="/root/.nvm/versions/node/v22.22.1/bin:${PATH}"
set -a && source /opt/lima-router/.env && set +a
unset TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID TELEGRAM_WEBHOOK_SECRET
exec openclaw channels login --channel openclaw-weixin
