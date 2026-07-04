# P0 MCP 冒烟命令

## 1. 本地启动最小 dlc_api

```bash
python -m uvicorn dlc_api.app:app --host 127.0.0.1 --port 18080
```

验证：

```bash
curl -sf http://127.0.0.1:18080/health
```

期望返回：

```json
{"status":"ok","service":"dlc-drawing","version":"0.1.0-p0"}
```

任务提交验证：

```bash
curl -s http://127.0.0.1:18080/write -X POST -H "Content-Type: application/json" \
  -d '{"device_id":"dev-p0","text":"hello"}'

curl -s http://127.0.0.1:18080/draw -X POST -H "Content-Type: application/json" \
  -d '{"device_id":"dev-p0","prompt":"一只猫"}'
```

## 2. 本地运行最小 dlc_mcp server（stdio）

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
6. 实际 tool 调用由智能体对话触发；调用会经 WebSocket → stdio server → `dlc_api` → 设备任务队列。

## 5. 当前 P0 已完成范围

- `dlc_api.app`：`/health`、`/write`、`/draw`
- `dlc_mcp.server`：`dlc.write_text`、`dlc.draw_generated`
- `dlc_mcp.mcp_pipe`：WebSocket → stdio 桥接
- 聚焦测试：`tests/test_dlc_api_health.py`、`tests/test_dlc_mcp_server.py`、`tests/test_dlc_mcp_pipe.py`
- 已验证：官方云 broker 可完成 initialize → tools/list → ping 握手，并成功发现 `dlc.write_text` / `dlc.draw_generated`

## 6. 已知限制与下一步

- 官方云 broker 在握手阶段仅做 tool discovery，真实 `tools/call` 需通过智能体对话触发。
- `dlc.draw_generated` 依赖后端图像生成链路（DashScope / pollinations 等），提示词增强后 URL 可能触发 `414 Request-URI Too Large`，需后续优化 prompt 增强或改用 POST body。
- 后续可补：连接日志、断线重连、心跳、graceful shutdown。
