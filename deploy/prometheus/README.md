# LiMa Prometheus 告警规则

本目录存放 LiMa 的 Prometheus 告警规则与示例配置。

## 文件说明

| 文件 | 用途 |
|---|---|
| `backend_retirement_alerts.yml` | 后端退役事件告警（M3）。 |
| `startup_alerts.yml` | 启动阶段耗时与 readiness 告警（G6）。 |
| `prometheus.yml` | 自托管 Prometheus 示例配置，抓取 `https://chat.donglicao.com/v1/ops/metrics/prometheus`。 |

## 前置条件

1. 服务启动时设置 `LIMA_PROMETHEUS_METRICS=1`。
2. 安装 `prometheus_client`（已在 `requirements_server.txt`）。
3. 抓取端点需要有效的 LiMa private API key（`authorization: Bearer <key>`）。

## 告警规则

### 启动慢

- `LiMaStartupPhaseSlow`：任一启动阶段耗时超过 5 秒（warning）。
- `LiMaStartupPhaseVerySlow`：任一启动阶段耗时超过 10 秒（critical）。

规则通过比较 histogram 的 `+Inf` count 与 `le="5000.0"` / `le="10000.0"` bucket 来检测稀疏的启动事件。

### 未就绪 / 启动错误

- `LiMaStartupNotReady`：`lima_startup_status != 1` 持续 2 分钟以上（critical）。
- `LiMaStartupError`：`lima_startup_status == 0` 持续 1 分钟以上（critical）。

## 部署方式

将规则文件挂载到 Prometheus 的 `rule_files` 路径：

```yaml
rule_files:
  - /etc/prometheus/rules/*.yml
```

### 京东云监控栈（推荐用于 LiMa 生产）

LiMa 主监控栈部署在京东云节点（`117.72.118.95`），由 `deploy/jdcloud/deploy_monitoring_stack.sh` 管理。

- **全新部署**：运行 `deploy/jdcloud/deploy_monitoring_stack.sh`，脚本会自动写入 `prometheus/rules/startup_alerts.yml`、挂载 rules 目录并配置抓取。
- **已有部署增量更新**：在京东云节点上运行：
  ```bash
  export LIMA_METRICS_API_KEY=<your_private_api_key>
  bash /opt/lima-router/deploy/jdcloud/update_startup_alerts.sh
  # 或从仓库复制后执行
  ```
- **Alertmanager 路由示例**：见 `deploy/jdcloud/alertmanager/alertmanager.yml`，按需替换 webhook URL。

> 注意：Prometheus 抓取 `https://chat.donglicao.com/v1/ops/metrics/prometheus` 需要 `LIMA_METRICS_API_KEY`。

## 本地验证

```bash
python -m pytest tests/test_prometheus_startup_alerts.py -v
```
