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

LiMa 主监控栈部署在京东云节点（`117.72.118.95`）。当前生产环境使用原生 Prometheus 二进制 + systemd 服务（见 `deploy/jdcloud/auto_deploy.sh` 或 `deploy/jdcloud/native_prometheus.txt`）；`deploy/jdcloud/deploy_monitoring_stack.sh` 提供 docker-compose 版本作为备选。

- **已有部署增量更新**（systemd 或 docker-compose 会自动检测）：
  ```bash
  # 在京东云节点上
  bash /opt/lima-monitoring/update_startup_alerts.sh
  # 或从仓库复制最新版本后执行
  # bash /opt/lima-router/deploy/jdcloud/update_startup_alerts.sh
  ```
  脚本会：
  1. 创建/更新 `/opt/lima-monitoring/prometheus/rules/startup_alerts.yml`
  2. 确保 `prometheus/prometheus.yml` 包含 `rule_files: rules/*.yml`
  3. 自动检测 systemd `prometheus.service` 或 docker-compose 并重启
  4. 访问 `http://localhost:9090/api/v1/rules` 验证 `lima_startup` 规则组已加载

- **全新部署**：
  - systemd 原生：`bash deploy/jdcloud/auto_deploy.sh` 或按 `deploy/jdcloud/native_prometheus.txt` 步骤执行。
  - docker-compose：`bash deploy/jdcloud/deploy_monitoring_stack.sh`。

### Alertmanager 通知（G7.1）

京东云 Alertmanager 以 systemd 服务运行，监听 `0.0.0.0:9093`。

- **部署/更新**：
  ```bash
  # 在京东云节点上
  export DINGTALK_WEBHOOK_URL='https://oapi.dingtalk.com/robot/send?access_token=xxx'
  export WECHAT_WEBHOOK_URL='https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx'
  bash /opt/lima-monitoring/update_alertmanager.sh
  # 或从仓库复制最新版本后执行
  # bash /opt/lima-router/deploy/jdcloud/update_alertmanager.sh
  ```
  脚本会：
  1. 下载/复用 alertmanager 二进制（默认 0.25.0，华为云镜像）
  2. 复制 `deploy/jdcloud/alertmanager/alertmanager.yml` 并用环境变量替换占位符
  3. 创建/更新 systemd `alertmanager.service`
  4. 在 `prometheus/prometheus.yml` 中写入/更新 `alerting` 块指向 `127.0.0.1:9093`
  5. 验证 alertmanager health 与 Prometheus alertmanager 链路
  6. 重启 Prometheus 以加载 alerting 配置更新

- **路由说明**（`deploy/jdcloud/alertmanager/alertmanager.yml`）：
  - `critical` → 钉钉（`LiMaStartupPhaseVerySlow`、`LiMaStartupNotReady`、`LiMaStartupError`）
  - `lima-router` → 企业微信（所有 `service: lima-router` 告警）
  - `warning` 被同名的 `critical` 告警抑制（`inhibit_rules`）

> 注意：Prometheus 抓取 `https://chat.donglicao.com/v1/ops/metrics/prometheus` 需要 `LIMA_METRICS_API_KEY`。当前生产 `prometheus/prometheus.yml` 中已硬编码该 key，增量更新脚本不需要额外设置。

## 本地验证

```bash
python -m pytest tests/test_prometheus_startup_alerts.py tests/test_jdcloud_alertmanager.py -v
```
