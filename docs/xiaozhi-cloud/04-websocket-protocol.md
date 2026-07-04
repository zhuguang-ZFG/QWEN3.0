# WebSocket 通信协议

> 来源：https://xiaozhi.dev/docs/development/websocket/
> 抓取日期：2026-07-05

## 总体流程

1. 建立连接（Connect）
2. 设备发送 `hello`（包含版本/传输方式/音频参数）
3. 服务器回 `hello` 确认
4. 双向传输：
   - 二进制：Opus 音频帧
   - 文本：状态、TTS/STT、命令（JSON）

## 参考

- 结合实际后端服务对接，确认鉴权头、心跳机制与超时处理策略
- 相关协议：MQTT+UDP、MCP 协议