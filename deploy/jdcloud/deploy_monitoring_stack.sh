#!/bin/bash
# LiMa 京东云监控与轻量服务部署脚本
# 日期: 2026-06-09
# 目标: 117.72.118.95 (3.8GB 内存)

set -e

echo "======================================"
echo "LiMa 京东云监控栈部署"
echo "======================================"

# 创建工作目录
mkdir -p /opt/lima-monitoring/{prometheus,grafana,redis}
cd /opt/lima-monitoring

# 1. 创建 Prometheus 配置
cat > prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - /etc/prometheus/rules/*.yml

scrape_configs:
  # 阿里云主 VPS
  - job_name: 'lima-router'
    scheme: https
    metrics_path: /v1/ops/metrics/prometheus
    authorization:
      type: Bearer
      credentials: ${LIMA_METRICS_API_KEY}
    static_configs:
      - targets: ['chat.donglicao.com']
        labels:
          instance: 'aliyun-vps'
          service: 'lima-router'

  # 京东云本地服务
  - job_name: 'jdcloud-services'
    static_configs:
      - targets: ['localhost:9090']  # Prometheus 自身
        labels:
          instance: 'jdcloud-prometheus'
      - targets: ['localhost:6379']  # Redis
        labels:
          instance: 'jdcloud-redis'

  # Provider 健康探测
  - job_name: 'provider-probe'
    static_configs:
      - targets: ['localhost:9091']
        labels:
          instance: 'provider-probe'
EOF

# 1.5 创建告警规则目录与规则文件
mkdir -p prometheus/rules
cat > prometheus/rules/startup_alerts.yml << 'EOF'
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

# 2. 创建 Grafana 数据源配置
mkdir -p grafana/provisioning/{datasources,dashboards}
cat > grafana/provisioning/datasources/prometheus.yml << 'EOF'
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
EOF

# 3. 创建 Redis Sentinel 配置
cat > redis/sentinel.conf << 'EOF'
port 26379
sentinel monitor aliyun-redis 47.112.162.80 6379 2
sentinel down-after-milliseconds aliyun-redis 5000
sentinel parallel-syncs aliyun-redis 1
sentinel failover-timeout aliyun-redis 10000
EOF

# 4. 创建 Docker Compose 文件
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: lima-prometheus
    restart: always
    ports:
      - "9090:9090"
    environment:
      - LIMA_METRICS_API_KEY=${LIMA_METRICS_API_KEY}
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./prometheus/rules:/etc/prometheus/rules:ro
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=7d'
      - '--web.enable-lifecycle'
    mem_limit: 400m
    cpus: 0.5

  grafana:
    image: grafana/grafana:latest
    container_name: lima-grafana
    restart: always
    ports:
      - "3000:3000"
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - grafana-data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=Lima@2026
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_SERVER_ROOT_URL=http://117.72.118.95:3000
    mem_limit: 300m
    cpus: 0.3
    depends_on:
      - prometheus

  redis-sentinel:
    image: redis:7-alpine
    container_name: lima-redis-sentinel
    restart: always
    ports:
      - "26379:26379"
    volumes:
      - ./redis/sentinel.conf:/etc/redis/sentinel.conf:ro
    command: redis-sentinel /etc/redis/sentinel.conf
    mem_limit: 200m
    cpus: 0.2

  redis-exporter:
    image: oliver006/redis_exporter:latest
    container_name: lima-redis-exporter
    restart: always
    ports:
      - "9121:9121"
    environment:
      - REDIS_ADDR=47.112.162.80:6379
    mem_limit: 50m
    cpus: 0.1

volumes:
  prometheus-data:
  grafana-data:

networks:
  default:
    name: lima-monitoring
EOF

# 5. 创建 Provider Probe 服务
cat > probe_daemon.py << 'EOF'
#!/usr/bin/env python3
"""
LiMa Provider 健康探测守护进程
独立运行，定期探测后端健康度，结果回传阿里云 VPS
"""
import asyncio
import httpx
import logging
from datetime import datetime
from prometheus_client import start_http_server, Gauge, Counter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus 指标
probe_success = Counter('lima_probe_success_total', 'Successful probes', ['backend'])
probe_failure = Counter('lima_probe_failure_total', 'Failed probes', ['backend'])
probe_latency = Gauge('lima_probe_latency_ms', 'Probe latency in ms', ['backend'])

# 阿里云 VPS 地址
LIMA_VPS_URL = "http://47.112.162.80:8080"

# 待探测后端（从阿里云同步，这里写几个示例）
BACKENDS = [
    {"id": "groq_llama70b", "url": "https://api.groq.com/openai/v1/chat/completions"},
    {"id": "cerebras_gptoss", "url": "https://api.cerebras.ai/v1/chat/completions"},
    {"id": "scnet_ds_flash", "url": "https://scnetwork.tech/v1/chat/completions"},
]

async def probe_backend(backend):
    """探测单个后端"""
    backend_id = backend["id"]
    url = backend["url"]

    try:
        start = datetime.now()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json={
                    "model": "test",
                    "messages": [{"role": "user", "content": "1+1=?"}],
                    "max_tokens": 10
                }
            )
        latency = (datetime.now() - start).total_seconds() * 1000

        if resp.status_code < 500:
            probe_success.labels(backend=backend_id).inc()
            probe_latency.labels(backend=backend_id).set(latency)
            logger.info(f"✓ {backend_id}: {latency:.0f}ms")
            return {"backend": backend_id, "status": "healthy", "latency_ms": latency}
        else:
            probe_failure.labels(backend=backend_id).inc()
            logger.warning(f"✗ {backend_id}: HTTP {resp.status_code}")
            return {"backend": backend_id, "status": "unhealthy", "error": f"HTTP {resp.status_code}"}

    except Exception as e:
        probe_failure.labels(backend=backend_id).inc()
        logger.error(f"✗ {backend_id}: {type(e).__name__}")
        return {"backend": backend_id, "status": "dead", "error": str(e)}

async def report_to_vps(results):
    """回传结果到阿里云 VPS"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{LIMA_VPS_URL}/v1/ops/backends/probe-batch",
                json={"source": "jdcloud", "results": results},
                headers={"Authorization": "Bearer lima-local"}
            )
        logger.info(f"→ 上报 {len(results)} 条探测结果到 VPS")
    except Exception as e:
        logger.error(f"上报失败: {e}")

async def main():
    """主循环"""
    # 启动 Prometheus 指标服务器
    start_http_server(9091)
    logger.info("Prometheus 指标: http://localhost:9091/metrics")

    while True:
        logger.info("=" * 50)
        logger.info(f"开始探测 {len(BACKENDS)} 个后端...")

        tasks = [probe_backend(b) for b in BACKENDS]
        results = await asyncio.gather(*tasks)

        await report_to_vps(results)

        logger.info("等待 300 秒后下一轮探测...")
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main())
EOF

chmod +x probe_daemon.py

# 6. 创建 systemd 服务
cat > /etc/systemd/system/lima-probe.service << 'EOF'
[Unit]
Description=LiMa Provider Probe Daemon
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/lima-monitoring
ExecStart=/usr/bin/python3 /opt/lima-monitoring/probe_daemon.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 7. 安装 Python 依赖
pip3 install httpx prometheus-client -q

# 8. 启动服务
echo ""
echo "======================================"
echo "启动服务..."
echo "======================================"

# 启动 Docker 栈
docker compose up -d

# 启动 Probe 守护进程
systemctl daemon-reload
systemctl enable lima-probe
systemctl start lima-probe

# 等待服务就绪
sleep 5

# 9. 健康检查
echo ""
echo "======================================"
echo "健康检查"
echo "======================================"

check_service() {
    local name=$1
    local url=$2
    if curl -sf "$url" > /dev/null 2>&1; then
        echo "✓ $name: OK"
    else
        echo "✗ $name: FAILED"
    fi
}

check_service "Prometheus" "http://localhost:9090/-/healthy"
check_service "Grafana" "http://localhost:3000/api/health"
check_service "Redis Sentinel" "http://localhost:26379/ping" || echo "  (Redis Sentinel 需手动验证)"
check_service "Probe Metrics" "http://localhost:9091/metrics"

echo ""
echo "======================================"
echo "部署完成！"
echo "======================================"
echo ""
echo "访问地址："
echo "  Grafana:    http://117.72.118.95:3000"
echo "              用户名: admin"
echo "              密码:   Lima@2026"
echo ""
echo "  Prometheus: http://117.72.118.95:9090"
echo "  Probe 指标: http://117.72.118.95:9091/metrics"
echo ""
echo "服务状态："
echo "  docker compose ps"
echo "  systemctl status lima-probe"
echo ""
