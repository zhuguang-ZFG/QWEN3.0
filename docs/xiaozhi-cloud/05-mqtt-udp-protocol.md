# MQTT + UDP 混合通信协议

> 来源：https://xiaozhi.dev/docs/development/mqtt-udp/
> 抓取日期：2026-07-05

## 1. 协议概览

- **MQTT**：用于控制消息、状态同步、JSON 数据交换
- **UDP**：用于实时音频数据传输，支持加密

### 特点

- 双通道设计：控制与数据分离
- 加密传输：UDP 音频数据使用 AES-CTR 加密
- 序列号保护：防止数据包重放和乱序
- 自动重连：MQTT 连接断开时自动重连

## 2. 总体流程

1. 建立 MQTT 连接
2. 请求音频通道（Hello 消息交换）
3. 建立 UDP 连接
4. 音频数据传输（加密 Opus）
5. 控制消息交换（MQTT）
6. 关闭连接

## 3. MQTT 控制通道

### Hello 消息交换

设备端发送：

```json
{
  "type": "hello",
  "version": 3,
  "transport": "udp",
  "features": {
    "mcp": true
  },
  "audio_params": {
    "format": "opus",
    "sample_rate": 16000,
    "channels": 1,
    "frame_duration": 60
  }
}
```

服务器响应：

```json
{
  "type": "hello",
  "transport": "udp",
  "session_id": "xxx",
  "audio_params": {
    "format": "opus",
    "sample_rate": 24000,
    "channels": 1,
    "frame_duration": 60
  },
  "udp": {
    "server": "192.168.1.100",
    "port": 8888,
    "key": "0123456789ABCDEF0123456789ABCDEF",
    "nonce": "0123456789ABCDEF0123456789ABCDEF"
  }
}
```

### JSON 消息类型

**设备端→服务器：**
- Listen 消息：`{"type": "listen", "state": "start", "mode": "manual"}`
- Abort 消息：`{"type": "abort", "reason": "wake_word_detected"}`
- MCP 消息：`{"type": "mcp", "payload": {"jsonrpc": "2.0", ...}}`
- Goodbye 消息：`{"type": "goodbye"}`

**服务器→设备端：**
- STT：语音识别结果
- TTS：语音合成控制
- LLM：情感表达控制
- MCP：物联网控制
- System：系统控制
- Custom：自定义消息

## 4. UDP 音频通道

### 加密音频包结构

```
|type 1byte|flags 1byte|payload_len 2bytes|ssrc 4bytes|timestamp 4bytes|sequence 4bytes|
|payload payload_len bytes|
```

- `type`：数据包类型，固定为 0x01
- `payload`：加密的 Opus 音频数据

### 加密算法

使用 AES-CTR 模式加密：
- 密钥：128位，由服务器提供
- 随机数：128位，由服务器提供
- 计数器：包含时间戳和序列号信息

### 序列号管理

- 发送端：`local_sequence_` 单调递增
- 接收端：`remote_sequence_` 验证连续性
- 防重放：拒绝序列号小于期望值的数据包

## 5. 配置参数

### MQTT 配置

- `endpoint`：MQTT 服务器地址
- `client_id`：客户端标识符
- `username`/`password`：认证凭据
- `keepalive`：心跳间隔（默认240秒）
- `publish_topic`：发布主题

### 音频参数

- 格式：Opus
- 采样率：16000 Hz（设备端）/ 24000 Hz（服务器端）
- 声道数：1（单声道）
- 帧时长：60ms

## 6. 与 WebSocket 协议比较

| 特性 | MQTT + UDP | WebSocket |
|------|-----------|-----------|
| 控制通道 | MQTT | WebSocket |
| 音频通道 | UDP (加密) | WebSocket (二进制) |
| 实时性 | 高 (UDP) | 中等 |
| 可靠性 | 中等 | 高 |
| 复杂度 | 高 | 低 |
| 加密 | AES-CTR | TLS |
| 防火墙友好度 | 低 | 高 |