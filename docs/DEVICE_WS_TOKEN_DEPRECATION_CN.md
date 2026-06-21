# 设备 WebSocket Token 传递方式废弃时间表（M6）

## 背景

在 URL query 中携带 Bearer token（`?token=`、`?authorization=`）会进入 access log、Referer 与浏览器历史，存在凭据泄露风险。推荐路径为 **一次性 ticket**。

## 推荐方式（现行）

1. `POST /device/v1/ws/ticket`（Header: `Authorization: Bearer <device_token>`，Body: `{"device_id":"..."}`）
2. WebSocket 连接：`wss://.../device/v1/ws?ticket=<ticket>`（ticket 30s TTL、单次消费）

实现：`device_ws_ticket.py`、`routes/device_gateway_dispatch.py`（优先 `?ticket=`）。

## 兼容方式（legacy，待废弃）

| 方式 | 状态 | 日志 |
|------|------|------|
| Header `Authorization: Bearer ...` | **支持** | — |
| Query `?ticket=` | **推荐** | — |
| Query `?token=` | **deprecated** | `device WS token query param exposes secret` |
| Query `?authorization=` | **deprecated** | `authorization query param missing Bearer prefix` |

## 时间表

| 阶段 | 日期 | 行为 |
|------|------|------|
| **Phase 0** | 2026-06-22 起 | Query token 仍可用；每次连接打 warning 日志 |
| **Phase 1** | **2026-09-01** | 默认拒绝 query token；设置 `LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN=1` 可临时恢复（运维/调试） |
| **Phase 2** | **2026-12-01** | 移除 query `token`/`authorization` 分支；仅 Header Bearer + ticket |

## 迁移清单

- [ ] 固件 / 小程序 / 数字人页面：改为 ticket 流程（见 `scripts/ws_ticket_http.py`）
- [ ] nginx：确认 device WS 路径 access_log 不含 query（或关闭该 location 日志）
- [ ] 2026-08 前：生产日志检索 `token query param`，确认无活跃 legacy 客户端

## 相关代码

- `routes/device_gateway_dispatch.py` — `extract_ws_token()`
- `access_guard.py` — `WS_QUERY_PARAM_TOKEN_WARNING`
- `tests/test_device_ws_ticket.py`、`tests/test_access_guard.py`
