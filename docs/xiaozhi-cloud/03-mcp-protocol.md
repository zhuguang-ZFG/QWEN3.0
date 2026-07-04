# MCP (Model Context Protocol) 协议文档

> 来源：https://xiaozhi.dev/docs/development/mcp/protocol/
> 抓取日期：2026-07-05

**注意**: AI 辅助生成，在实现后台服务时，请参照代码确认细节！

本项目中的 MCP 协议用于后台 API（MCP 客户端）与 ESP32 设备（MCP 服务器）之间的通信，以便后台能够发现和调用设备提供的功能（工具）。

## 协议格式

MCP 消息是封装在基础通信协议（如 WebSocket 或 MQTT）的消息体中的。其内部结构遵循 JSON-RPC 2.0 规范。

```json
{
  "session_id": "...",
  "type": "mcp",
  "payload": {
    "jsonrpc": "2.0",
    "method": "...",
    "params": { ... },
    "id": ...,
    "result": { ... },
    "error": { ... }
  }
}
```

其中 `payload` 部分是标准的 JSON-RPC 2.0 消息：

- `jsonrpc`: 固定的字符串 "2.0"
- `method`: 要调用的方法名称
- `params`: 方法的参数
- `id`: 请求的标识符，匹配请求和响应
- `result`: 方法成功执行时的结果
- `error`: 方法执行失败时的错误信息

## 交互流程

### 1. 连接建立与能力通告

- **时机**：设备启动并成功连接到后台 API 后
- **发送方**：设备
- **消息**：设备发送 "hello" 消息给后台 API

```json
{
    "type": "hello",
    "version": 3,
    "features": {
      "mcp": true
    },
    "transport": "websocket",
    "audio_params": { ... },
    "session_id": "..."
}
```

### 2. 初始化 MCP 会话

- **时机**：后台 API 收到设备 "hello" 消息，确认设备支持 MCP 后
- **发送方**：后台 API (客户端)
- **方法**：`initialize`

```json
{
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
      "capabilities": {
        "vision": {
          "url": "...",
          "token": "..."
        }
      }
    },
    "id": 1
}
```

设备响应：

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
      "protocolVersion": "2024-11-05",
      "capabilities": {
        "tools": {}
      },
      "serverInfo": {
        "name": "...",
        "version": "..."
      }
    }
}
```

### 3. 发现设备工具列表

- **方法**：`tools/list`

```json
{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {
      "cursor": ""
    },
    "id": 2
}
```

设备响应：

```json
{
    "jsonrpc": "2.0",
    "id": 2,
    "result": {
      "tools": [
        {
          "name": "self.get_device_status",
          "description": "...",
          "inputSchema": { ... }
        },
        {
          "name": "self.audio_speaker.set_volume",
          "description": "...",
          "inputSchema": { ... }
        }
      ],
      "nextCursor": "..."
    }
}
```

### 4. 调用设备工具

- **方法**：`tools/call`

```json
{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "self.audio_speaker.set_volume",
      "arguments": {
        "volume": 50
      }
    },
    "id": 3
}
```

成功响应：

```json
{
    "jsonrpc": "2.0",
    "id": 3,
    "result": {
      "content": [
        { "type": "text", "text": "true" }
      ],
      "isError": false
    }
}
```

失败响应：

```json
{
    "jsonrpc": "2.0",
    "id": 3,
    "error": {
      "code": -32601,
      "message": "Unknown tool: self.non_existent_tool"
    }
}
```

### 5. 设备主动发送消息 (Notifications)

设备可能主动发送 MCP 消息（Notification 格式，没有 `id` 字段）：

```json
{
    "jsonrpc": "2.0",
    "method": "notifications/state_changed",
    "params": {
      "newState": "idle",
      "oldState": "connecting"
    }
}
```

## 交互序列图

```
Device → BackendAPI: Hello Message (包含 "mcp": true)
BackendAPI → Device: MCP Initialize Request (method: initialize)
Device → BackendAPI: MCP Initialize Response (protocolVersion, serverInfo)
BackendAPI → Device: MCP Get Tools List Request (method: tools/list)
Device → BackendAPI: MCP Get Tools List Response (tools: [...], nextCursor)
[Optional Pagination: more tools/list exchanges]
BackendAPI → Device: MCP Call Tool Request (method: tools/call, name, arguments)
Device → BackendAPI: MCP Tool Call Response (result or error)
[Optional: Device → BackendAPI: MCP Notification]
```