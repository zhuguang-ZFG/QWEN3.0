#!/bin/bash
# NewAPI 监控配置脚本
# 用途：配置 healthchecks.io 健康监控
# 执行：ssh root@117.72.118.95，然后运行此脚本

set -euo pipefail

echo "=========================================="
echo "NewAPI 监控配置"
echo "=========================================="
echo ""

# 1. 创建监控脚本
echo "=== 步骤 1/3：创建健康检查脚本 ==="

cat > /opt/newapi/healthcheck.sh << 'EOF'
#!/bin/bash
set -euo pipefail

CHECK_TYPE=${1:-https}
CHECK_UUID=${2:-}

if [ -z "$CHECK_UUID" ]; then
    echo "用法: $0 <https|chat> <check_uuid>"
    exit 1
fi

case "$CHECK_TYPE" in
    https)
        # 检查公网 HTTPS 可达性
        if curl -sf https://api.donglicao.com/api/status > /dev/null 2>&1; then
            curl -fsS -m 10 --retry 3 "https://hc-ping.com/$CHECK_UUID" > /dev/null 2>&1
        else
            curl -fsS -m 10 --retry 3 "https://hc-ping.com/$CHECK_UUID/fail" > /dev/null 2>&1
        fi
        ;;
    chat)
        # 检查聊天 API 完整链路（需要测试 token）
        if [ -z "${NEWAPI_TEST_TOKEN:-}" ]; then
            echo "错误: 未设置 NEWAPI_TEST_TOKEN 环境变量"
            curl -fsS -m 10 --retry 3 "https://hc-ping.com/$CHECK_UUID/fail" > /dev/null 2>&1
            exit 1
        fi

        RESPONSE=$(curl -s -X POST https://api.donglicao.com/v1/chat/completions \
            -H "Authorization: Bearer $NEWAPI_TEST_TOKEN" \
            -H "Content-Type: application/json" \
            -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"ping"}]}' \
            --max-time 30)

        if echo "$RESPONSE" | grep -q '"choices"'; then
            curl -fsS -m 10 --retry 3 "https://hc-ping.com/$CHECK_UUID" > /dev/null 2>&1
        else
            curl -fsS -m 10 --retry 3 "https://hc-ping.com/$CHECK_UUID/fail" > /dev/null 2>&1
        fi
        ;;
    *)
        echo "错误: 未知检查类型 $CHECK_TYPE"
        exit 1
        ;;
esac
EOF

chmod +x /opt/newapi/healthcheck.sh
echo "✅ 健康检查脚本已创建: /opt/newapi/healthcheck.sh"

# 2. 配置 cron
echo ""
echo "=== 步骤 2/3：配置 cron 定时任务 ==="
echo ""
echo "⚠️  你需要先在 healthchecks.io 创建 2 个 check："
echo "   1. jdcloud-newapi-https (每 5 分钟)"
echo "   2. jdcloud-newapi-chat (每 30 分钟)"
echo ""
read -p "已创建 healthchecks.io check？(y/N): " HC_CREATED
if [[ ! "$HC_CREATED" =~ ^[Yy]$ ]]; then
    echo "请访问 https://healthchecks.io 创建 check，然后重新运行此脚本"
    exit 0
fi

echo ""
read -p "输入 HTTPS check 的 UUID: " HTTPS_UUID
read -p "输入 Chat check 的 UUID: " CHAT_UUID

# 验证 UUID 格式
if [[ ! "$HTTPS_UUID" =~ ^[a-f0-9-]{36}$ ]] || [[ ! "$CHAT_UUID" =~ ^[a-f0-9-]{36}$ ]]; then
    echo "❌ UUID 格式无效（应为 36 字符的 hex-dash 格式）"
    exit 1
fi

echo ""
read -p "输入测试用的 API Token（用于 chat 检查）: " TEST_TOKEN

# 创建环境变量文件
cat > /opt/newapi/.healthcheck.env << EOF
NEWAPI_TEST_TOKEN=$TEST_TOKEN
EOF
chmod 600 /opt/newapi/.healthcheck.env
echo "✅ 环境变量已保存: /opt/newapi/.healthcheck.env"

# 添加 cron
CRON_HTTPS="*/5 * * * * . /opt/newapi/.healthcheck.env && /opt/newapi/healthcheck.sh https $HTTPS_UUID >> /var/log/newapi-healthcheck.log 2>&1"
CRON_CHAT="*/30 * * * * . /opt/newapi/.healthcheck.env && /opt/newapi/healthcheck.sh chat $CHAT_UUID >> /var/log/newapi-healthcheck.log 2>&1"

(crontab -l 2>/dev/null | grep -v "newapi/healthcheck.sh"; echo "$CRON_HTTPS"; echo "$CRON_CHAT") | crontab -

echo "✅ Cron 任务已添加"

# 3. 测试
echo ""
echo "=== 步骤 3/3：测试健康检查 ==="
echo ""
read -p "立即测试 HTTPS 检查？(y/N): " TEST_HTTPS
if [[ "$TEST_HTTPS" =~ ^[Yy]$ ]]; then
    /opt/newapi/healthcheck.sh https $HTTPS_UUID
    echo "✅ HTTPS 检查已执行，查看 healthchecks.io 确认"
fi

echo ""
read -p "立即测试 Chat 检查？(y/N): " TEST_CHAT
if [[ "$TEST_CHAT" =~ ^[Yy]$ ]]; then
    export NEWAPI_TEST_TOKEN=$TEST_TOKEN
    /opt/newapi/healthcheck.sh chat $CHAT_UUID
    echo "✅ Chat 检查已执行，查看 healthchecks.io 确认"
fi

echo ""
echo "=========================================="
echo "监控配置完成！"
echo "=========================================="
echo ""
echo "验证："
echo "  crontab -l | grep healthcheck"
echo ""
echo "查看日志："
echo "  tail -f /var/log/newapi-healthcheck.log"
echo ""
