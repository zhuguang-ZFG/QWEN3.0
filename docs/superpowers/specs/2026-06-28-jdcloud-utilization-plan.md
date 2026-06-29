# 京东云利用率提升计划（Phase 1：probe 结果回写与异地观测）

> 状态：Phase 1 已完成
> 作者：Kimi Code CLI
> 日期：2026-06-28
> 关联：`docs/ops/JDCLOUD_RUNTIME_STATUS.md`、`docs/ops/JDCLOUD_NEWAPI_DEPLOY.md`

---

## 1. 现状

京东云节点 `117.72.118.95` 当前承担两个角色：

1. **new-api 聚合门面**：`api.donglicao.com` 经阿里云反代后实际运行在京东云（`docs/ops/JDCLOUD_NEWAPI_DEPLOY.md`）。
2. **provider probe / 监控辅助节点**：`lima-probe.timer` 周期性探测 AI 提供商，输出到 `/opt/lima-probe/data/discoveries.jsonl` 与 `known_providers.json`。

除此之外，京东云的计算/网络资源没有直接服务于 LiMa 主路由或设备面，属于“半利用”状态。

---

## 2. 可选提升方向

| 方向 | 价值 | 风险 | 工时估算 |
|------|------|------|----------|
| **A. probe 结果回写 + 异地观测** | 让京东云成为 LiMa 的异地健康/价格/延迟数据源，admin 面板可直接查看 | 低：只增加只读数据上报，不暴露新 API | 2–3 天 |
| **B. 分担低价/免费后端流量** | 把部分免费/低价后端请求路由到京东云 Worker，降低主 VPS 成本 | 中：需要新增反向代理、密钥隔离、后端注册 | 5–7 天 |
| **C. 热备 / 故障转移** | 主节点故障时切换到京东云 LiMa 镜像 | 高：需要数据同步、状态共享、DNS/代理切换 | 7–10 天 |
| **D. 资源 audit** | 先 SSH 登上京东云盘点 CPU/内存/磁盘/网络余量 | 无 | 0.5 天 |

**推荐先实施 A**：
- 与当前 probe 工作自然衔接，不破坏现有架构。
- 不引入新公网入口，不增加攻击面。
- 输出可直接支撑后续 B/C 的决策（哪些后端在京东云线路上更稳定/便宜）。

---

## 3. Phase 1 目标

让京东云 probe 的**结构化结果**能够安全地回流到 LiMa 主节点，并在 Admin 端点展示：

- 每个 provider 的探测状态（alive/dead）。
- 延迟、价格 tier、最近探测时间。
- 探测来源标记为 `jdcloud`。

---

## 4. 实现方案

### 4.1 LiMa 侧：新增 Admin 接收端点

- **新建** `routes/admin_probe_ingress.py`：
  - `POST /admin/api/probe/ingress`
  - 认证：使用 `LIMA_PROBE_INGRESS_TOKEN`（独立 token，非 admin token，最小权限）。
  - 校验 payload 签名或简单 HMAC（可选）。
  - 将结果写入 `observability/probe_state.py` 的内存/文件快照。
- **扩展** `routes/admin_metrics.py` 或新增 `GET /admin/api/probe/jdcloud`：
  - 返回京东云 probe 聚合结果。

### 4.2 京东云侧：probe 结果推送脚本

- **新建** `deploy/jdcloud/push_probe_results.sh`（或 Python 脚本）：
  - 读取 `/opt/lima-probe/data/known_providers.json` 和最近的 `discoveries.jsonl`。
  - 生成脱敏 payload（不含真实 key、密码）。
  - 通过 HTTPS 或内网通道 POST 到 `https://chat.donglicao.com/admin/api/probe/ingress`。
  - 失败时记录本地日志，不阻塞 probe。
- 在 `lima-probe.service` 的 `ExecStopPost` 或 `lima-probe.timer` 的 `[Unit] OnSuccess` 触发推送；或独立 timer 每 5 分钟推一次。

### 4.3 数据模型

```python
@dataclass
class ProbeIngressEvent:
    source: str = "jdcloud"
    provider: str
    status: str  # alive | degraded | dead | unknown
    latency_ms: float
    price_tier: str = ""
    checked_at: str  # ISO
    metadata: dict  # 可扩展
```

### 4.4 安全与默认关闭

- `LIMA_PROBE_INGRESS_ENABLED=0` 默认关闭。
- token 独立，不重用 `LIMA_ADMIN_TOKEN`。
- payload 必须经过 `_sanitize_metadata()` 风格脱敏。
- 京东云侧脚本不暴露私钥；仅上报探测结果元数据。

---

## 5. 验收标准

- [ ] `POST /admin/api/probe/ingress` 在关闭时返回 503/禁用提示。
- [ ] 开启后，京东云 probe 结果能在 `/admin/api/probe/jdcloud` 查询到。
- [ ] payload 中不包含任何真实 API key、密码、私钥。
- [ ] 京东云侧推送失败时只记录 warning，不影响 probe 本身。
- [ ] 新增单元测试覆盖认证、脱敏、聚合逻辑。
- [ ] `ruff`、`pyright`、`check_code_size` 通过。

---

## 6. 风险与回滚

| 风险 | 应对 |
|------|------|
| 推送端点被滥用 | 独立 token + IP 白名单（京东云 IP） |
| payload 泄露敏感信息 | 严格脱敏 + 单元测试断言 |
| probe timer 依赖推送 | 推送与 probe 解耦，失败不影响 probe |

回滚：关闭 `LIMA_PROBE_INGRESS_ENABLED=0`，删除推送脚本/timer。

---

## 7. Phase 1 完成证据

- `POST /admin/api/probe/ingress` 端点已存在于主 VPS，无需新建。
- 京东云推送脚本 `deploy/jdcloud/push_probe_results.py` 与
  `push_probe_results_utils.py` 已部署。
- `lima-probe-push.service` / `lima-probe-push.timer` 已启用并 active，
  每 5 分钟推送一次。
- 手动触发推送返回 `200`，`recorded=39`。
- `GET /admin/api/probe/jdcloud` 返回 `count=39`，数据与京东云 probe 快照一致。
- 京东云节点清理完成：退役 `openclaw-gateway`，清理 docker images/journal/logs；
  内存从 `used 3.4G / available 436M` 改善为 `used 3.1G / available 688M`；
  磁盘从 `used 32G` 降至 `used 28G`。

## 8. 下一步

1. 观察 Phase 1 数据质量与稳定性。
2. 评估 Phase 2（分担低价/免费后端流量）的内存与网络约束。
3. 更新 `docs/ops/JDCLOUD_RUNTIME_STATUS.md` 与 `STATUS.md`。
