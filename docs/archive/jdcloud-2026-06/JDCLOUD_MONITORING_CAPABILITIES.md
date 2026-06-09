# 京东云监控能力增强方案

## 当前状态（2026-06-09）

### 已部署
- ✅ Prometheus 2.45.0（二进制方式）
  - 端口：9090
  - 配置：`/opt/lima-monitoring/prometheus/prometheus.yml`
  - 采集目标：阿里云 VPS (`chat.donglicao.com`)
  - 健康状态：`up`
  - 采集间隔：30s

- ✅ 轻量级监控面板 (`/opt/lima-monitoring/monitor.py`)
  - Python 脚本，查询 Prometheus API
  - 显示核心指标（健康状态、请求量、延迟、错误率）

### 问题发现
1. **Grafana 部署失败**：Docker Hub 和官方源均无法访问（网络超时）
2. **业务指标缺失**：阿里云 VPS 仅暴露基础进程指标（CPU、内存、GC），缺少：
   - `lima_requests_total`（请求总数）
   - `lima_backend_health`（后端健康度）
   - `lima_request_duration_seconds`（请求延迟）
   - 其他业务级指标

## 京东云可部署的增强服务

### 1. Alertmanager（告警管理）✨ 推荐

**能力**：
- 基于 Prometheus 指标的告警规则
- 告警聚合、去重、静默
- 多通道通知（邮件、Webhook、企业微信、钉钉）

**部署方式**：
```bash
# 二进制安装（避免 Docker 网络问题）
wget https://github.com/prometheus/alertmanager/releases/download/v0.26.0/alertmanager-0.26.0.linux-amd64.tar.gz
tar -xzf alertmanager-0.26.0.linux-amd64.tar.gz
mv alertmanager-0.26.0.linux-amd64 /opt/lima-monitoring/alertmanager
```

**告警规则示例**：
```yaml
groups:
  - name: lima_alerts
    interval: 1m
    rules:
      - alert: LiMaVPSDown
        expr: up{job="lima-router"} == 0
        for: 2m
        annotations:
          summary: "阿里云 VPS 不可达"

      - alert: HighErrorRate
        expr: rate(lima_requests_total{status="error"}[5m]) > 0.1
        for: 3m
        annotations:
          summary: "错误率超过 10%"
```

**价值**：
- 自动监控阿里云 VPS 可用性
- 及时发现后端故障、高错误率
- 减少人工巡检成本

---

### 2. Node Exporter（系统指标采集）

**能力**：
- 采集 **京东云本身** 的系统指标（CPU、内存、磁盘、网络）
- 补充 Prometheus 监控盲区

**部署方式**：
```bash
wget https://github.com/prometheus/node_exporter/releases/download/v1.7.0/node_exporter-1.7.0.linux-amd64.tar.gz
tar -xzf node_exporter-1.7.0.linux-amd64.tar.gz
cd node_exporter-1.7.0.linux-amd64
./node_exporter &
```

**Prometheus 配置**：
```yaml
scrape_configs:
  - job_name: 'jdcloud-node'
    static_configs:
      - targets: ['localhost:9100']
        labels:
          instance: 'jdcloud'
          environment: 'production'
```

**价值**：
- 监控京东云自身资源使用情况
- 对比阿里云和京东云性能差异
- 预警磁盘满、内存不足等问题

---

### 3. Blackbox Exporter（端点探测）

**能力**：
- HTTP/HTTPS/TCP/ICMP 探测
- 检测阿里云 VPS 各端点可用性
- 测量响应时间、SSL 证书有效期

**部署方式**：
```bash
wget https://github.com/prometheus/blackbox_exporter/releases/download/v0.24.0/blackbox_exporter-0.24.0.linux-amd64.tar.gz
tar -xzf blackbox_exporter-0.24.0.linux-amd64.tar.gz
cd blackbox_exporter-0.24.0.linux-amd64
./blackbox_exporter &
```

**探测配置**：
```yaml
# Prometheus 配置
scrape_configs:
  - job_name: 'blackbox-http'
    metrics_path: /probe
    params:
      module: [http_2xx]
    static_configs:
      - targets:
          - https://chat.donglicao.com/v1/health
          - https://chat.donglicao.com/v1/ops/metrics/prometheus
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - target_label: __address__
        replacement: localhost:9115
```

**价值**：
- 从京东云视角探测阿里云可达性
- 检测 HTTPS 证书过期（提前预警）
- 多地域可用性验证

---

### 4. Loki + Promtail（日志聚合）

**能力**：
- 采集阿里云 VPS 的 LiMa 日志
- 结构化查询、关联 Prometheus 指标
- 轻量级替代 ELK

**部署方式**：
```bash
# Loki（日志存储引擎）
wget https://github.com/grafana/loki/releases/download/v2.9.4/loki-linux-amd64.zip
unzip loki-linux-amd64.zip
mv loki-linux-amd64 /opt/lima-monitoring/loki/loki

# Promtail（日志收集器，部署在阿里云 VPS）
# 通过 SSH 推送到阿里云
```

**价值**：
- 集中查看阿里云 LiMa 日志
- 快速定位错误堆栈
- 关联指标和日志（如：错误率飙升时查看对应日志）

---

### 5. 自定义 LiMa 业务指标导出器

**问题**：
- 阿里云 VPS 当前只暴露基础进程指标
- 缺少 `lima_requests_total`、`lima_backend_health` 等业务指标

**解决方案**：
在阿里云 VPS 的 LiMa 后端添加 Prometheus 客户端库：

```python
# routes/ops_metrics.py（阿里云 VPS）
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# 定义业务指标
requests_total = Counter(
    'lima_requests_total',
    'Total LiMa requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'lima_request_duration_seconds',
    'Request latency',
    ['endpoint']
)

backend_health = Gauge(
    'lima_backend_health',
    'Backend health score (0-1)',
    ['backend']
)

@app.get("/v1/ops/metrics/prometheus")
async def prometheus_metrics():
    return Response(content=generate_latest(), media_type="text/plain")
```

**价值**：
- 直接暴露 LiMa 核心业务指标
- 无需额外 exporter
- 与代码紧密集成

---

## 推荐部署优先级

### P0（立即部署）
1. **自定义业务指标导出器**（修改阿里云 VPS LiMa 后端）
   - 暴露 `lima_requests_total`、`lima_backend_health`、请求延迟
   - 让现有 Prometheus 立即可用

2. **Node Exporter**（京东云）
   - 监控京东云自身健康状态
   - 部署简单（单个二进制文件）

### P1（本周内）
3. **Alertmanager**（京东云）
   - 配置告警规则（VPS Down、高错误率）
   - 集成 Webhook 通知（可接入企业微信/钉钉）

4. **Blackbox Exporter**（京东云）
   - 多端点探测（Health、Metrics、Chat API）
   - SSL 证书监控

### P2（后续优化）
5. **Loki + Promtail**（日志聚合）
   - 需要在阿里云部署 Promtail
   - 涉及跨 VPS 日志传输

---

## 内网互通场景

由于京东云和阿里云 **内网已互通**，可以实现：

### 场景 1：双向监控
- 京东云 Prometheus → 阿里云 LiMa（已实现）
- 阿里云 Prometheus → 京东云服务（可选）

### 场景 2：高可用部署
- 阿里云：主 LiMa 实例
- 京东云：备用 LiMa 实例 + Prometheus + Alertmanager
- 当阿里云不可达时，自动切换到京东云

### 场景 3：日志和指标统一
- 京东云作为「监控中心」
- 采集阿里云、京东云、魔搭社区的所有指标和日志

---

## 下一步行动

1. **修改阿里云 LiMa 后端**：添加 `prometheus_client` 库，暴露业务指标
2. **部署 Node Exporter**：监控京东云自身
3. **配置 Alertmanager**：自动告警
4. **验证监控面板**：运行 `python3 /opt/lima-monitoring/monitor.py` 确认新指标可见

---

## 附录：当前网络拓扑

```
┌─────────────────┐          ┌─────────────────┐
│   阿里云 VPS    │◄─────────┤   京东云 VPS    │
│ chat.donglicao  │  内网互通 │  117.72.118.95  │
│                 │          │                 │
│ - LiMa 后端     │          │ - Prometheus    │
│ - /v1/ops/metrics│         │ - Node Exporter │
│ - 端口 443      │          │ - Alertmanager  │
└─────────────────┘          └─────────────────┘
        ▲                            │
        │                            │
        └────────────────────────────┘
          每 30s 采集指标
```
