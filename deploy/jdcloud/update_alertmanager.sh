#!/bin/bash
# 在京东云监控栈部署/更新 Alertmanager，让 Prometheus 启动告警能够通知到真实渠道。
# 需要环境变量（至少设置一个真实通知渠道）：
#   DINGTALK_WEBHOOK_URL  - 钉钉机器人 webhook（接收 critical 告警）
#   WECHAT_WEBHOOK_URL    - 企业微信机器人 webhook（接收 lima-router 服务告警）
# 如果未设置，脚本会保留占位符 URL 并打印警告，便于本地/测试部署。
#
# 用法：
#   export DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxx
#   export WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
#   bash deploy/jdcloud/update_alertmanager.sh

set -e

INSTALL_DIR="/opt/lima-monitoring"
AM_DIR="${INSTALL_DIR}/alertmanager-bin"
CONFIG_DIR="${INSTALL_DIR}/alertmanager"
CONFIG_FILE="${CONFIG_DIR}/alertmanager.yml"
DATA_DIR="${INSTALL_DIR}/alertmanager-data"
SERVICE_FILE="/etc/systemd/system/alertmanager.service"

PROM_YML="${INSTALL_DIR}/prometheus/prometheus.yml"

ALERTMANAGER_VERSION="${ALERTMANAGER_VERSION:-0.25.0}"
ALERTMANAGER_TARBALL="alertmanager-${ALERTMANAGER_VERSION}.linux-amd64.tar.gz"
ALERTMANAGER_URL="https://mirrors.huaweicloud.com/prometheus/alertmanager/${ALERTMANAGER_VERSION}/${ALERTMANAGER_TARBALL}"

if [ ! -d "${INSTALL_DIR}" ]; then
    echo "ERROR: ${INSTALL_DIR} not found. Deploy Prometheus first."
    exit 1
fi

cd "${INSTALL_DIR}"

# 1. 确保目录存在
mkdir -p "${AM_DIR}" "${CONFIG_DIR}" "${DATA_DIR}"

# 2. 检查/下载 alertmanager 二进制
if [ ! -x "${AM_DIR}/alertmanager" ]; then
    echo "Alertmanager binary not found; installing ${ALERTMANAGER_VERSION}..."
    TMP_DIR=$(mktemp -d)
    cd "${TMP_DIR}"
    if [ -f "${INSTALL_DIR}/${ALERTMANAGER_TARBALL}" ]; then
        cp "${INSTALL_DIR}/${ALERTMANAGER_TARBALL}" "${ALERTMANAGER_TARBALL}"
        echo "OK: using local tarball ${INSTALL_DIR}/${ALERTMANAGER_TARBALL}"
    else
        echo "Downloading from ${ALERTMANAGER_URL}..."
        if ! wget -q "${ALERTMANAGER_URL}" -O "${ALERTMANAGER_TARBALL}"; then
            echo "ERROR: failed to download ${ALERTMANAGER_URL}"
            echo "Hint: upload ${ALERTMANAGER_TARBALL} to ${INSTALL_DIR}/ and re-run this script."
            exit 1
        fi
    fi
    tar xzf "${ALERTMANAGER_TARBALL}"
    mv "alertmanager-${ALERTMANAGER_VERSION}.linux-amd64"/* "${AM_DIR}/"
    cd "${INSTALL_DIR}"
    rm -rf "${TMP_DIR}"
    echo "OK: alertmanager binary installed to ${AM_DIR}"
else
    echo "OK: alertmanager binary already exists"
fi

# 3. 写入 alertmanager 配置并替换占位符
# 优先使用与脚本同目录的 alertmanager.yml，便于独立上传到目标节点执行。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${SCRIPT_DIR}/alertmanager.yml" ]; then
    SOURCE_CONFIG="${SCRIPT_DIR}/alertmanager.yml"
elif [ -f "${SCRIPT_DIR}/alertmanager/alertmanager.yml" ]; then
    SOURCE_CONFIG="${SCRIPT_DIR}/alertmanager/alertmanager.yml"
elif [ -f "deploy/jdcloud/alertmanager/alertmanager.yml" ]; then
    SOURCE_CONFIG="deploy/jdcloud/alertmanager/alertmanager.yml"
else
    echo "ERROR: alertmanager.yml source not found"
    exit 1
fi
cp "${SOURCE_CONFIG}" "${CONFIG_FILE}"

# Replace placeholders safely (handles '&' and other sed-special characters in URLs).
python3 - <<'PY'
import os

config_path = "/opt/lima-monitoring/alertmanager/alertmanager.yml"
replacements = [
    ("__DINGTALK_WEBHOOK_URL__", "DINGTALK_WEBHOOK_URL", "http://127.0.0.1:9/dingtalk-placeholder"),
    ("__WECHAT_WEBHOOK_URL__", "WECHAT_WEBHOOK_URL", "http://127.0.0.1:9/wechat-placeholder"),
]

with open(config_path, "r", encoding="utf-8") as f:
    text = f.read()

for placeholder, env_var, default in replacements:
    value = os.environ.get(env_var, default)
    text = text.replace(placeholder, value)
    if value == default:
        print(f"WARN: {env_var} not set; alerts will go to placeholder URL")
    else:
        print(f"OK: configured {env_var}")

with open(config_path, "w", encoding="utf-8") as f:
    f.write(text)
PY

# 4. 创建/更新 systemd service
cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=Alertmanager for LiMa
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=${AM_DIR}/alertmanager --config.file=${CONFIG_FILE} --storage.path=${DATA_DIR} --web.listen-address=0.0.0.0:9093
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable alertmanager

# 5. 确保 Prometheus 指向 alertmanager
python3 - <<'PY'
import re
path = "/opt/lima-monitoring/prometheus/prometheus.yml"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

alerting_block = """alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - 127.0.0.1:9093
"""

if "alerting:" not in text:
    text = alerting_block + "\n" + text
    print("OK: added alerting block to prometheus.yml")
elif "127.0.0.1:9093" not in text:
    # Replace existing alerting block target
    text = re.sub(
        r"alerting:\s*\n\s*alertmanagers:\s*\n\s*- static_configs:\s*\n\s*- targets:\s*\n\s*- .*",
        "alerting:\n  alertmanagers:\n    - static_configs:\n        - targets:\n            - 127.0.0.1:9093",
        text,
    )
    print("OK: updated alerting target to 127.0.0.1:9093")
else:
    print("OK: alerting target already set to 127.0.0.1:9093")

with open(path, "w", encoding="utf-8") as f:
    f.write(text)
PY

# 6. 重启服务
systemctl restart alertmanager
sleep 2

if systemctl is-active --quiet alertmanager; then
    echo "OK: alertmanager.service is active"
else
    echo "ERROR: alertmanager.service failed to start"
    systemctl status alertmanager --no-pager -l
    exit 1
fi

# 7. 重启 Prometheus 以加载 alerting 配置更新
if systemctl is-active --quiet prometheus 2>/dev/null; then
    systemctl restart prometheus
    echo "OK: prometheus.service restarted"
fi

# 8. 验证
sleep 3
echo ""
echo "Verification:"
curl -sS "http://localhost:9093/-/healthy" && echo " alertmanager healthy" || echo " alertmanager health check failed"

# Check Prometheus alertmanager targets
python3 - <<'PY'
import sys, json, urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:9090/api/v1/alertmanagers") as resp:
        data = json.load(resp)
    active = data.get("data", {}).get("activeAlertmanagers", [])
    urls = [am.get("url", "") for am in active]
    print(f"Prometheus alertmanagers: {urls}")
    if any("9093" in u for u in urls):
        print("OK: Prometheus sees alertmanager on :9093")
    else:
        print("WARN: Prometheus does not report alertmanager on :9093")
except Exception as exc:
    print(f"WARN: could not query Prometheus alertmanagers: {exc}")
PY

PUBLIC_IP="${PUBLIC_IP:-117.72.118.95}"
echo ""
echo "=== Alertmanager deployed at http://${PUBLIC_IP}:9093 ==="
echo "Remember to set real DINGTALK_WEBHOOK_URL / WECHAT_WEBHOOK_URL and re-run this script."
