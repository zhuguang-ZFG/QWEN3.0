# 小智官方云文档（本地缓存）

> 来源：https://xiaozhi.dev/docs/
> 抓取日期：2026-07-05
> 用途：LiMa 瘦身方案参考——小智云负责语音/对话/LLM，LiMa 收缩为绘图/写字 MCP 核心。

## 文档索引

| 文件 | 来源 URL | 内容 |
|------|---------|------|
| `01-docs-center.md` | https://xiaozhi.dev/docs/ | 文档中心首页、导航、性能指标 |
| `02-mcp-usage.md` | https://xiaozhi.dev/docs/development/mcp/usage/ | MCP 协议使用指南、设备端 AddTool、JSON-RPC 示例 |
| `03-mcp-protocol.md` | https://xiaozhi.dev/docs/development/mcp/protocol/ | MCP 协议交互流程、initialize/tools-list/tools-call、序列图 |
| `04-websocket-protocol.md` | https://xiaozhi.dev/docs/development/websocket/ | WebSocket 通信协议、Hello 握手、音频帧 |
| `05-mqtt-udp-protocol.md` | https://xiaozhi.dev/docs/development/mqtt-udp/ | MQTT+UDP 混合协议、加密音频、状态机 |
| `06-faq.md` | https://xiaozhi.dev/docs/usage/faq/ | 常见问题、硬件/固件/功能/使用 |

## 关键结论（对本项目）

1. **MCP 是小智官方推荐的设备控制协议**，通过 JSON-RPC 2.0 在后台与设备间发现和调用工具。
2. **设备端通过 `AddTool` 注册工具**，工具名建议 `self.模块.功能` 命名风格。
3. **后台通过 `tools/list` 发现工具、`tools/call` 调用工具**，支持分页。
4. **外部 MCP 服务可通过 `mcp-endpoint-server` 接入**（https://github.com/xinnan-tech/mcp-endpoint-server）。
5. **小智云支持 DeepSeek/Qwen/豆包等大模型切换**，通过管理后台配置。
6. **本项目 DLC 绘图服务应暴露**：
   - `dlc.write_text(text)` — 服务端 MCP tool
   - `dlc.draw_generated(prompt)` — 服务端 MCP tool
   - `self.plotter.run_path(path)` — 设备端 MCP tool（执行路径）