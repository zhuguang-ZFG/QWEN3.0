# LiMa 系统架构文档（P4/P5 瘦身后）

> 更新日期：2026-07-09
> 当前版本：`dlc-drawing 0.4.0-p3`，Python 3.10 + FastAPI
> 生产入口：`server_dlc:8081`，公网 `https://chat.donglicao.com`

旧版多后端 AI 路由架构（server.py + routing_engine + router_v3 + chat/admin/voice/provider 探测）已在 P4/P5 瘦身物理删除，旧版架构文档归档于 [`archive/strategic-plans-2026-06/ARCHITECTURE_OLD_20260626.md`](archive/strategic-plans-2026-06/ARCHITECTURE_OLD_20260626.md)。

## 1. 系统定位

LiMa 是深圳市动力巢科技有限公司（donglicao.com）面向 ESP32 绘图机/写字机/2D 数字人的云端控制平面：路径生成、任务下发、设备管理。通过 MCP 协议与小智官方云（xiaozhi.me）集成，支持语音控制绘图/写字。微信小程序提供设备配网、AI 绘图/写字、设备状态与审批交互。

## 2. 架构全景

```text
┌──────────────────────────────────────────────────────────┐
│ 客户端层                                                  │
│ 微信小程序 (manager-mobile) / 小智官方云 MCP / 直接 HTTP │
└───────────────┬──────────────────────────────┬───────────┘
                │ HTTPS                        │ JSON-RPC over WS
                ▼                              ▼
┌──────────────────────────────────────────────────────────┐
│ server_dlc.py — FastAPI 入口 (:8081，/docs 已禁用 SEC-05)│
│  ├─ dlc_api/  (/dlc/tasks/* /dlc/devices/* — token 鉴权) │
│  └─ routes/   (/device/v1/app/* — 小程序设备 API)        │
└───────────────┬──────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────┐
│ dlc_core/ — 绘图/写字核心                                │
│  draw.py / write.py / dispatch.py / path_validator.py    │
│  presets.py / safety.py                                  │
└───────────────┬──────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────┐
│ device_gateway/ — Redis 任务队列 + WSS 下发到 ESP32 硬件  │
│  redis_store / coordinator / device_draw_handler / auth   │
└──────────────────────────────────────────────────────────┘
                ▲
┌───────────────┴──────────────────────────────────────────┐
│ dlc_mcp/ — JSON-RPC server (stdio ↔ WS bridge)            │
│  server.py (小智云 MCP endpoint) / mcp_pipe.py            │
└──────────────────────────────────────────────────────────┘
```

## 3. 关键模块归属（当前在用）

| 职责 | 模块 |
|------|------|
| HTTP 入口 | `server_dlc.py` |
| DLC 路由 | `dlc_api/` (`routes.py`, `app.py`, `deps.py`, `schemas.py`, `device_app_router.py`) |
| 绘图/写字核心 | `dlc_core/` (`draw.py`, `dispatch.py`, `device_status.py`, `write.py`, `path_validator.py`, `presets.py`, `safety.py`, `intent.py`) |
| MCP JSON-RPC | `dlc_mcp/` (`server.py`, `mcp_pipe.py`) |
| 设备网关 | `device_gateway/` (Redis 队列、WS、设备状态、family approval、gallery) |
| 设备 App API | `routes/` (`device_app_api.py`, `device_app_tasks.py`, `images_backends.py`, `device_app_gallery.py`) |
| 鉴权/限流 | `access_guard.py`, `rate_limiter.py`, `rate_limiter_redis.py`, `ws_ticket.py`, `device_logic/auth.py` |
| 图生 | `dashscope_image_client.py`（DashScope/wanx，经 `asyncio.to_thread` 不阻塞事件循环，调用级 `wait_for` 超时兜底） |

## 4. 请求处理链路

```
微信小程序 → server_dlc.py (/device/v1/app/*) → device_app_router 聚合
小智云 MCP → dlc_mcp/server.py (JSON-RPC) → dlc_api/routes.py (/dlc/tasks/*)
直接 HTTP → dlc_api/routes.py (verify_dlc_api_token)
所有路径 → dlc_core (handle_draw / handle_write / handle_draw_from_image)
         → dlc_core/dispatch.py → device_gateway (Redis 队列)
        → dlc_core/dispatch.py → device_gateway (Redis 队列 + WSS)
        → ESP32 固件执行运动
```

## 5. 部署拓扑

```
Internet → 阿里云 VPS 47.112.162.80 (nginx → server_dlc :8081, Redis)
                ↓ 同代码部署
         JDCloud 117.72.118.95 (备节点)
```

- 部署脚本：`scripts/deploy_unified.py`（双节点、容量感知、自动备份）
- 回滚：`/opt/dlc-drawing/backups/`
- 详见 [`docs/DEPLOY_AND_RELEASE_CONVENTION.md`](DEPLOY_AND_RELEASE_CONVENTION.md)

## 6. 已退役模块（不要按此找代码）

旧 `server.py` / `routing_engine*` / `router_v3` / `routing_executor` / `http_caller` / `context_pipeline`（代码上下文 v3.0 删）/ `session_memory` 主路径 / `observability` 主体（仅余事件模型）/ `provider_probe`（仅 JDCloud 冷离线指针）/ `backends_registry` / `chat_endpoints` / `chat_preflight` / `skills_injector` / `sticky_session` / `budget_manager` / `health_tracker` / `routing_classifier` / `routing_intent` —— 均已在 P4/P5 瘦身物理删除。退役证据见 `progress.md` 与 `docs/archive/`。

## 7. 固件与小程序

- 固件：`esp32S_XYZ/firmware/u8-xiaozhi/`（ESP32 + U1 协议 + BluFi 配网 + motion_executor 并发锁）
- 小程序：`esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/` v3.9.0（uni-app + Vue3 + TS）
- 子模块指针由父仓库 `esp32S_XYZ` gitlink 跟踪