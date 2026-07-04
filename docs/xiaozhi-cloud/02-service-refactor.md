# 服务端改造分册：dlc_core / dlc_api / dlc_mcp

> 当前主路线：**在 `D:/QWEN3.0` 内瘦身出 `dlc_core / dlc_api / dlc_mcp`。**
> 关联文档：`README.md`、`00-roadmap.md`、`01-architecture.md`、`09-p0-evidence.md`、`08-open-questions.md`
> 权威总设计：`lima-slimdown-design.md` §3
> 本册定位：把服务端三层的**模块边界、接口形状、迁移来源、实现阶段**冻结下来，作为 P1 编码前的接口契约。

---

## 1. 本册目的

服务端瘦身分三层：

- `dlc_core/`：纯算法 + 薄封装，不含网络 I/O（SRP 核心库）
- `dlc_api/`：FastAPI HTTP 层，供固件 / 小程序 / 外部调用
- `dlc_mcp/`：MCP Server + WebSocket 接入器，供小智官方云调用

本册要解决的问题：

1. 明确每个模块从哪个 LiMa 现有文件迁移而来（避免重写）。
2. 冻结 `dlc_api` 路由与 `dlc_mcp` tool 列表（避免后续摇摆）。
3. 标清哪些已是 P0 实测事实、哪些是 P1+ 待实现，不把设计写成已完成。

---

## 2. 当前真实状态（P1 已落地）

> 以下是 `D:/QWEN3.0` 里**已经存在并验证过**的代码，来源 `10-p1-evidence.md`。

### 2.1 已落地文件

```text
dlc_core/
  __init__.py          # facade 聚合导出
  intent.py            # 意图解析 facade
  write.py             # 写字 facade
  draw.py              # 绘图 facade（P1 默认禁用 AI 生图）
  presets.py           # 预设图形 facade
  path_validator.py    # 路径校验 facade
  safety.py            # 权威安全常量
  dispatch.py          # 任务下发 facade（含 device_busy pre-check）
dlc_api/
  __init__.py
  app.py               # FastAPI app，include dlc_api.routes
  deps.py              # `verify_dlc_api_token` 占位实现（FIXME-Q07）
  routes.py            # /health、/dlc/tasks/preview、/dlc/tasks/dispatch
dlc_mcp/
  __init__.py
  server.py            # JSON-RPC：initialize / tools/list / tools/call
  mcp_pipe.py          # WebSocket ↔ stdio 桥接
xiaozhi_drawing/       # 15 个算法文件，全部保留，dlc_core 将依赖它
```

### 2.2 P1 已验证接口（已冻结）

`dlc_api`（`dlc_api/routes.py`）：

| 方法 | 路径 | P1 行为 |
|------|------|---------|
| GET | `/health` | 返回 `{"status":"ok","service":"dlc-drawing","version":"0.2.0-p1"}` |
| POST | `/dlc/tasks/preview` | body `{type, device_id, payload}` → `dlc_core.handle_write/handle_draw`，生成路径/预览 |
| POST | `/dlc/tasks/dispatch` | body `{type, device_id, payload, request_id?}` → 生成路径 + `dlc_core.dispatch_task` |

`dlc_mcp`（`dlc_mcp/server.py`）：

| tool | P1 行为 |
|------|---------|
| `dlc.write_text` | 校验 `device_id`+`text`，POST `dlc_api /dlc/tasks/dispatch type=write_text` |
| `dlc.draw_generated` | 校验 `device_id`+`prompt`，POST `dlc_api /dlc/tasks/dispatch type=draw_generated` |

> P0 的 `/write`、`/draw` 已在 P1 删除，由 `/dlc/tasks/*` 统一契约替代。

---

## 3. dlc_core 模块边界（P1 冻结目标）

> 每个模块标注：来源文件 + 实现阶段。**P1 优先用 facade 复用现有实现，不重写。**

| 模块 | 职责 | 迁移来源 | 阶段 |
|------|------|----------|------|
| `intent.py` | 文本→能力分类（write_text/draw/home/pause/...） | `device_gateway/intent.py` | P1 facade |
| `task_model.py` | intent→motion_task 结构 | `device_gateway/task_creation.py` 精简 | P1 |
| `write.py` | 写字处理 → path + preview | `xiaozhi_drawing/text_to_path.py` + `device_gateway` 写字链 | P1 |
| `draw.py` | 提示词/预设绘图 + 图片矢量化 | `device_gateway/device_draw_handler.py` 精简 | P1（generated）/ P2（from_image） |
| `presets.py` | 预设图形（圆/方/三角/星/心） | `xiaozhi_drawing/preset_shapes.py` | P1 facade |
| `path_pipeline.py` | 文字/SVG→路径点 | `device_gateway/path_pipeline.py` + `xiaozhi_drawing/pipeline.py` | P1 |
| `path_validator.py` | 路径安全校验 | `device_gateway/path_validator.py` | P1 |
| `safety.py` | 工作区/点数/feed 边界常量 | `device_gateway/path_data.py`、`safety.py`、`path_validator.py` 收敛 | P1（统一 `MAX_PATH_POINTS=200`） |
| `preview.py` | SVG 预览生成 | `xiaozhi_drawing/svg_converter.py` | P1 |
| `dispatch.py` | 任务下发（含 device_busy pre-check） | `device_gateway/tasks.py`、`redis_store.py` | P1 |
| `profiles.py` | 设备尺寸/约束 | `device_gateway/device_profile/` | P1 facade |
| `device_status.py` | 状态聚合（registry+task_store+shadow） | `device_gateway/sessions.py`、`store.py`、`device_intelligence/shadow.py` | P2 |
| `knowledge.py` | 绘图机知识库（可选） | 新增 / `device_memory` | P3（可选） |

### 3.1 冻结的核心签名（P1 契约）

```python
# dlc_core/intent.py
def parse_intent(text: str) -> dict:
    """{capability, params, source, confidence, explanation}
    capability: write_text | draw_generated | home | pause | resume | stop | move_abs | move_rel | run_path
    P1 facade: from device_gateway.intent import resolve_voice_task as parse_intent
    """

# dlc_core/write.py
async def handle_write(text: str, *, font_style="default", size="medium",
                       device_id: str | None = None) -> dict:
    """{status, path_data, preview_svg, width, height, model, error}"""

# dlc_core/draw.py
async def handle_draw(prompt: str, *, device_id=None, allow_dashscope=False) -> dict:
    """{status, svg_path, preview_svg, width, height, model, error}
    allow_dashscope: MCP/固件=False；小程序 HTTP 可 True。
    """

async def handle_draw_from_image(image_url: str, *, device_id=None, skeletonize=True) -> dict:
    """图片矢量化。收到请求必须立即下载到 /tmp/dlc_uploads/，规避 Telegram 临时 URL 过期。"""

# dlc_core/path_validator.py
def validate_path(path: list[dict], *, workspace: dict | None = None) -> dict:
    """{ok, errors, warnings}"""

# dlc_core/safety.py
DEFAULT_WORKSPACE_MM = {"x": 100.0, "y": 100.0, "z": 20.0}
MAX_PATH_POINTS = 200  # authoritative；删除旧模块 128/200 冲突常量

# dlc_core/dispatch.py
async def dispatch_task(device_id: str, task: dict, *, channel: str = "mqtt") -> dict:
    """下发前 device_busy pre-check：有活跃任务返回 {status:"rejected", reason:"device_busy"}"""

# dlc_core/device_status.py
async def get_device_status(device_id: str) -> dict:
    """{online, working, active_task_id, firmware_version, last_seen_at, shadow}"""
```

> **Ponytail 决策：** P1 阶段 `dlc_core` 模块尽量做成对 `device_gateway` / `xiaozhi_drawing` 的 facade（薄封装），先建立稳定入口，不整体搬运代码。物理迁移放到 P3/P4，配合 CodeGraph 影响分析逐步进行。

---

## 4. dlc_api 路由（P1 冻结）

### 4.1 正式 `/dlc/*` 契约

| 方法 | 路径 | 调用方 | 鉴权 | 说明 |
|------|------|--------|------|------|
| GET | `/health` | 运维/LB | 无 | 存活探针 |
| POST | `/dlc/tasks/preview` | 固件/MCP/小程序 | `verify_dlc_api_token` | 生成路径+预览，不下发 |
| POST | `/dlc/tasks/validate` | 固件 | `verify_dlc_api_token` | 已有路径二次校验 |
| POST | `/dlc/tasks/dispatch` | 固件/MCP/小程序 | `verify_dlc_api_token` + `caller_device_id==body.device_id` | 生成+下发 |
| GET | `/dlc/tasks/{task_id}` | 固件/MCP | `verify_dlc_api_token` + task 归属校验 | 查询任务 |
| GET | `/dlc/devices/{device_id}/status` | MCP | `verify_dlc_api_token` + `caller==path.device_id` | 设备状态 |
| GET | `/dlc/knowledge` | MCP | `verify_dlc_api_token` | 知识库（可选） |

- `preview`/`dispatch` 的 `type`: `write_text | draw_generated | draw_from_image`
- `allow_dashscope`: 仅 `type=draw_generated` 生效，小程序可 True，MCP/固件强制 False。

### 4.2 P0 → P1 迁移说明

P0 的 `/write`、`/draw` 是骨架，P1 处理方式：

1. 保留 `/write`、`/draw` 作为兼容别名（内部转 `dispatch type=write_text/draw_generated`），或
2. 直接替换为 `/dlc/tasks/dispatch`，并更新 `dlc_mcp/server.py` 调用路径。

> **决策记录：** 采用方案 2（替换），因为 P0 骨架尚无外部依赖，越早统一契约越省后续兼容成本。P1 实现时同步改 `dlc_mcp/server.py` 的 endpoint。这属于 §08-open-questions 之外的确定性动作。

### 4.3 现有 `/device/v1/app/*`（小程序）不改路径

小程序继续用 `/device/v1/app/*`，**不迁到 `/dlc/*`**；仅把内部路径生成逻辑替换为 `dlc_core`。映射见 `lima-slimdown-design.md` §3.5。

---

## 5. dlc_mcp 工具（P1 冻结）

### 5.1 tool 列表

| tool | 入参 | 阶段 | 说明 |
|------|------|------|------|
| `dlc.write_text` | `text`(+P1 起 `device_id`) | P0 已有 | 写字 |
| `dlc.draw_generated` | `prompt` | P0 已有 | 本地预设/字体，`allow_dashscope=False` |
| `dlc.draw_from_image` | `image_url`, `skeletonize?` | P2 | 图库/上传图矢量化 |
| `dlc.validate_path` | `path` | P1 | 路径校验 |
| `dlc.get_device_status` | `device_id` | P2 | 设备状态 |
| `dlc.get_plotter_knowledge` | `topic`, `query` | P3（可选） | 知识库 |

**不暴露 `dlc.dispatch_task`：** 避免 LLM 选择复杂度；dispatch 仅走 HTTP `/dlc/tasks/dispatch`。理由见 `lima-slimdown-design.md` §3.4。

### 5.2 P0 与设计的差异（必须记录）

- P0 的 `dlc.write_text` / `dlc.draw_generated` 已带 `device_id` 参数，且直接 POST `/write`、`/draw`。
- 设计里 `dlc.write_text` 只写 `text`——**设备绑定问题**（tool 如何知道 device_id）是 §08-open-questions 关联项，P1 需明确：
  - 方案 a：MCP endpoint per-device（一个设备一个 token，服务端从 token 反查 device_id）；
  - 方案 b：tool 显式传 device_id（P0 现状）。
- P1 决策前，保留 P0 的显式 `device_id` 传参。

---

## 6. 服务入口

| 入口 | 阶段 | 说明 |
|------|------|------|
| `dlc_api/app.py` | P1 已更新 | 最小 app，`/health` + `/dlc/tasks/preview` + `/dlc/tasks/dispatch` |
| `dlc_api/deps.py` | P1 新增 | `verify_dlc_api_token` 占位实现（FIXME-Q07） |
| `server_dlc.py` | P2 新增 | 正式生产入口，仅监听 `127.0.0.1:8080`，公网经 nginx TLS |
| `server.py` | 现存 | 旧 LiMa 入口，P4 降级/删除 |

---

## 7. 本册验收标准

1. `dlc_core` 每个模块都有明确来源文件与实现阶段。
2. `dlc_api` `/dlc/*` 契约冻结，P0→P1 迁移方式明确。
3. `dlc_mcp` tool 列表冻结，`device_id` 传参问题挂到 open-questions。
4. 未把 facade（P1 计划）写成已完成实现。
5. 与 `09-p0-evidence.md` 的真实状态无冲突。

---

## 8. 下一步

- `03-firmware-refactor.md`：U8/U1 固件、`self.motor.run_path`、`self.plotter.*`、`motion_busy_` 防呆。
- `04-miniprogram-refactor.md`：登录/配网/一键配网/状态页/任务页。
