# 阿里云 LiMa Prometheus 业务指标部署报告

**日期**: 2026-06-09
**部署目标**: 阿里云 VPS (47.112.162.80)
**状态**: ✅ 成功

## 一、部署内容

### 1. 新增文件
- `observability/prometheus_exporter.py` - 后台线程导出后端健康度 Gauge 指标

### 2. 修改文件
- `routes/request_tracking.py` - 在 `record_request()` 中添加 Prometheus 指标记录
- `server_lifespan.py` - 启动/停止 Prometheus 导出器线程

### 3. 配置变更
- 阿里云 VPS `.env` 文件添加 `LIMA_PROMETHEUS_METRICS=1`

## 二、导出的业务指标

### 2.1 Counter（计数器）
```prometheus
# 请求总数（按后端和状态分类）
lima_requests_total{backend="openai-gpt4", status="success"} 1234
lima_requests_total{backend="anthropic-claude", status="error"} 56

# 后端错误总数（按后端和错误类型分类）
lima_backend_errors_total{backend="groq_llama70b", error_type="timeout"} 12
lima_backend_errors_total{backend="deepseek_free", error_type="rate_limit"} 8

# 设备任务总数（按能力和状态分类）
lima_device_tasks_total{capability="code_generation", status="completed"} 567
lima_device_tasks_total{capability="debugging", status="failed"} 23
```

### 2.2 Histogram（直方图）
```prometheus
# 请求持续时间分布（毫秒）
lima_request_duration_ms_bucket{backend="openai-gpt4", le="250"} 890
lima_request_duration_ms_bucket{backend="openai-gpt4", le="1000"} 1234
lima_request_duration_ms_sum{backend="openai-gpt4"} 456789.0
lima_request_duration_ms_count{backend="openai-gpt4"} 1234

# 后端响应延迟分布（毫秒）
lima_backend_latency_ms_bucket{backend="anthropic-claude", le="500"} 678
lima_backend_latency_ms_bucket{backend="anthropic-claude", le="2500"} 890
lima_backend_latency_ms_sum{backend="anthropic-claude"} 234567.0
lima_backend_latency_ms_count{backend="anthropic-claude"} 890
```

### 2.3 Gauge（仪表）
```prometheus
# 后端健康状态（1=健康, 0.5=降级, 0=死亡）
lima_backend_health{backend="cfai_llama4", status="healthy"} 1.0
lima_backend_health{backend="cfai_qwen_coder", status="degraded"} 0.5
lima_backend_health{backend="groq_llama70b", status="suspicious"} 0.0
lima_backend_health{backend="aliyun_qwen3", status="dead"} 0.0

# 后端健康分数（0-1）
lima_backend_score{backend="longcat"} 0.98
lima_backend_score{backend="nvidia_nemotron"} 0.95
lima_backend_score{backend="chinamobile"} 0.92
lima_backend_score{backend="cfai_qwen_coder"} 0.45
```

## 三、部署步骤

### 3.1 文件上传
```bash
scp routes/request_tracking.py root@47.112.162.80:/opt/lima-router/routes/
scp observability/prometheus_exporter.py root@47.112.162.80:/opt/lima-router/observability/
scp server_lifespan.py root@47.112.162.80:/opt/lima-router/
```

### 3.2 环境配置
```bash
ssh root@47.112.162.80
cd /opt/lima-router
echo "LIMA_PROMETHEUS_METRICS=1" >> .env
```

### 3.3 服务重启
```bash
pkill -f 'uvicorn server:app'
cd /opt/lima-router
nohup /usr/local/bin/python3.10 -m uvicorn server:app --host 0.0.0.0 --port 8080 > /tmp/lima.log 2>&1 &
```

## 四、验证结果

### 4.1 端点测试
```bash
# 在 VPS 本地测试
curl -s -H 'Authorization: Bearer <YOUR_API_KEY>' \
  http://localhost:8080/v1/ops/metrics/prometheus | head -50
```

**结果**: ✅ 返回完整的 Prometheus 指标（包括 Python 运行时指标和 LiMa 业务指标）

### 4.2 业务指标验证
```bash
curl -s -H 'Authorization: Bearer <YOUR_API_KEY>' \
  http://localhost:8080/v1/ops/metrics/prometheus | grep '^lima_'
```

**结果**: ✅ 成功导出以下指标：
- `lima_backend_health` - 168 个后端的健康状态
- `lima_backend_score` - 168 个后端的分数
- 其他计数器和直方图指标将在有实际流量后出现

### 4.3 后端健康状态统计
从导出的指标中统计：
- **健康 (healthy)**: 10 个后端（值=1.0）
  - longcat, longcat_web, longcat_web_think, longcat_web_research
  - nvidia_nemotron, nvidia_llama70b, nvidia_qwen_coder, nvidia_llama4
  - chinamobile, cfai_llama4
- **降级 (degraded)**: 11 个后端（值=0.5）
  - cfai_qwen_coder, cfai_llama70b, scnet_qwen235b, ovh_deepseek
  - fireworks_llama405b, deepseek_free, cfai_deepseek_r1, cfai_mistral
  - ovh_llama70b, nvidia_mistral, scnet_ds_pro
- **可疑 (suspicious)**: 5 个后端（值=0.0）
  - groq_llama70b, groq_llama4, groq_qwen32b, groq_llama8b, dashscope_coding
- **死亡 (dead)**: 142 个后端（值=0.0）

## 五、京东云 Prometheus 集成

### 5.1 Scrape 配置
在京东云 Prometheus 配置文件中添加：

```yaml
scrape_configs:
  - job_name: 'lima-aliyun'
    scheme: https
    metrics_path: '/v1/ops/metrics/prometheus'
    authorization:
      credentials: '<YOUR_API_KEY>'
    static_configs:
      - targets: ['chat.donglicao.com']
        labels:
          environment: 'production'
          service: 'lima'
          provider: 'aliyun'
```

### 5.2 抓取验证
等待 30-60 秒后，在 Prometheus UI 中查询：
```promql
lima_backend_health{environment="production"}
```

### 5.3 Grafana 可视化面板
推荐创建以下面板：

#### 面板 1: 后端健康状态总览
```promql
sum(lima_backend_health) by (status)
```

#### 面板 2: 健康后端占比
```promql
sum(lima_backend_health > 0.9) / count(lima_backend_health) * 100
```

#### 面板 3: 请求成功率（按后端）
```promql
sum(rate(lima_requests_total{status="success"}[5m])) by (backend) /
sum(rate(lima_requests_total[5m])) by (backend) * 100
```

#### 面板 4: P95 响应延迟（按后端）
```promql
histogram_quantile(0.95, sum(rate(lima_backend_latency_ms_bucket[5m])) by (backend, le))
```

#### 面板 5: 错误率趋势
```promql
sum(rate(lima_backend_errors_total[5m])) by (backend, error_type)
```

## 六、告警规则建议

### 6.1 后端健康告警
```yaml
- alert: LiMaBackendDead
  expr: lima_backend_health{status="healthy"} < 0.1
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "LiMa 后端 {{ $labels.backend }} 已死亡"
    description: "后端健康值 {{ $value }}，持续 5 分钟"

- alert: LiMaBackendDegraded
  expr: lima_backend_health{status="degraded"} == 0.5
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "LiMa 后端 {{ $labels.backend }} 性能降级"
    description: "后端处于降级状态，持续 10 分钟"
```

### 6.2 响应延迟告警
```yaml
- alert: LiMaHighLatency
  expr: histogram_quantile(0.95, sum(rate(lima_backend_latency_ms_bucket[5m])) by (backend, le)) > 5000
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "LiMa 后端 {{ $labels.backend }} 延迟过高"
    description: "P95 延迟 {{ $value }}ms，超过 5000ms 阈值"
```

### 6.3 错误率告警
```yaml
- alert: LiMaHighErrorRate
  expr: sum(rate(lima_backend_errors_total[5m])) by (backend) > 10
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "LiMa 后端 {{ $labels.backend }} 错误率过高"
    description: "每秒错误数 {{ $value }}，持续 5 分钟"
```

## 七、技术亮点

1. **零侵入采集**: 在现有 `record_request()` 函数中添加 Prometheus 记录，无需修改业务逻辑
2. **后台导出**: 使用独立线程每 30 秒更新 Gauge 指标，避免阻塞主请求路径
3. **优雅降级**: 如果 `prometheus_client` 未安装，功能自动禁用，不影响主服务
4. **环境变量控制**: 通过 `LIMA_PROMETHEUS_METRICS=1` 开关，方便在不同环境启用/禁用

## 八、后续优化建议

1. **增加业务维度标签**:
   - 添加 `ide` 标签（Claude Code, Cursor, Windsurf 等）
   - 添加 `intent` 标签（code_generation, debugging, refactoring 等）
   - 添加 `region` 标签（国内/海外用户区分）

2. **新增指标**:
   - `lima_session_duration_seconds` - 会话持续时间
   - `lima_cache_hit_rate` - 语义缓存命中率
   - `lima_tokens_generated_total` - 生成的 token 总数

3. **性能优化**:
   - 考虑使用 `prometheus_client` 的 multiprocess mode 支持多进程部署
   - 对高基数标签（如 `session_id`）使用 exemplar 采样而非全量标签

## 九、文档链接

- Prometheus 指标端点: `https://chat.donglicao.com/v1/ops/metrics/prometheus`
- 指标命名规范: https://prometheus.io/docs/practices/naming/
- Histogram 最佳实践: https://prometheus.io/docs/practices/histograms/

---

**部署人员**: Claude Code
**审核状态**: 待人工验证京东云 Prometheus 采集
**下一步**: 在京东云 Prometheus 中配置 scrape job 并验证数据采集
