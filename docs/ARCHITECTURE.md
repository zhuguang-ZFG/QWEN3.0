# LiMa 系统架构（P4/P5 瘦身后）

> 更新日期：2026-07-21
> 版本：`dlc-drawing 0.4.0-p3` · Python 3.10 + FastAPI · `server_dlc:8081`

## 定位

ESP32 绘图/写字机云端控制平面：路径生成、任务下发、设备 WSS 投递。小智官方云承载对话/LLM；本仓 DLC 承载运动与设备。

## 全景

```text
小程序 / 小智 MCP / HTTP / ESP32
        │              │
        ▼              ▼
  server_dlc.py (:8081)
    dlc_api/  dlc_mcp/  routes/device_app_*  routes/device_ws
        │
        ▼
  dlc_core/ + device_gateway/
    path_workspace / path_pipeline / profiles
    delivery_reaper / redis 队列 / device_draw_handler
        │
        ▼
  ESP32 WSS (ticket → hello → drain → motion_task)
```

## 模块

| 职责 | 路径 |
|------|------|
| 入口 | `server_dlc.py` |
| DLC API | `dlc_api/`（含 `motion_payload.py`） |
| 绘图写字 | `dlc_core/` |
| MCP | `dlc_mcp/` |
| 网关 | `device_gateway/` |
| 设备 App / 语音 | `routes/device_app_*`、`device_voice/` |
| 设备 WSS | `routes/device_ws.py`、`device_ws_ticket.py` |

## 工作区优先级

1. 显式 `workspace_mm`（x/y/z 齐全且 >0）
2. 调用方 `profile` 对象
3. complete profile（`profile_id` + 正有限 workspace）
4. 有 device_id 但 incomplete → product 300×300×80
5. 无 device → DEFAULT 300×300×80

## 投递

| 状态 | 含义 |
|------|------|
| 在线 push / `sent` | WSS 已下发 |
| `queued_no_delivery` | 设备离线（诚实排队） |
| reaper | 僵尸会话 / processing 超时回收 |

## 部署

`python scripts/deploy_unified.py --target jdcloud` → 京东云 `117.72.118.95`。
约定见 [`DEPLOY_AND_RELEASE_CONVENTION.md`](DEPLOY_AND_RELEASE_CONVENTION.md)。

## 已退役

旧 `server.py` / `routing_engine*` / 多后端 chat 栈 — 代码与文档均已删除，查 git history。
