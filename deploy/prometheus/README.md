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

示例 Docker Compose 见 `esp32S_XYZ/ops/monitoring/docker-compose.yml`（监控栈共享模式）。

## 本地验证

```bash
python -m pytest tests/test_prometheus_startup_alerts.py -v
```
