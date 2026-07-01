# 设备 WebSocket Token 传递方式废弃时间表（M6）

## 背景

在 URL query 中携带 Bearer token（`?token=`、`?authorization=`）会进入 access log、Referer 与浏览器历史，存在凭据泄露风险。推荐路径为 **一次性 ticket**。

## 推荐方式（现行）

1. `POST /device/v1/ws/ticket`（Header: `Authorization: Bearer <device_token>`，Body: `{"device_id":"..."}`）
2. WebSocket 连接：`wss://.../device/v1/ws?ticket=<ticket>`（ticket 30s TTL、单次消费）

实现：`device_ws_ticket.py`、`routes/device_gateway_dispatch.py`（优先 `?ticket=`）。

## 支持方式

| 方式 | 状态 | 说明 |
|------|------|------|
| Header `Authorization: Bearer ...` | **支持** | 设备直连时使用 |
| Query `?ticket=` | **推荐** | 一次性 ticket，30s TTL、单次消费，防 URL 泄露 |
| Query `?token=` | **已移除** | 2026-07-02 起不再支持，防止 Bearer 进入 access log/Referer |
| Query `?authorization=` | **已移除** | 同上 |

## 时间表

| 阶段 | 日期 | 行为 |
|------|------|------|
| **Phase 0** | 2026-06-22 起 | Query token 仍可用；每次连接打 warning 日志 |
| **Phase 1** | 2026-06-29 | 默认拒绝 query token；`LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN=1` 作为临时回退 |
| **Phase 2** | **2026-07-02** | 移除 query `token`/`authorization` 分支及 `LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN` 环境变量；仅 Header Bearer + ticket |

## 迁移清单

- [x] 后端 `extract_ws_token` 移除 query token/authorization 分支
- [ ] 固件 / 小程序 / 数字人页面：改为 ticket 流程（见 `scripts/ws_ticket_http.py`）
- [ ] nginx：确认 device WS 路径 access_log 不含 query（或关闭该 location 日志）
- [ ] 生产日志检索 `token query param`，确认无活跃 legacy 客户端

## 相关代码

- `routes/device_gateway_dispatch.py` — `extract_ws_token()`
- `device_ws_ticket.py` — ticket 发放/消费
- `tests/test_device_ws_ticket.py`、`tests/test_device_gateway_dispatch.py`
