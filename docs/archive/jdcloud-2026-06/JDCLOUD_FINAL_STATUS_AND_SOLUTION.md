# 京东云监控项目 - 最终总结与方案

## 部署状态 ✅

### 京东云 (117.72.118.95)
- ✅ Prometheus v2.45.0 已安装并运行
- ✅ 端口 9090 已开放（安全组配置完成）
- ✅ systemd 服务已启用（开机自启）
- ✅ 配置文件正确（带认证的 metrics 端点）
- ✅ 外网可访问：http://117.72.118.95:9090

### 阿里云 (47.112.162.80)
- ✅ LiMa Router 正常运行
- ✅ Prometheus metrics 端点已启用：`/v1/ops/metrics/prometheus`
- ✅ API Key 认证正常
- ✅ 本地测试通过：`curl http://localhost:8080/v1/ops/metrics/prometheus`

## 核心问题 ❌

**网络隔离**：京东云 → 阿里云不通

```
京东云测试：
curl http://47.112.162.80:8080
→ connection refused

诊断：
- ping 47.112.162.80：100% 丢包
- wget/curl 超时
- Prometheus scrape 失败："dial tcp connect: connection refused"
```

**原因分析**：
1. 阿里云 8080 端口未对外开放（仅监听内网）
2. 或者云服务商之间网络隔离
3. 需要公网 IP + 端口映射

## 解决方案

### 方案 A：开放阿里云 8080 公网访问 ⭐ 推荐

**步骤**：
1. 在阿里云控制台添加安全组规则：
   - 入站 TCP 8080
   - 源：117.72.118.95/32（仅允许京东云）

2. 验证：在京东云执行
   ```bash
   curl http://47.112.162.80:8080/health
   ```

3. 成功后 Prometheus 会自动开始采集

**优点**：
- 无需修改配置
- 延迟最低
- 配置简单

**安全性**：
- ✅ 限制源 IP（仅京东云可访问）
- ✅ API Key 认证
- ✅ 不影响现有服务

### 方案 B：使用公网域名 + HTTPS

如果 LiMa 有公网域名（如 `api.lima.example.com`）：

```yaml
scrape_configs:
  - job_name: 'lima-router'
    scheme: https
    metrics_path: '/v1/ops/metrics/prometheus'
    authorization:
      credentials: 'xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw'
    static_configs:
      - targets: ['api.lima.example.com:443']
```

### 方案 C：通过 VPN/隧道打通内网

复杂度高，暂不推荐。

### 方案 D：放弃跨云监控，京东云自监控

在京东云部署轻量服务并自监控：
- 仅监控京东云本地服务
- 放弃对阿里云的监控

## 推荐行动（方案 A）

### 1. 配置阿里云安全组

登录阿里云控制台 → ECS → 安全组：

```
规则方向：入方向
授权策略：允许
协议类型：自定义 TCP
端口范围：8080/8080
授权对象：117.72.118.95/32
描述：京东云 Prometheus 采集
```

### 2. 验证连通性

在京东云 SSH 执行：

```bash
# 测试连接
curl -v http://47.112.162.80:8080/health

# 测试 metrics（需认证）
curl -H "Authorization: Bearer xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw" \
  http://47.112.162.80:8080/v1/ops/metrics/prometheus | head -20
```

### 3. 确认 Prometheus 采集

等待 30 秒后：

```bash
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool | grep '"health"'
# 预期输出："health": "up"
```

### 4. 验证指标采集

```bash
curl -s 'http://localhost:9090/api/v1/query?query=lima_requests_total'
```

## 当前文件清单

| 文件 | 状态 |
|------|-----|
| 京东云 Prometheus 二进制 | ✅ `/opt/lima-monitoring/prometheus-bin/` |
| 京东云配置文件 | ✅ `/opt/lima-monitoring/prometheus/prometheus.yml` |
| 京东云 systemd 服务 | ✅ `/etc/systemd/system/prometheus.service` |
| 阿里云 metrics 端点 | ✅ `http://47.112.162.80:8080/v1/ops/metrics/prometheus` |
| 阿里云环境变量 | ✅ `LIMA_PROMETHEUS_METRICS=1` 已添加 |

## 指标说明

LiMa Router 导出的 Prometheus 指标：

```
# 系统指标
process_resident_memory_bytes    # 内存占用
process_cpu_seconds_total        # CPU 使用
process_open_fds                 # 打开文件数

# LiMa 业务指标
lima_requests_total              # 请求总数
lima_backend_errors_total        # 后端错误数
lima_device_tasks_total          # 设备任务数
```

## 访问地址

### Prometheus Web UI
- 外网：http://117.72.118.95:9090
- Targets：http://117.72.118.95:9090/targets
- Graph：http://117.72.118.95:9090/graph

### 示例查询

```promql
# 过去 5 分钟请求速率
rate(lima_requests_total[5m])

# 内存使用
process_resident_memory_bytes / 1024 / 1024

# CPU 使用率
rate(process_cpu_seconds_total[1m]) * 100
```

## 下一步

### 紧急（解决监控）
1. ⏳ 配置阿里云安全组开放 8080 端口
2. ⏳ 验证京东云可访问阿里云
3. ⏳ 确认 Prometheus 采集成功

### 短期（增强功能）
1. 部署 Grafana Dashboard
2. 配置告警规则
3. 添加更多监控目标

### 长期（优化架构）
1. 迁移到统一云服务商
2. 或部署 VPN 打通内网
3. 考虑 Prometheus 联邦集群

## 成本估算

| 项目 | 费用 |
|------|-----|
| 京东云 VPS (已有) | ¥0 |
| Prometheus (开源) | ¥0 |
| 网络流量 (采集) | ~¥0.01/天 |
| **总计** | **几乎免费** |

## 部署证据

完整部署过程见：
- `docs/JDCLOUD_PROMETHEUS_DEPLOYMENT_REPORT.md`
- `docs/JDCLOUD_DEPLOYMENT_BLOCKER.md`
- 本文件

部署脚本：
- `deploy/jdcloud/deploy_monitoring_stack.sh`
- `deploy/jdcloud/deploy_jd.py`
