# OpenCode + LiMa 集成指南

将 [OpenCode](https://opencode.ai) 连接到 LiMa Server，获得 **180+ AI 后端自动路由** 的终端编码体验。

## 为什么用 OpenCode + LiMa？

| 能力 | OpenCode 原生 | OpenCode + LiMa |
|------|:---:|:---:|
| 可用后端数 | 75+ providers | **180+ 后端**，自动健康检查与路由 |
| 模型切换 | 手动 `/models` | **自动路由**，无需手动切模型 |
| 后端 fallback | 无 | **3 级 fallback 链**，永不中断 |
| 编码质量 | 取决于所选模型 | **智能选择最强 coding 后端** |
| 工具调用 | 标准 OpenAI | **多后端工具转发**，兼容 14+ 工具后端 |
| 上下文优化 | 自行管理 | **自动上下文压缩与注入** |
| 会话记忆 | 本地 SQLite | **服务端会话持久化** |

## 快速开始

### 1. 获取 LiMa API Key

联系管理员在 [LiMa 管理面板](/admin) 的「客户端 Key 管理」中发放一个 Key。

### 2. 配置 OpenCode

在 `~/.config/opencode/opencode.json`（Linux/macOS）或 `%APPDATA%\opencode\opencode.json`（Windows）中添加：

```json
{
  "model": "openai/lima-1.3",
  "provider": {
    "openai": {
      "baseURL": "https://chat.donglicao.com/v1",
      "apiKey": "<你的 LIMA_API_KEY>"
    }
  }
}
```

或者在 TUI 中通过 `/connect` 命令交互式配置。

### 3. 启动

```bash
cd /path/to/your/project
opencode
```

首次使用建议运行 `/init` 让 OpenCode 分析项目结构。

## 推荐配置

```json
{
  "model": "openai/lima-1.3",
  "provider": {
    "openai": {
      "baseURL": "https://chat.donglicao.com/v1",
      "apiKey": "<你的 LIMA_API_KEY>",
      "timeout": 300000,
      "chunkTimeout": 30000
    }
  }
}
```

| 配置项 | 推荐值 | 说明 |
|--------|--------|------|
| `timeout` | `300000` (5 分钟) | 复杂编码任务可能需要较长处理时间 |
| `chunkTimeout` | `30000` (30 秒) | 流式块间超时，匹配 LiMa 默认值 |
| `model` | `openai/lima-1.3` | 使用 LiMa 自动路由；也可指定具体模型如 `openai/claude-sonnet-4` |

## LiMa 后端优化

当使用 OpenCode 连接 LiMa 时，LiMa 后端会自动：

- **识别 OpenCode 客户端**：通过请求特征自动检测，无需额外配置
- **IDE 级路由质量**：享受 OpenCode IDE 专属的高质量后端池和优化路由
- **5x 速率限制**：IDE 客户端获得更高的请求配额
- **编码场景优化**：自动走 coding 专用路由路径

### 环境变量配置

在 LiMa Server 的 `.env` 中配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LIMA_OPENCODE_MODEL_LIST` | `0` | 设为 `1` 启用 OpenCode 专属模型列表（/v1/models 返回 coding 精选模型） |
| `LIMA_OPENCODE_SKILLS` | `0` | 设为 `1` 启用 OpenCode Skills 注入（全类别 skill 补缺） |
| `LIMA_OPENCODE_TOOL_MODE` | `direct` | 默认启用工具调用直通模式（原生 OpenAI 格式）；设为 `convert` 走 Anthropic 转换管线 |
| `LIMA_OPENCODE_OVERFLOW` | `1` | 设为 `0` 禁用 overflow 检测（上下文溢出自动处理） |
| `LIMA_OPENCODE_NORMALIZE` | `1` | 设为 `0` 禁用消息规范化（surrogate 清理、toolCallId 适配） |
| `LIMA_OPENCODE_USAGE` | `1` | 设为 `0` 禁用 usage token 用量追踪 |
| `LIMA_OPENCODE_SESSION_AFFINITY` | `1` | 设为 `0` 禁用 x-session-affinity 会话亲和性 |

### 高级功能

#### Overflow 上下文溢出自动处理

当对话上下文超过后端模型限制时，LiMa 会自动：
1. 检测 18+ 种 overflow 错误模式（正则匹配）
2. 返回 HTTP 413 状态码（非流式）或 SSE error event（流式）
3. 附带清晰的溢出提示消息，帮助用户理解原因

OpenCode 会正确处理这些错误，不会崩溃或产生混乱的错误信息。

#### 消息规范化管线

LiMa 自动处理 OpenCode 消息中的兼容性问题：
- **Surrogate 清理**：移除 Unicode surrogate pairs（某些模型不支持）
- **toolCallId 适配**：为缺失 `tool_call_id` 的 tool 消息自动生成 ID
- **content part 过滤**：移除空的 content part，避免后端报错

#### x-session-affinity 会话亲和性

LiMa 通过 `x-session-affinity` header 实现会话粘性，确保同一对话的请求路由到同一后端，避免上下文丢失。

#### reasoning_effort 参数透传

对于支持 reasoning 的模型（如 Claude、DeepSeek），LiMa 会透传 OpenCode 的 `reasoning_effort` 参数，控制模型的推理深度。

#### Usage Token 用量追踪

LiMa 在响应中注入 `x-lima-usage` header，包含：
- `prompt_tokens`：输入 token 数
- `completion_tokens`：输出 token 数
- `total_tokens`：总 token 数
- `model`：实际使用的后端模型

OpenCode 可以读取这些信息来跟踪 token 消耗。

## 从 LiMa CLI 迁移

| LiMa CLI | OpenCode |
|---------------|----------|
| `/lima vibe` 工作流 | `Tab` 切换 Plan 模式 → 描述需求 |
| `/model` 切换模型 | `/models` 或自动路由 |
| Skills 系统 (`~/.agents/skills/`) | OpenCode agents (`.opencode/agents/`) |
| MCP 配置 (`mcpServers`) | OpenCode MCP (`mcp` 配置) |
| `/init` 初始化 | `/init` 相同命令 |
| `/undo` 撤销 | `/undo` 相同命令 |
| 通知 (`notify` 脚本) | OpenCode `attention` 设置 |
| 图片粘贴 `Ctrl+V` | 拖拽图片到终端 |
| LiMa Server 接入 | 同左，完全兼容 |

## 常见问题

### OpenCode 需要什么版本的 LiMa？

LiMa v2.0+ 即可。OpenCode 使用标准 OpenAI `/v1/chat/completions` 端点，与 LiMa 完全兼容。

### 可以用多个模型吗？

可以。LiMa 的 `lima-1.3` 模型名会自动路由到最优后端。你也可以在 OpenCode 中指定具体模型名（如 `openai/claude-sonnet-4`），LiMa 会直接使用对应的后端。

### 工具调用是否正常？

正常。OpenCode 发送标准 OpenAI 格式的 `tools` 数组，LiMa 通过 tool_forward 管道转发到支持工具调用的后端。如需原生 OpenAI 格式响应，可启用 `LIMA_OPENCODE_TOOL_MODE=direct`。

### LiMa CLI 还能用吗？

LiMa CLI 已进入维护模式，不再进行活跃开发。推荐迁移到 OpenCode。

### 出现“上下文溢出”错误怎么办？

当对话过长时，LiMa 会返回 overflow 错误。解决方案：
1. 在 OpenCode 中使用 `/clear` 清空当前对话
2. 或者拆分任务，分多次对话完成
3. 如果不需要 overflow 自动处理，可以在 LiMa Server 的 `.env` 中设置 `LIMA_OPENCODE_OVERFLOW=0`

### 流式响应中断怎么办？

如果流式响应中途停止，可能是：
1. 网络不稳定导致连接超时
2. 后端模型响应时间过长
3. 可以尝试增加 OpenCode 的 `chunkTimeout` 配置值
