# P1 MCP 冒烟命令

## 1. 本地启动 dlc_api

```bash
python -m uvicorn dlc_api.app:app --host 127.0.0.1 --port 18080
```

验证：

```bash
curl -sf http://127.0.0.1:18080/health
```

期望返回：

```json
{"status":"ok","service":"dlc-drawing","version":"0.2.0-p1"}
```

任务提交验证（需先在环境变量配置 `LIMA_DEVICE_TOKENS`）：

```bash
export LIMA_DEVICE_TOKENS="test-token:dev-p0"

curl -s http://127.0.0.1:18080/dlc/tasks/dispatch \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{"type":"write_text","device_id":"dev-p0","payload":{"text":"hello"}}'

curl -s http://127.0.0.1:18080/dlc/tasks/dispatch \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{"type":"draw_generated","device_id":"dev-p0","payload":{"prompt":"一只猫"}}'
```

预览路径（不下发）：

```bash
curl -s http://127.0.0.1:18080/dlc/tasks/preview \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{"type":"draw_generated","device_id":"dev-p0","payload":{"prompt":"圆"}}'
```

## 2. 本地运行 dlc_mcp server（stdio）

```bash
python dlc_mcp/server.py
```

可用 tool：
- `dlc.write_text`
- `dlc.draw_generated`

本地直接调用示例：

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python dlc_mcp/server.py

echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"dlc.write_text","arguments":{"device_id":"dev-p0","text":"hello"}}}' | python dlc_mcp/server.py
```

## 3. 本地运行 WebSocket 桥接（mcp_pipe.py）

```bash
python dlc_mcp/mcp_pipe.py --endpoint "wss://api.xiaozhi.me/mcp/?token=<JWT>"
```

若要显式指定 stdio server 命令：

```bash
python dlc_mcp/mcp_pipe.py --endpoint "wss://api.xiaozhi.me/mcp/?token=<JWT>" -- python dlc_mcp/server.py
```

## 4. 官方云 MCP 接入实测

1. 登录 `https://xiaozhi.me`
2. 进入目标智能体 → 配置角色 → MCP 接入点
3. 复制官方给出的 endpoint：

```text
wss://api.xiaozhi.me/mcp/?token=<JWT>
```

4. 本地启动桥接：

```bash
python dlc_mcp/mcp_pipe.py --endpoint "wss://api.xiaozhi.me/mcp/?token=<JWT>"
```

5. 在小智控制台看到 `dlc.write_text` 与 `dlc.draw_generated` 即表示官方云已成功发现 tool。
6. 实际 tool 调用由智能体对话触发；调用会经 WebSocket → stdio server → `dlc_api /dlc/tasks/dispatch` → 设备任务队列。

## 5. 当前 P1 已完成范围

- `dlc_api.app`：`/health`、`/dlc/tasks/preview`、`/dlc/tasks/dispatch`
- `dlc_mcp.server`：`dlc.write_text`、`dlc.draw_generated`（内部调 `/dlc/tasks/dispatch`）
- `dlc_mcp.mcp_pipe`：WebSocket → stdio 桥接
- 聚焦测试：`tests/test_dlc_core_*.py`、`tests/test_dlc_api.py`、`tests/test_dlc_mcp_server.py`
- 已验证：21 个测试用例通过；官方云 broker 可完成 initialize → tools/list → ping 握手，并成功发现 `dlc.write_text` / `dlc.draw_generated`

## 6. 已知限制与下一步

- 官方云 broker 在握手阶段仅做 tool discovery，真实 `tools/call` 需通过智能体对话触发（Q-01）。
- `dlc.draw_generated` 在 P1 默认禁用 AI 生图，仅走预设图形/字体路径（Q-02）。
- 鉴权当前使用 `LIMA_DEVICE_TOKENS` env 兜底，per-device token 下放 P2/P3（Q-07）。
- 后续可补：连接日志、断线重连、心跳、graceful shutdown。
