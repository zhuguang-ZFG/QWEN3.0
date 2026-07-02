# LiMa AI 写字/绘图机稳定后端改进计划

> 制定时间：2026-06-29
> 依据：当前代码审查 + `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md` + `docs/archive/strategic-plans-2026-06/PROJECT_OPTIMIZATION_ROADMAP_CN.md`
> 目标：让 LiMa 从"功能可用"演进为写字/绘图机可长期依赖的稳定云端后端。

---

## 一、当前已具备的基础（不再重复建设）

| 能力 | 位置 | 状态 |
|---|---|---|
| 多后端 AI 路由 | `routing_engine.py`、`router_v3/` | 成熟 |
| 设备任务分类与 `route_policy` | `device_gateway/model_routing.py` | 已贯通 |
| 设备任务队列/派发/重入队 | `device_gateway/tasks.py`、Redis `device_gateway/redis_store.py` | 已具备 |
| 自然语言 AI 绘图 | `device_gateway/device_draw_handler.py` → `render_svg_task` | 已上线 |
| 生图多后端降级 | `routes/images.py` → `device_gateway/image_fallback.py` | 已上线 |
| 仿手写接入 | `routes/handwriting.py` → `integrations/autohanding/client.py` | 已上线 |
| 路径验证器 | `device_gateway/path_validator.py` | 存在，待与设备配置深度集成 |
| 设备画像 | `device_gateway/device_profile/` | 接口存在，数据源待补齐 |
| 指标（image） | `observability/prometheus_metrics.py` | image 相关已有，device task/handwriting 待补齐 |

---

## 二、代码审查发现的关键缺口

1. **Handwriting 单点依赖 autohanding.com**
   - `integrations/autohanding/client.py` 无重试；429/timeout/5xx 直接失败。
   - 没有本地降级路径，外部服务抖动时写字机直接无法工作。
   - 缺少 handwriting 专属指标。

2. **设备任务链路缺少 metrics**
   - `device_gateway/task_lifecycle.py`、`device_logic/gateway.py`、`routes/device_gateway_dispatch.py` 均无 Prometheus 计数。
   - 无法回答：任务创建→派发→ack→完成的转化率、失败率、重试率。

3. **任务重试无上限**
   - Redis store 有 `increment_retry_count`，但派发/重入队逻辑未检查最大重试次数，存在无限堆积风险。

4. **路径验证未绑定真实设备工作区**
   - `device_gateway/path_validator.py` 使用硬编码 `MAX_POINT_COORD ±500` 和 `MAX_PATH_POINTS 200`。
   - `device_gateway/safety.py` 使用 `DEFAULT_WORKSPACE_MM 100×100`。
   - 未按设备画像的 `workspace_mm`、`limits.max_points`、`capabilities` 做保守限制。

5. **设备画像未接入路由决策**
   - `device_gateway/device_profile/registry.py` 当前是内存注册表，重启即失；未与 `resolve_device_route_policy()` 形成闭环。

6. **缺少端到端发布门**
   - 已有 `draw_generated` 单测，但缺少 fake WebSocket 设备从 task 创建到 motion_event 的完整链路测试。

---

## 三、改进里程碑

### M15 Handwriting 韧性增强（1–2 天）

**目标**：外部服务抖动时，写字机仍能写字。

- `integrations/autohanding/client.py`
  - 对 timeout/5xx 增加指数退避重试（2 次，间隔 1s/2s）；遇到 429 立即透传，不加重。
  - 重试仍失败时抛出 `AutohandingClientError`。
- `routes/handwriting.py` / `device_gateway/task_draw_params.py`
  - autohanding 连续失败时，降级到本地 `device_gateway.path_pipeline.text_to_path` 生成确定性路径。
  - 降级路径返回 `backend: "lima-local"` 并在 `preview_svg` 中可见，确保用户知道不是手写体。
  - 对中文字符集：当前 stroke font 仅覆盖 ASCII；降级前优先尝试 autohanding，中文失败时返回可操作的 502 错误并记录，不静默输出乱码。
- `observability/prometheus_metrics.py`
  - 新增 `handwriting_requests_total{status, fallback}`、`handwriting_duration_seconds`。

**验证**：
```powershell
python -m pytest tests/test_autohanding_client.py tests/test_handwriting_fallback.py -q
python scripts/check_code_size.py integrations/autohanding/client.py routes/handwriting.py
pyright routes/handwriting.py integrations/autohanding/client.py
```

---

### M16 设备任务可观测性与重试边界（2–3 天）

**目标**：任务从创建到设备执行的每一步都可度量、可告警，避免无限重试。

- `observability/prometheus_metrics.py`
  - 新增 `device_tasks_created_total{capability, source}`
  - 新增 `device_tasks_dispatched_total{device_id, capability, status}`
  - 新增 `device_tasks_queued_total{device_id}`（gauge）
  - 新增 `device_task_dispatch_failures_total{reason}`
  - 新增 `device_task_retry_total{task_id}`（counter，按 task_id 标签需谨慎，可改为按 capability）
- `device_gateway/task_lifecycle.py` / `device_logic/gateway.py`
  - `dispatch_or_enqueue` 调用处打点：sent/queued/failed。
  - `mark_task_dispatched` 成功时记录 ack 等待开始时间。
- `device_gateway/redis_store.py`
  - `ack_processing` 成功/失败打点。
  - `recover_stale_processing` 触发时记录 `device_task_retry_total`。
- `routes/device_gateway_dispatch.py`
  - `requeue_session_outstanding` 前检查 `retry_count >= 3`，超过则转死信（记录 `device_task_dead_letter_total` 并停止重试）。

**验证**：
```powershell
python -m pytest tests/test_device_task_metrics.py tests/test_device_task_retry.py -q
python -m pytest tests/test_device_gateway_redis_store.py -q
```

---

### M17 SVG / 路径预检与设备工作区绑定（2–3 天）

**目标**：无效或危险路径在云端就被拦截，不落到机器。

- `device_gateway/path_validator.py`
  - 将硬编码 `MAX_PATH_POINTS`/`MAX_POINT_COORD` 改为从 `DeviceProfile` 读取 `limits.max_points`、`workspace_mm`。
  - 无画像时使用 `device_gateway/safety.py` 的保守默认值。
  - 增加 `preview_svg` 大小上限（如 1MB）检查。
- `device_gateway/path_pipeline.py`
  - `render_svg_task` / `render_text_task` 在返回前调用验证器，失败时抛出带 `MotionErrorCode` 的异常。
- `device_intelligence/safety.py` / `device_gateway/profiles.py`
  - 确保 `profile_limit_error` 能返回结构化错误码，而不仅是字符串。

**验证**：
```powershell
python -m pytest tests/test_path_validator_profile.py tests/test_path_simplification.py -q
python -m pytest tests/test_device_gateway_protocol.py -q
```

---

### M18 设备画像驱动的路由决策（3–5 天）

**目标**：路由选择先问设备能做什么，再问模型哪个强。

- `device_gateway/device_profile/registry.py`
  - 从持久存储加载画像（优先复用 `session_memory` SQLite 或 Redis shadow）。
  - 增加默认画像生成：未知设备使用最小工作区、最低进给、仅允许 `write_text`/`home`。
- `device_gateway/model_routing.py`
  - `resolve_device_route_policy` 已接受 `resolved_profile`；确保 `handwriting`/`draw_generated` 路径都传入画像。
  - 当画像 `capabilities` 不包含 `device_draw` 时，将 `draw_generated` 降级为 `write_text` 或返回审批门。
- `device_gateway/task_creation.py`
  - `apply_profile_constraints` 记录所有简化决策到任务制品。

**验证**：
```powershell
python -m pytest tests/test_device_profile_routing.py tests/test_device_gateway_model_routing.py -q
```

---

### M19 端到端发布门与假设备冒烟（2–3 天）

**目标**：每次影响运动的行为变更都必须经过 fake WebSocket 端到端测试。

- 新增 `tests/test_device_handwriting_e2e.py`
  - 创建假 `DeviceSession`，调用 `POST /device/v1/app/handwriting`（task 模式），断言任务被 dispatch/ack，最终 motion_event 包含预期 `source_capability`。
- 新增 `tests/test_device_draw_e2e.py`
  - 对 `draw_generated` 走完整链路：prompt → image fallback → SVG → path → dispatch → ack。
- 新增 `docs/release_evidence/TEMPLATE_HANDWRITING_DRAW_RELEASE.md`
  - 包含假设备证据、VPS health、关键指标截图。

**验证**：
```powershell
python -m pytest tests/test_device_handwriting_e2e.py tests/test_device_draw_e2e.py -q
python scripts/run_pre_commit_check.py --full
python scripts/deploy_unified.py --slice core
```

---

## 四、跨里程碑的通用项

| 项 | 说明 |
|---|---|
| **缓存** | M15/M18 之后引入 handwriting/draw 结果缓存，降低 API 成本。 |
| **限流** | 为 `/device/v1/app/handwriting` 和 `/device/v1/app/images/generations` 增加 per-device + per-account 限流。 |
| **文档同步** | 每关闭一个里程碑，同步 `STATUS.md`、`progress.md`、`docs/LIMA_MEMORY_CN.md`。 |
| **子模块边界** | U1/U8 固件侧的 `route_policy` 消费与拒绝逻辑仍在 `esp32S_XYZ`；LiMa 侧只保证云端契约正确，不越界修改固件。 |

---

## 五、推荐执行顺序

```text
M15（handwriting 韧性） → M16（任务可观测性） → M17（路径预检） → M18（画像路由） → M19（端到端发布门）
```

前两项（M15、M16）直接提升"稳定后端"体验，风险低、见效快，建议优先启动。
