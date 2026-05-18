#!/bin/bash
# LiMa 服务健康检查脚本
# 部署到云端 cron: */5 * * * * /opt/lima-monitor/health_check.sh

LOG="/var/log/lima-monitor.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# 检查 one-api
ONEAPI_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:3001/api/status)

# 检查 frp 隧道（通过隧道访问本地 LiMa 服务）
FRP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://127.0.0.1:8088/v1/models)

# 记录日志
echo "[$TIMESTAMP] one-api=$ONEAPI_STATUS frp_tunnel=$FRP_STATUS" >> $LOG

# 告警逻辑
ALERT=""
if [ "$ONEAPI_STATUS" != "200" ]; then
    ALERT="${ALERT}one-api DOWN (HTTP $ONEAPI_STATUS); "
fi
if [ "$FRP_STATUS" != "200" ]; then
    ALERT="${ALERT}frp tunnel DOWN (HTTP $FRP_STATUS); "
fi

if [ -n "$ALERT" ]; then
    echo "[$TIMESTAMP] ALERT: $ALERT" >> $LOG
    # TODO: 接入通知渠道（企业微信/钉钉 webhook）
    # curl -s -X POST "$WEBHOOK_URL" -H 'Content-Type: application/json' \
    #   -d "{\"msgtype\":\"text\",\"text\":{\"content\":\"[LiMa] $ALERT\"}}"
fi

# 日志轮转：保留 7 天
find /var/log/ -name "lima-monitor.log.*" -mtime +7 -delete 2>/dev/null
