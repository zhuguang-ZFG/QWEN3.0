# Architecture — 模块地图与边界

## 请求处理链路（P4/P5 瘦身后的真实架构）

```
Client → server_dlc.py (FastAPI 入口，:8081，/docs 已禁用 SEC-05)
      → dlc_api/routes.py (/dlc/tasks/* + /dlc/devices/*，verify_dlc_api_token)
      → dlc_core (handle_draw / handle_write / handle_draw_from_image)
      → dlc_core/dispatch.py → device_gateway (Redis 任务队列 → ESP32)
小智云 MCP → dlc_mcp/server.py (JSON-RPC stdio ↔ WS bridge)
          → dlc_api/routes.py
微信小程序 → server_dlc.py (/device/v1/app/*，device_app_router 聚合)
```

证据：`server_dlc.py`（入口 wiring）、`docs/AGENTS_REFERENCE_CN.md`「架构」节。

## 关键模块归属

| 职责 | 模块 |
|------|------|
| HTTP 入口 | `server_dlc.py` |
| DLC 路由 | `dlc_api/`（`routes.py`、`app.py`、`deps.py`、`schemas.py`、`device_app_router.py`、`middleware.py`、`idempotency.py`） |
| 绘图/写字核心 | `dlc_core/`（`draw.py`、`dispatch.py`、`device_status.py`、`write.py`、`path_validator.py`、`presets.py`、`safety.py`、`intent.py`） |
| MCP JSON-RPC | `dlc_mcp/`（`server.py`、`mcp_pipe.py`） |
| 设备网关 | `device_gateway/`（Redis 队列、WS、设备状态、family approval、gallery） |
| 设备 App API | `routes/`（`device_app_*`、`device_app_voice*`） |
| 语音 ASR | `device_voice/`（DashScope / FunASR / Whisper）、`voice_app_ws_ticket.py` |
| 鉴权/限流 | `access_guard.py`、`rate_limiter.py`、`ws_ticket.py`、`device_logic/auth.py` |
| 图生 | `dashscope_image_client.py`（DashScope/wanx，经 `asyncio.to_thread`） |
| 配置 | `config/`（如 `config/voice_settings.py` 的 `VOICE` 对象） |

## 退役模块（禁止按此去找代码）

旧 `server.py` / `routing_engine*` / `router_v3` / `routing_executor` / `http_caller` / `context_pipeline` / `session_memory` 主路径 / `observability`（除 `structured_logging`）/ `provider_probe` / `backends_registry` 已在 P4/P5 瘦身**物理删除**。归档说明见 `docs/archive/`，删除史见 `progress.md`。

自托管 WSS→ESP32 已退役，设备任务以 Redis 队列/小程序路径为主（`STATUS.md`）。

## 仓库结构

- `server_dlc.py` + `dlc_api/` + `dlc_core/` + `dlc_mcp/` + `device_gateway/` + `device_voice/` + `routes/` — 生产服务
- `scripts/` — 工具、部署（`deploy_unified.py`）、冒烟（`run_voice_e2e_production.py`）、门禁（`run_pre_commit_check.py`、`check_code_size.py`）
- `tests/` — 221+ 测试文件，按域分子目录（`device_gateway/`、`sdk/`、`xiaozhi_schema/`、`fixtures/`、`helpers/`）；新增测试放进对应域目录
- `esp32S_XYZ/` — git 子模块（固件 + 小程序），规范见 `../esp32S_XYZ/index.md`
- `docs/` 与 `docs-site/` — 文档；`deploy/`、`nginx/` — 部署资产
