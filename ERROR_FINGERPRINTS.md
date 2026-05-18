# AI 编程工具 — 错误指纹数据库

> 用于路由模型：错误消息格式是强信号，每工具独有不重叠
> 提取日期: 2026-05-18

---

## Claude Code

### 工具验证错误
```
InputValidationError: Write failed due to the following issues:
The required parameter `file_path` is missing
The required parameter `content` is missing

InputValidationError: Bash failed due to the following issue:
The required parameter `command` is missing

InputValidationError: Edit failed — old_string must be unique in file
```

### 文件系统错误
```
File has been modified since read, either by the user or by a linter.
Read it again before attempting to edit.

File does not exist. Note: your current working directory is ...

File unchanged since last read. The content from the earlier Read
tool_result in this conversation is still current.

Wasted call — file unchanged since your last Read.
```

### MCP 错误
```
MCP error -32603: fetch failed
MCP error -32603: Error calling LongCat API: HTTP Error 404: Not Found
Connection error.
[Tool backend error: No endpoints found for ...]
```

### 权限/安全
```
Permission for this action was denied by the Claude Code auto mode classifier.
Reason: ...
```

### Git 错误
```
Exit code 1 / Exit code 2 / Exit code 128
```

---

## Cursor

### 模型/API 错误
```
ERROR_MODEL_NO_LONGER_SUPPORTED
ERROR_NOT_HIGH_ENOUGH_PERMISSIONS
NOT_LOGGED_IN
AGENT_REQUIRES_LOGIN
AUTH_TOKEN_NOT_FOUND
AUTH_TOKEN_EXPIRED
INVALID_AUTH_ID
UNAUTHORIZED
```

### Hook 执行错误
```
Error executing postToolUse hook
Error executing postToolUseFailure hook
Error executing subagentStart hook
Error executing subagentStop hook (success case)
Error executing subagentStop hook (error case)
Error executing subagentStop hook (post-execution error case)
Error closing tool call stream
```

### 工具调用错误
```
Error in call_mcp_tool: ... without reading the tool definition
Error running tool: ...
BAD_USER_DEVICE_STATE
OTHER_ERROR
```

### 认证/账户
```
NOT_LOGGED_IN
AGENT_REQUIRES_LOGIN
AUTH_TOKEN_NOT_FOUND
AUTH_TOKEN_EXPIRED
NOT_HIGH_ENOUGH_PERMISSIONS
```

---

## Codex

### API/模型错误
```
(从 70K 日志中提取的 WARN/ERROR 模式)
codex_protocol::openai_models: model not found / unsupported
codex_core::session::turn: turn failed
codex_app_server::outgoing_message: failed to send
codex_client::transport: connection error / timeout
```

### 沙箱错误
```
sandbox_mode is `read-only`: The sandbox only permits reading files.
sandbox_mode is `workspace-write`: Editing files in other directories requires approval.
Filesystem sandboxing defines which files can be read or written.
Network access is restricted.
```

### 权限/升级
```
Escalation Requests: Commands are run outside the sandbox if approved.
Permission denied for this action.
```

### 状态管理
```
state db backfill not complete
timed out waiting for state db backfill
```

---

## Kiro

### 认证错误
```
external_idp_token_exchange
invalid_token
access_token
id_token
```

### 流/模型错误
```
invalid_tool_call / invalid_tool_calls
invalid_type_error
Stream completed without receiving ...
```

### LangChain 错误
```
lc_error_code
lc_direct_tool_output
error_utilization_penalty
```

---

## 路由特征：一行区分

```python
ERROR_ROUTING = {
    "claude": [
        "InputValidationError:",       # 独有错误类型名
        "MCP error -32603:",           # JSON-RPC 错误码
        "File has been modified since read",  # 独有措辞
        "Wasted call",                 # 独有提示
        "File unchanged since last read",  # 独有措辞
    ],
    "cursor": [
        "ERROR_MODEL_NO_LONGER_SUPPORTED",  # 全大写蛇形
        "ERROR_NOT_HIGH_ENOUGH_PERMISSIONS",
        "Error executing postToolUse hook",  # Hook 相关
        "Error executing subagentStart hook",
        "NOT_LOGGED_IN",               # 全大写
        "AUTH_TOKEN_EXPIRED",
    ],
    "codex": [
        "sandbox_mode is",             # 沙箱概念
        "state db backfill",           # 内部状态管理
        "Escalation Requests",         # 升级请求概念
        "codex_protocol::openai_models",  # Rust 模块路径
        "Filesystem sandboxing defines",  # 独有措辞
    ],
    "kiro": [
        "lc_error_code",               # LangChain 前缀
        "lc_direct_tool_output",
        "external_idp_token_exchange", # AWS IAM 认证
        "invalid_tool_calls",          # 复数形式
    ],
}
```

---

## 错误格式风格差异

| 风格 | Cursor | Codex | Claude Code | Kiro |
|------|--------|-------|-------------|------|
| 常量命名 | `UPPER_SNAKE` | 无 | 无 | 无 |
| 错误类型 | 枚举值 | Rust模块路径 | 类名+描述 | LangChain前缀 |
| Hook错误 | `Error executing X hook` | 无 | 无 | 无 |
| 文件描述 | 标准 | "sandbox"概念 | "modified since read" | 标准 |
| MCP错误 | `Error in call_mcp_tool` | 无 | `MCP error -32603` | `invalid_tool_call(s)` |
| 认证 | `NOT_LOGGED_IN` 等枚举 | `device-auth` | `ANTHROPIC_API_KEY` | `idp_token_exchange` |
