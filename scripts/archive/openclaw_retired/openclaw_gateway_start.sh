#!/bin/bash
# LiMa VPS: minimal OpenClaw gateway (WeChat + LiMa brain only).
set -euo pipefail
set -a
# shellcheck source=/dev/null
source /opt/lima-router/.env
set +a
unset TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID TELEGRAM_WEBHOOK_SECRET
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=384}"
export OPENCLAW_STATE_DIR=/opt/lima-router/openclaw/state
export OPENCLAW_CONFIG_PATH=/opt/lima-router/openclaw/openclaw.json
export PATH="/root/.nvm/versions/node/v22.22.1/bin:${PATH}"
exec openclaw gateway run --bind loopback --port 18789
