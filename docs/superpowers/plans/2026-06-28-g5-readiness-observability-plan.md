# G5 计划：让 readiness probe 在生产链路中可用 + 启动阶段可观测

## 目标

G4 已经在应用层实现了 `/health/ready` 与启动阶段耗时打印。G5 的目标是让这套机制真正被生产基础设施消费：

1. **通过生产 nginx 暴露 `/health/ready`**，使外部负载均衡、云监控、Kubernetes 等可以把 `https://chat.donglicao.com/health/ready` 当作 readiness probe。
2. **把启动阶段耗时导出为 Prometheus 指标**，让启动慢可以被告警和追踪。
3. **不改动现有 `/health` 行为**，保持向后兼容。

---

## Phase 0：文档发现（已完成）

### 已确认的事实

| 项 | 来源 | 结论 |
|---|---|---|
| nginx 权威配置 | `_nginx_chat_temp.conf` | 当前只有 `/health` location，没有 `/health/ready`。 |
| VPS nginx 副本 | `infra/vps/nginx/chat.donglicao.com.conf` | 与权威源结构一致，但顶部标注“Authoritative source: _nginx_chat_temp.conf”。 |
| nginx 部署方式 | `scripts/deploy_chat_web.py:122` | 只执行 `nginx -t && systemctl reload nginx`，不主动拷贝 `chat.donglicao.com.conf`。 |
| `/health/ready` 响应 | `routes/system_endpoints.py:128-140` | `ready` 返回 200 + `{"status":"ready"}`；否则 503 + `startup_status`/`pending_warm`/`error_count`。 |
| 启动阶段结构 | `server_lifespan_state.py:71-80` | 阶段含 `name`、`elapsed_ms`、`status`、`detail`。 |
| Prometheus 客户端 | `observability/prometheus_metrics.py` | 已使用 `prometheus_client`，有 Counter/Gauge/Histogram 模式。 |
| Prometheus 导出 | `observability/prometheus_exporter.py` | 后台线程每 30 秒更新 Gauge；启动阶段指标可在 `record_phase` 中直接记录。 |
| 阶段清单 | `server_lifespan_phases.py:197-211` | 6 个 critical phase + 5 个 warm phase。 |

### 反模式/限制

- **不要期望 nginx 开源版做 upstream 主动健康检查**：单节点部署没有多 upstream，开源 nginx 也不支持 `health_check` 指令（nginx plus 功能）。G5 只是把 `/health/ready` 作为普通 location 暴露出去。
- **不要在 `/health/ready` 里返回 `phases`**：保持 readiness 响应小而稳定；耗时详情继续走 `/health`。
- **不要修改 `/health` 语义**：`/health` 仍认为 `warming` 是 OK。

---

## Phase 1：nginx 暴露 `/health/ready`

### 1.1 修改 `_nginx_chat_temp.conf`

在现有 `/health` location 下方新增 `/health/ready` location，复用同样的 proxy 参数：

```nginx
# ── Health / Readiness ─────────────────────────────────────────────────
location = /health {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header User-Agent $http_user_agent;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}

location = /health/ready {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header User-Agent $http_user_agent;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_buffering off;
    # Readiness probe should fail fast so load balancers can retry elsewhere.
    proxy_read_timeout 10s;
    proxy_send_timeout 10s;
    proxy_connect_timeout 5s;
}
```

### 1.2 同步修改 `infra/vps/nginx/chat.donglicao.com.conf`

保持与权威源一致，并在文件顶部更新同步日期。

### 1.3 验证清单

- [ ] `nginx -t` 在 VPS 上通过。
- [ ] `curl -sf https://chat.donglicao.com/health/ready` 在 ready 时返回 200。
- [ ] 服务 warming 时返回 503 + `not_ready`。

---

## Phase 2：Prometheus 启动阶段指标

### 2.1 新增指标

在 `observability/prometheus_metrics.py` 中新增：

```python
# Histogram: per-phase duration
lima_startup_phase_duration_ms = histogram(
    "lima_startup_phase_duration_ms",
    "Startup phase duration in milliseconds",
    ["phase"],
    buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000],
    registry=registry,
)

# Gauge: current startup status (1=ready, 0.5=warming, 0=starting/error)
lima_startup_status = gauge(
    "lima_startup_status",
    "Current startup status: 1=ready, 0.5=warming, 0=starting/error",
    registry=registry,
)
```

### 2.2 记录点

在 `server_lifespan_state.py` 中：

1. `record_phase()` 完成时调用 `prometheus_metrics.record_startup_phase(name, elapsed_ms)`。
2. `set_startup_status()` 变化时调用 `prometheus_metrics.record_startup_status(status)`。

注意：记录函数需要防御 `prometheus_client` 未安装的情况（与现有代码风格一致），且不阻塞启动。

### 2.3 新增记录函数

在 `observability/prometheus_metrics.py` 中新增：

```python
_STATUS_VALUES = {"ready": 1.0, "warming": 0.5, "starting": 0.0, "error": 0.0}

def record_startup_phase(phase: str, elapsed_ms: float) -> None:
    if not is_enabled():
        return
    _ensure_instruments()
    h = _histograms.get("startup_phase_duration")
    if h:
        h.labels(phase=phase).observe(elapsed_ms)


def record_startup_status(status: str) -> None:
    if not is_enabled():
        return
    _ensure_instruments()
    g = _gauges.get("startup_status")
    if g:
        g.set(_STATUS_VALUES.get(status, 0.0))
```

### 2.4 验证清单

- [ ] `tests/test_observability_metrics.py` 新增用例验证 histogram/gauge 被正确记录。
- [ ] `LIMA_PROMETHEUS_METRICS=1` 启动后，`/v1/ops/metrics/prometheus` 输出包含 `lima_startup_phase_duration_ms_bucket` 和 `lima_startup_status`。
- [ ] `LIMA_PROMETHEUS_METRICS=0` 时无异常。

---

## Phase 3：部署脚本同步 nginx 配置（可选但推荐）

当前 `scripts/deploy_unified.py` 部署 core 切片时不主动同步 nginx。为避免手动拷贝遗漏，新增一个可选步骤：

1. 通过 SSH 把 `_nginx_chat_temp.conf` 拷贝到 `/etc/nginx/conf.d/chat.donglicao.com.conf`。
2. 执行 `nginx -t`。
3. 测试通过再 `systemctl reload nginx`。
4. 验证 `https://chat.donglicao.com/health/ready` 返回符合预期。

**风险**：nginx 配置是基础设施变更，错误会导致站点不可用。建议：
- 先备份远程 `/etc/nginx/conf.d/chat.donglicao.com.conf`。
- `nginx -t` 失败时回滚并中止部署。
- 默认关闭，通过 `--sync-nginx` 显式开启，避免每次 core 部署都触碰 nginx。

---

## Phase 4：测试

### 4.1 新增/更新测试

- `tests/test_system_endpoints.py`：确认 `/health/ready` 外网可达路径（如需要）保持现有覆盖。
- `tests/test_observability_metrics.py`：新增 `test_startup_phase_metric`、`test_startup_status_metric`。
- 新增 `tests/test_nginx_ready_config.py`：解析 `_nginx_chat_temp.conf`，断言存在 `/health/ready` location 且超时参数合理。

### 4.2 运行清单

- [ ] `python -m pytest tests/test_observability_metrics.py tests/test_system_endpoints.py -v`
- [ ] `ruff check .`
- [ ] `ruff format --check`
- [ ] `pyright observability/prometheus_metrics.py server_lifespan_state.py`
- [ ] `scripts/check_code_size.py`

---

## Phase 5：部署与文档

### 5.1 VPS 部署

1. 运行 `python scripts/deploy_unified.py --slice core`（如选择同步 nginx，加 `--sync-nginx`）。
2. 在 VPS 上手动验证：
   ```bash
   nginx -t
   curl -sf https://chat.donglicao.com/health/ready
   ```
3. 如果启用了 Prometheus，检查 `/v1/ops/metrics/prometheus` 包含新指标。

### 5.2 文档更新

- `progress.md`：新增 G5 结项条目。
- `docs/DEPLOY_AND_RELEASE_CONVENTION.md`：如有 `--sync-nginx` 参数，补充说明。
- `_nginx_chat_temp.conf` 顶部注释更新同步日期与变更说明。

---

## 验收标准

- [ ] `https://chat.donglicao.com/health/ready` 可正常访问，ready 时 200、未 ready 时 503。
- [ ] nginx 配置变更通过 `nginx -t` 并已 reload。
- [ ] Prometheus 指标 `lima_startup_phase_duration_ms` 与 `lima_startup_status` 在启用时可见。
- [ ] 所有新增/修改测试通过，ruff/pyright/code_size 干净。
- [ ] `progress.md` 已更新。

---

## 决策点

1. **是否在本次 G5 中加入 `--sync-nginx` 部署自动化？**
   - 推荐：只做 nginx 配置变更 + 本地测试 + 手动 VPS 同步；部署脚本同步作为 G5.1 或留待下次。
2. **是否在 `/health/ready` 响应中增加 `version`/`model` 等字段？**
   - 不推荐：保持响应最小，负载均衡器只关心 200/503。
3. **是否为 Prometheus 指标增加告警规则示例？**
   - 可选：本次可只输出指标；告警规则作为后续运维文档补充。
