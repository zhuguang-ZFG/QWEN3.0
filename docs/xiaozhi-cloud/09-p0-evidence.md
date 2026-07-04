# P0 证据文档：小智官方云 MCP 接入与 DLC 骨架

> 关联入口：`docs/xiaozhi-cloud/README.md`
> 关联路线图：`docs/xiaozhi-cloud/00-roadmap.md`
> 关联冒烟命令：`docs/xiaozhi-cloud/p0-mcp-smoke-commands.md`
> 收口原则：**只记录已实测事实，不写猜测。未实测项统一进 `08-open-questions.md`。**

---

## 1. 本文件目的

在正式进入 P1 前，把 P0 阶段已经**实际跑通**的部分锁死为“既成事实”，作为 P1 接口与实现的证据基线。

任何 P1 决策都必须能追溯到本文件里的一条实测证据，或明确标注为“P0 未验证 → 见 `08-open-questions.md`”。

---

## 2. P0 已验证事实

### 2.1 项目内新增骨架已落地

| 骨架 | 路径 | 状态 |
|------|------|------|
| DLC HTTP API | `dlc_api/app.py`、`dlc_api/routes.py` | 已实现 `/health`、`/write`、`/draw` |
| DLC MCP 服务 | `dlc_mcp/server.py` | 已实现 `dlc.write_text`、`dlc.draw_generated` |
| DLC MCP 桥接 | `dlc_mcp/mcp_pipe.py` | 已实现 WebSocket ↔ stdio 桥接 |
| 聚焦测试 | `tests/test_dlc_api_health.py`、`tests/test_dlc_mcp_server.py`、`tests/test_dlc_mcp_pipe.py` | 12+ 个用例全部通过 |

### 2.2 `dlc_api` 已验证行为

- `GET /health` 返回：

  ```json
  {"status":"ok","service":"dlc-drawing","version":"0.1.0-p0"}
  ```

- `POST /write` 已实测能够走通到 `device_gateway.tasks.create_and_route_task`，返回：

  ```json
  {
    "status": "queued",
    "sent": false,
    "queue_depth": 1,
    "task_id": "task-000001",
    "error": null
  }
  ```

- `POST /draw` 已实测能够提交任务并返回 `task_id`，任务对应的图像生成链路失败见 §4。

- `/write` 与 `/draw` 已抽出 `_submit_device_task` helper，共用同一入口逻辑，路径为
  `dlc_api/routes.py:55-72`。

### 2.3 `dlc_mcp` 已验证行为

- `dlc_mcp/server.py` 已实测：
  - `initialize` 返回 `protocolVersion=2024-11-05`、`serverInfo.name=dlc-mcp-p0`
  - `tools/list` 返回 `dlc.write_text` 与 `dlc.draw_generated`
  - `tools/call` 会通过 `httpx.Client` 调 `dlc_api` 对应端点并把结构化摘要作为 MCP `content.text` 返回
  - 未知 method → `-32601 Method not found`
  - 参数缺失 → `-32602 Invalid params`
  - `dlc_api` 不可达 → `-32603` 且记录 `logger.warning`
- 复用同一个 `httpx.Client`（`main()` 中创建后传入 `handle_request`），避免每次工具调用新建连接。
- stdout 使用 `sys.stdout.buffer.write(... .encode("utf-8"))`，明确规避 Windows GBK 控制台导致 JSON 非 UTF-8 的问题。

### 2.4 官方云 MCP 接入已验证事实

用真实 endpoint 完成握手（脱敏：`wss://api.xiaozhi.me/mcp/?token=<JWT>`）：

- 官方云 broker 会主动发送 `initialize`
- 本地 `dlc_mcp.server` 通过 `mcp_pipe` 桥接后成功回复
- 官方云 broker 主动发送 `notifications/initialized`
- 官方云 broker 随后发送 `tools/list`
- 本地 stdio server 返回的 tool 列表被官方云正确解析
- 官方云控制台可以看到：
  - `dlc.write_text`
  - `dlc.draw_generated`

结论：**官方云能发现由本地 dlc_mcp 暴露的自定义 tool**。

### 2.5 编码问题闭环

- 症状：一开始 `dlc_mcp/server.py` 在 Windows 控制台下输出中文时，`stdout` 使用了控制台的 GBK 编码，导致返回给 broker 的 JSON 里出现 `0xc1` 等非 UTF-8 字节。
- 根因：Python 在 Windows 控制台下 `sys.stdout` 默认按控制台 code page 编码，`ensure_ascii=False` 时会把非 ASCII 字符写成非 UTF-8 字节序列。
- 修复：改为直接向 `sys.stdout.buffer` 写入 UTF-8 字节：

  ```python
  payload = json.dumps(resp, ensure_ascii=False) + "\n"
  sys.stdout.buffer.write(payload.encode("utf-8"))
  sys.stdout.buffer.flush()
  ```

- 结果：桥接层用 `text = line.decode("utf-8", errors="replace")` 能正确解析，实测握手完全通过。

### 2.6 已通过的自动化验证

- `python -m pytest tests/test_dlc_api_health.py tests/test_dlc_mcp_server.py tests/test_dlc_mcp_pipe.py -q` → **12 passed**（review 修复后追加至 13 passed）
- `ruff check dlc_api dlc_mcp tests/test_dlc_api_health.py tests/test_dlc_mcp_server.py tests/test_dlc_mcp_pipe.py` → **All checks passed**
- `python -m py_compile dlc_api/*.py dlc_mcp/*.py` → 无语法错误
- 手工冒烟（本地服务）：
  - `curl /health` → 200
  - `curl POST /write` → 200 + `task_id`
  - `curl POST /draw` → 200 + `task_id`

---

## 3. P0 已定型的接口形状

以下形状被 P0 实测证据固定，是 P1 冻结接口时的最小承诺，**不再改变以下字段**：

### 3.1 `dlc_api` P0 表面

- `GET /health` → `{status, service, version}`
- `POST /write` → 请求体 `{device_id, text, request_id?}`；响应体 `{status, sent, queue_depth, task_id, error}`
- `POST /draw` → 请求体 `{device_id, prompt, request_id?}`；响应体同上

### 3.2 `dlc_mcp` P0 tool 列表

- `dlc.write_text(device_id, text)`
- `dlc.draw_generated(device_id, prompt)`

> P1 允许在**不破坏**上述形状的前提下追加字段与新增 tool。任何删除或字段名变更必须在 `02-service-refactor.md` 显式声明。

---

## 4. P0 已知限制（必须写入文档）

### 4.1 `dlc.draw_generated` 图像生成链路阶段性失败

- 复现方式：`POST /draw` 或 `tools/call dlc.draw_generated`
- 现象：`device_gateway` 的现有图像生成链路（`DashScope` / `pollinations`）：
  - DashScope：返回 `401 InvalidApiKey`
  - Pollinations：因提示词增强后 URL 过长返回 `414 Request-URI Too Large`
- 结果：`draw_generated` 端到端还没跑通到设备。
- P0 影响面：**不影响 P0 定义的“MCP discovery + 骨架接口”验收**，仅影响 `draw_generated` 的端到端生图路径。
- P1 处理方向（不在 P0 内解决）：
  - 优化 prompt / 换用 POST body / 换后端；或
  - 把重点转向 `draw_from_image` + 预设图形；
  - 详见 `08-open-questions.md`。

### 4.2 官方云 broker 只完成 discovery，未做真实 `tools/call`

- P0 阶段官方云 broker 主动发的只有 `initialize` / `tools/list` / `notifications/initialized` / `ping`。
- 真实 `tools/call` 需要通过智能体对话触发；P0 已通过 broker discovery，**但未在真实语音对话中触发 tool 调用**。
- 因此“官方云在真实对话中如何调用外部 tool 序列”仍属未验证 → 归 `08-open-questions.md`。

### 4.3 断线/重连/心跳/graceful shutdown 未做

- `mcp_pipe` 当前是最小骨架；断线重连、心跳、超时策略、优雅关停都留到 P1/P2。

### 4.4 P0 未涉及固件与小程序

- P0 只覆盖服务端 + 官方云 MCP 接入。
- 固件端（U8/U1）与小程序端在 P0 未做联调，仅在设计文档中出现。

---

## 5. P0 未变更的既有 LiMa 子系统

以下子系统在 P0 阶段**未做变更**，是 `dlc_api` 现阶段的下游依赖：

- `device_gateway.tasks.create_and_route_task`
- `device_gateway` 任务存储（`store.py` / `redis_store.py`）
- `device_gateway.intent` 与相关意图链路

P0 只是给它们上层加了一个新的 HTTP + MCP 入口，没有做任何删除、迁移或重构。P1 才会开始把这些下游逐步收缩为 `dlc_core.*`。

---

## 6. P0 关键代码位置速查

| 主题 | 位置 |
|------|------|
| `dlc_api` FastAPI 入口 | `dlc_api/app.py` |
| `dlc_api` 路由与 helper | `dlc_api/routes.py:1-104` |
| `dlc_mcp` JSON-RPC handler | `dlc_mcp/server.py:83-135` |
| `dlc_mcp` UTF-8 输出修复点 | `dlc_mcp/server.py:139-152` |
| `dlc_mcp` WebSocket ↔ stdio 桥接 | `dlc_mcp/mcp_pipe.py` |
| P0 聚焦测试 | `tests/test_dlc_api_health.py`、`tests/test_dlc_mcp_server.py`、`tests/test_dlc_mcp_pipe.py` |
| 冒烟命令与实测流程 | `docs/xiaozhi-cloud/p0-mcp-smoke-commands.md` |

---

## 7. P0 验收结论

在本项目当前时间点：

- **P0 结论**：小智官方云能够通过本地 `dlc_mcp` 桥接发现并解析 DLC 自定义 tool；`dlc_api` 已能提交任务到设备任务队列。
- **P0 剩余风险**：`draw_generated` 图像生成链路当前不可用；真实语音对话中的 `tools/call` 行为未实测。
- **P0 可进入 P1**：**是**。P1 的第一步是把 P0 骨架接口冻结进 `02-service-refactor.md`，然后再开始收缩 LiMa 的下游依赖。
