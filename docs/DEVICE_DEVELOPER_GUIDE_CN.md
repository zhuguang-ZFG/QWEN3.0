# 设备开发者入口

> 更新日期：2026-07-21

## 闭环

1. [`ARCHITECTURE.md`](ARCHITECTURE.md) — 链路与工作区
2. [`DEVICE_WS_TOKEN_DEPRECATION_CN.md`](DEVICE_WS_TOKEN_DEPRECATION_CN.md) — ticket
3. [`release_evidence/TEMPLATE_AI_TO_MOTION_RELEASE.md`](release_evidence/TEMPLATE_AI_TO_MOTION_RELEASE.md)
4. [`../STATUS.md`](../STATUS.md) — 当前待办

## 关键代码

| 路径 | 用途 |
|------|------|
| `routes/device_ws.py` | WSS hello / drain / push |
| `device_ws_ticket.py` | 设备 ticket |
| `device_gateway/delivery_reaper.py` | 投递 reaper |
| `device_gateway/path_workspace.py` | 工作区 |
| `device_gateway/path_pipeline.py` | path 渲染 |
| `device_gateway/profiles.py` | profile complete |
| `device_gateway/task_draw_params.py` | draw_generated |
| `device_gateway/device_draw_handler.py` | 生图→SVG |
| `routes/device_app_voice*.py` | 小程序语音 |

## 热路径

```text
tasks → build_run_params_async → render_*(device_id) → run_path
     → 在线 WSS push / 离线 queued_no_delivery
```

默认画布 300×300×80 mm。complete = 非空 `profile_id` + 正有限 workspace。

## 仿真

```powershell
$env:FZ_ROOT='D:\Users\zhugu\fz'
python $env:FZ_ROOT\scripts\agent_gate.py --profile standard
```

真机须连 `wss://…/device/v1/ws?ticket=` 并 hello。
