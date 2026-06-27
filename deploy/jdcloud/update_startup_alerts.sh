#!/bin/bash
# 增量更新 LiMa 启动告警规则到京东云监控栈。
# 适用于已运行 deploy_monitoring_stack.sh / auto_deploy.sh / native_prometheus.txt 的节点。
# Prometheus 可能以 systemd 服务或 docker-compose 方式运行，脚本会自动检测。

set -e

INSTALL_DIR="/opt/lima-monitoring"
RULES_DIR="${INSTALL_DIR}/prometheus/rules"
PROM_YML="${INSTALL_DIR}/prometheus/prometheus.yml"

if [ ! -d "${INSTALL_DIR}" ]; then
    echo "ERROR: ${INSTALL_DIR} not found. Deploy Prometheus first."
    exit 1
fi

cd "${INSTALL_DIR}"

# 1. 确保规则目录存在
mkdir -p "${RULES_DIR}"

# 2. 写入启动告警规则
cat > "${RULES_DIR}/startup_alerts.yml" << 'EOF'
groups:
  - name: lima_startup
    rules:
      - alert: LiMaStartupPhaseSlow
        expr: |
          (
            lima_startup_phase_duration_ms_count
            -
            lima_startup_phase_duration_ms_bucket{le="5000.0"}
          ) > 0
        for: 0m
        labels:
          severity: warning
          service: lima-router
        annotations:
          summary: "Startup phase {{ $labels.phase }} took longer than 5s"
          description: >-
            At least one observation of startup phase {{ $labels.phase }}
            exceeded 5 seconds. Check /health startup.phases on the instance
            for the exact timing.

      - alert: LiMaStartupPhaseVerySlow
        expr: |
          (
            lima_startup_phase_duration_ms_count
            -
            lima_startup_phase_duration_ms_bucket{le="10000.0"}
          ) > 0
        for: 0m
        labels:
          severity: critical
          service: lima-router
        annotations:
          summary: "Startup phase {{ $labels.phase }} took longer than 10s"
          description: >-
            At least one observation of startup phase {{ $labels.phase }}
            exceeded 10 seconds. This is likely blocking readiness or
            warm-up; review /health startup.phases and instance logs.

      - alert: LiMaStartupNotReady
        expr: lima_startup_status != 1
        for: 2m
        labels:
          severity: critical
          service: lima-router
        annotations:
          summary: "LiMa is not ready"
          description: >-
            lima_startup_status has not been ready for more than 2 minutes.
            Current status: {{ $value }} (0=starting/error, 0.5=warming).
            Check /health/ready and /health on the instance.

      - alert: LiMaStartupError
        expr: lima_startup_status == 0
        for: 1m
        labels:
          severity: critical
          service: lima-router
        annotations:
          summary: "LiMa startup is in error or still starting"
          description: >-
            lima_startup_status is 0, indicating a critical startup phase
            failed or the service is still starting after 1 minute. Inspect
            journalctl -u lima-router and /health startup.errors.
EOF

# 3. 修补 prometheus.yml：添加/更新 rule_files（相对于 config file 目录）
python3 - <<'PY'
import re
path = "/opt/lima-monitoring/prometheus/prometheus.yml"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()
if "rule_files:" in text:
    text = re.sub(r"rule_files:\n\s+-\s+.*", "rule_files:\n  - rules/*.yml", text)
else:
    text = text.replace("scrape_configs:", "rule_files:\n  - rules/*.yml\n\nscrape_configs:")
with open(path, "w", encoding="utf-8") as f:
    f.write(text)
PY
echo "OK: rule_files set to rules/*.yml"

# 4. 检测运行方式并重载配置
if systemctl is-active --quiet prometheus 2>/dev/null; then
    echo "Detected systemd prometheus.service"
    systemctl restart prometheus
    echo "OK: prometheus.service restarted"
elif [ -f "docker-compose.yml" ] && docker compose ps prometheus >/dev/null 2>&1; then
    echo "Detected docker compose prometheus"
    # Ensure rules volume is mounted for docker-compose deployments
    if ! grep -q './prometheus/rules:/etc/prometheus/rules:ro' docker-compose.yml; then
        python3 - <<'PY'
path = "docker-compose.yml"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()
old = "      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro"
new = old + "\n      - ./prometheus/rules:/etc/prometheus/rules:ro"
if old in text and new not in text:
    text = text.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
PY
        echo "OK: added rules volume to docker-compose.yml"
    fi
    docker compose up -d
    docker compose restart prometheus
    echo "OK: prometheus container restarted"
else
    echo "WARN: cannot detect prometheus runtime; please restart manually"
fi

# 5. 验证
sleep 3
echo ""
echo "Verification:"
curl -sS "http://localhost:9090/-/healthy" && echo " prometheus healthy" || echo " prometheus health check failed"
curl -sS 'http://localhost:9090/api/v1/rules' | python3 -c "
import sys, json
d = json.load(sys.stdin)
groups = {g['name']: len(g['rules']) for g in d.get('data', {}).get('groups', [])}
print(f'rule groups: {groups}')
assert 'lima_startup' in groups, 'lima_startup group not loaded'
print('OK: lima_startup rule group loaded')
"
