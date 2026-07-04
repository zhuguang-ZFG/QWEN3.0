# P1 证据文档：D4 接口冻结与核心闭环

> 关联入口：`docs/xiaozhi-cloud/README.md`
> 关联路线图：`docs/xiaozhi-cloud/00-roadmap.md` §4
> 关联设计：`docs/xiaozhi-cloud/02-service-refactor.md`
> 关联未决项：`docs/xiaozhi-cloud/08-open-questions.md`（Q-02 / Q-07）
> 关联 P0 证据：`docs/xiaozhi-cloud/09-p0-evidence.md`
> 收口原则：**只记录已实测事实与已冻结接口。**

---

## 1. 本文件目的

记录 P1 阶段实际完成的接口冻结、核心 facade 落地与测试证据，作为 P2（固件/小程序接入）的输入基线。

---

## 2. P1 已验证事实

### 2.1 `dlc_core` facade 已落地

| 模块 | 路径 | 来源 | 验证状态 |
|------|------|------|----------|
| `safety` | `dlc_core/safety.py` | 新增，统一常量 | 单元测试通过 |
| `intent` | `dlc_core/intent.py` | `device_gateway.intent` facade | 单元测试通过 |
| `write` | `dlc_core/write.py` | `device_gateway.device_write_handler` facade | 单元测试通过 |
| `draw` | `dlc_core/draw.py` | `device_gateway.device_draw_handler` 精简 | 单元测试通过 |
| `presets` | `dlc_core/presets.py` | `xiaozhi_drawing.preset_shapes` facade | 单元测试通过 |
| `path_validator` | `dlc_core/path_validator.py` | `device_gateway.path_validator` 最小封装 | 单元测试通过 |
| `dispatch` | `dlc_core/dispatch.py` | `device_gateway.tasks` 薄封装 | 集成测试通过 |

### 2.2 `dlc_api` 接口已冻结

- `GET /health` 返回：

  ```json
  {"status": "ok", "service": "dlc-drawing", "version": "0.2.0-p1"}
  ```

- `POST /dlc/tasks/preview`：
  - 请求体 `{type, device_id, payload}`
  - `type=write_text` 时生成文字路径预览
  - `type=draw_generated` 时生成预设图形/字体路径预览
  - 响应体 `{status, path_data/svg_path, preview_svg, width, height, model, error}`

- `POST /dlc/tasks/dispatch`：
  - 请求体 `{type, device_id, payload, request_id?}`
  - 生成路径后调用 `dlc_core.dispatch_task` 入队/下发
  - 响应体 `{status, task_id, queue_depth, error}`

- P0 的 `/write`、`/draw` 已删除，测试验证返回 `404`。

### 2.3 `dlc_mcp` tool 已切换

- `dlc.write_text` 与 `dlc.draw_generated` 内部 POST 端点已从 `/write`、`/draw` 切到 `/dlc/tasks/dispatch`。
- tool schema 保持与 P0 兼容（入参仍为 `device_id` + `text`/`prompt`）。
- stdout UTF-8 输出机制保留。

### 2.4 `draw_generated` P1 降级策略已落地

- P1 的 `dlc_core.draw.handle_draw` 默认 `allow_dashscope=False`。
- 实际语义：优先预设图形匹配，其次字体路径，AI 生图被显式禁用并返回友好错误。
- 该策略规避了 Q-02 后端不确定性，保证 P1 能稳定演示「画圆/画方」等预设图形闭环。

---

## 3. P1 自动化验证证据

### 3.1 测试命令与结果

```bash
python -m pytest tests/test_dlc_core_safety.py tests/test_dlc_core_presets.py tests/test_dlc_core_write.py tests/test_dlc_core_draw.py tests/test_dlc_api.py tests/test_dlc_mcp_server.py -v
```

结果：**21 passed**。

### 3.2 代码检查

```bash
ruff check dlc_core dlc_api dlc_mcp tests/test_dlc_*.py
```

结果：**All checks passed!**

### 3.3 类型检查

```bash
pyright dlc_core dlc_api dlc_mcp
```

结果：**0 errors**（`dlc_mcp/mcp_pipe.py` 有 18 个 pre-existing warnings，与 websockets 类型 stubs 有关，非 P1 新增）。

---

## 4. P1 决策记录

| 决策 | 内容 | 原因 |
|------|------|------|
| `/write`、`/draw` 删除 | 直接替换为 `/dlc/tasks/*` | P0 骨架无外部依赖，越早统一契约越省兼容成本 |
| `draw_generated` 降级 | P1 默认禁用 AI 生图，预设图形优先 | DashScope/Pollinations 链路尚未恢复，见 Q-02 |
| 鉴权占位 | `verify_dlc_api_token` 使用 `LIMA_DEVICE_TOKENS` env 兜底 | per-device token 下放 P2，见 Q-07 |
| facade 优先 | `dlc_core` 只做薄封装，不整体搬运 `device_gateway` | 符合 Ponytail 原则，降低测试风险 |

---

## 5. P1 关键代码位置速查

| 主题 | 位置 |
|------|------|
| `dlc_core` facade 入口 | `dlc_core/__init__.py` |
| 写字 facade | `dlc_core/write.py` |
| 绘图 facade | `dlc_core/draw.py` |
| 预设图形 facade | `dlc_core/presets.py` |
| 安全常量 | `dlc_core/safety.py` |
| 任务下发 facade | `dlc_core/dispatch.py` |
| `dlc_api` 路由 | `dlc_api/routes.py` |
| `dlc_api` 鉴权占位 | `dlc_api/deps.py` |
| `dlc_mcp` JSON-RPC handler | `dlc_mcp/server.py` |
| P1 测试集 | `tests/test_dlc_core_*.py`、`tests/test_dlc_api.py`、`tests/test_dlc_mcp_server.py` |

---

## 6. P1 验收结论

- **P1 目标达成**：`dlc_core / dlc_api / dlc_mcp` 接口已冻结，写字与预设图形绘图闭环在测试中成立。
- **可进入 P2**：固件/小程序接入所需的服务端接口边界已稳定。
- **遗留风险**：`draw_generated` AI 生图端到端仍依赖后端修复（Q-02）；鉴权需 P2 替换为 per-device token（Q-07）。

---

## 7. TDD 证据（RED → GREEN）

| 计划任务 | 测试文件（RED） | 失败原因 | 实现文件（GREEN） | 验证命令 | 结果 |
|----------|-----------------|----------|-------------------|----------|------|
| `dlc_core.safety` 常量 | `tests/test_dlc_core_safety.py` | `ModuleNotFoundError: No module named 'dlc_core.safety'` | `dlc_core/safety.py` | `pytest tests/test_dlc_core_safety.py -v` | 2 passed |
| `dlc_core.presets` facade | `tests/test_dlc_core_presets.py` | `ModuleNotFoundError: No module named 'dlc_core.presets'` | `dlc_core/presets.py` | `pytest tests/test_dlc_core_presets.py -v` | 2 passed |
| `dlc_core.write` facade | `tests/test_dlc_core_write.py` | `ModuleNotFoundError: No module named 'dlc_core.write'` | `dlc_core/write.py` | `pytest tests/test_dlc_core_write.py -v` | 2 passed |
| `dlc_core.draw` facade | `tests/test_dlc_core_draw.py` | `ModuleNotFoundError: No module named 'dlc_core.draw'` | `dlc_core/draw.py` | `pytest tests/test_dlc_core_draw.py -v` | 3 passed |
| `dlc_api` `/dlc/*` 路由 | `tests/test_dlc_api.py` | `404` for `/dlc/tasks/*`；`/write`/`/draw` 仍存在 | `dlc_api/routes.py` + `dlc_api/deps.py` | `pytest tests/test_dlc_api.py -v` | 5 passed |
| `dlc_mcp` endpoint 切换 | `tests/test_dlc_mcp_server.py` | 仍调 `/write` | `dlc_mcp/server.py` | `pytest tests/test_dlc_mcp_server.py -v` | 7 passed |

**合计**：21 passed，ruff 全绿，pyright 0 errors。

---

## 8. 覆盖说明

- P1 新增代码集中在 `dlc_core/`、`dlc_api/`、`dlc_mcp/`、`tests/test_dlc_*.py`。
- `dlc_mcp/mcp_pipe.py` 未做改动，沿用 P0 实现。
- `draw_generated` 的 AI 生图分支在 P1 被显式禁用，因此 `_generate_image` 中调用 `_handle_device_draw` 的路径当前无测试覆盖；该路径将在 Q-02 后端收敛后补测。
