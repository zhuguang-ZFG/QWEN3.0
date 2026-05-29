#!/bin/bash
# LiMa Telegram Bot 部署脚本
# 在 VPS 上运行: bash scripts/deploy_telegram.sh
# 运行前确保已设置环境变量（见下方提示）

set -e

echo "=== LiMa Telegram Bot 部署 ==="
echo ""

# 检查必要环境变量
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "ERROR: TELEGRAM_BOT_TOKEN 未设置"
    echo "请先运行: export TELEGRAM_BOT_TOKEN='你的token'"
    exit 1
fi

if [ -z "$TELEGRAM_CHAT_ID" ]; then
    echo "ERROR: TELEGRAM_CHAT_ID 未设置"
    echo "请先运行: export TELEGRAM_CHAT_ID='你的chat_id'"
    exit 1
fi

WEBHOOK_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(16))")
echo "生成 WEBHOOK_SECRET: $WEBHOOK_SECRET"

# 写入 systemd 环境文件
LIMA_ENV="/opt/lima-router/lima.env"
echo "写入环境变量到 $LIMA_ENV ..."

# 追加 Telegram 变量（如果不存在）
grep -q "TELEGRAM_BOT_TOKEN" "$LIMA_ENV" 2>/dev/null || \
    echo "TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN" >> "$LIMA_ENV"
grep -q "TELEGRAM_CHAT_ID" "$LIMA_ENV" 2>/dev/null || \
    echo "TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID" >> "$LIMA_ENV"
grep -q "TELEGRAM_WEBHOOK_SECRET" "$LIMA_ENV" 2>/dev/null || \
    echo "TELEGRAM_WEBHOOK_SECRET=$WEBHOOK_SECRET" >> "$LIMA_ENV"

echo "环境变量已写入"

# 上传 Telegram 模块
REMOTE_DIR="/opt/lima-router"
echo "复制 Telegram 模块..."
cp telegram_bot.py "$REMOTE_DIR/"
cp telegram_notify.py "$REMOTE_DIR/"
cp routes/telegram.py "$REMOTE_DIR/routes/"

echo "重启 lima-router..."
systemctl restart lima-router
sleep 2

# 验证服务启动
if systemctl is-active --quiet lima-router; then
    echo "lima-router 运行中"
else
    echo "ERROR: lima-router 启动失败"
    journalctl -u lima-router --no-pager -n 20
    exit 1
fi

# 注册 webhook
echo "注册 Telegram webhook..."
ADMIN_TOKEN=$(grep LIMA_ADMIN_TOKEN "$LIMA_ENV" | cut -d= -f2)
curl -s -X POST "http://localhost:8080/telegram/setup" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"url\":\"https://chat.donglicao.com/telegram/webhook\"}" \
    | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin),indent=2))"

echo ""
echo "=== 部署完成 ==="
echo "现在去 Telegram 给你的 Bot 发 /status 试试"
echo ""
echo "重要: 部署后请去 @BotFather 用 /revoke 重新生成 token"
echo "      然后更新 $LIMA_ENV 中的 TELEGRAM_BOT_TOKEN"
