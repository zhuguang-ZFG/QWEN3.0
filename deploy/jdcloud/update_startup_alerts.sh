#!/bin/bash
# 增量更新 LiMa 启动告警规则到京东云监控栈。
# 适用于已运行 deploy_monitoring_stack.sh 的节点。
# 需要环境变量 LIMA_METRICS_API_KEY（用于 Prometheus 抓取认证）。

set -e

INSTALL_DIR="/opt/lima-monitoring"
RULES_DIR="${INSTALL_DIR}/prometheus/rules"
PROM_YML="${INSTALL_DIR}/prometheus/prometheus.yml"
COMPOSE_FILE="${INSTALL_DIR}/docker-compose.yml"

if [ ! -d "${INSTALL_DIR}" ]; then
    echo "ERROR: ${INSTALL_DIR} not found. Run deploy_monitoring_stack.sh first."
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

# 3. 修补 prometheus.yml：添加 rule_files（如果不存在）
if ! grep -q '^rule_files:' "${PROM_YML}"; then
    # 在 global 块后插入 rule_files
    awk '1; /^global:/ { found=1 } found && /^$/ && !done { print ""; print "rule_files:"; print "  - /etc/prometheus/rules/*.yml"; done=1 }' "${PROM_YML}" > "${PROM_YML}.tmp" && mv "${PROM_YML}.tmp" "${PROM_YML}"
    echo "OK: added rule_files to prometheus.yml"
else
    echo "OK: rule_files already present"
fi

# 4. 修补 docker-compose.yml：挂载 rules 目录并传入 API key
if ! grep -q './prometheus/rules:/etc/prometheus/rules:ro' "${COMPOSE_FILE}"; then
    sed -i 's|./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro|&\n      - ./prometheus/rules:/etc/prometheus/rules:ro|' "${COMPOSE_FILE}"
    echo "OK: added rules volume to docker-compose.yml"
else
    echo "OK: rules volume already present"
fi

if ! grep -q 'LIMA_METRICS_API_KEY' "${COMPOSE_FILE}"; then
    sed -i '/image: prom\/prometheus:latest/a\    environment:\n      - LIMA_METRICS_API_KEY=${LIMA_METRICS_API_KEY}' "${COMPOSE_FILE}"
    echo "OK: added LIMA_METRICS_API_KEY env to docker-compose.yml"
else
    echo "OK: LIMA_METRICS_API_KEY env already present"
fi

# 5. 重新加载 Prometheus 配置
echo "Reloading Prometheus..."
docker compose up -d
if curl -sf -X POST "http://localhost:9090/-/reload" > /dev/null 2>&1; then
    echo "OK: Prometheus config reloaded"
else
    echo "WARN: Prometheus reload API failed; restarting container..."
    docker compose restart prometheus
fi

# 6. 验证
sleep 3
echo ""
echo "Verification:"
curl -sS "http://localhost:9090/api/v1/rules" | grep -o '"name":"lima_startup"' && echo "OK: lima_startup rule group loaded" || echo "WARN: lima_startup rule group not found"
