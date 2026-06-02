# Tool Calling 管道改善优化

> 2026-06-03 · 设计文档 · Superpowers 原则1（文档先行）

## 背景

LiMa 工具调用管道已实现双协议（OpenAI/Anthropic）、双梯队（Tier1 OpenAI → Tier2 Anthropic-native）、
流式/非流式、文本提取等核心能力。经代码审查发现 7 个需改善的问题。

## 改善清单

### Task 1: tool_choice 尊重客户端请求 [Critical]

**问题**: `tool_forward.py` L139 和 `tool_forward_stream.py` L204 硬编码 `"tool_choice": "auto"`，
忽略客户端传入的 `tool_choice` 参数。IDE 客户端（Claude Code/Cursor）常发
`tool_choice: {"type": "tool", "name": "Read"}` 来强制使用特定工具。

**修复**:
1. `routes/tool_forward.py` — `anthropic_native_forward_sync()` 中从 `body` 提取 `tool_choice` 并传入 `req_body`
2. `routes/tool_forward_stream.py` — `stream_tier1_openai()` 同样从 `body` 提取
3. `converters/anthropic_format.py` — 新增 `convert_tool_choice_anthropic_to_openai()` 转换器
4. `routes/chat_endpoints.py` — `_openai_to_anthropic_tool_body()` 传递 `tool_choice`

### Task 2: 变量遮蔽修复 [Critical]

**问题**: `tool_forward_stream.py` L259 `body = await http_resp.aread()` 遮蔽了函数参数 `body`，
若异常后引用 `body` 将得到 HTTP 响应体而非请求体。

**修复**: 重命名为 `err_body = await http_resp.aread()`。

### Task 3: Tier2 SSE passthrough 格式修复 [High]

**问题**: `tool_forward_stream.py` L267 `yield line + "\n\n"` 对每行 SSE 都追加 `\n\n`，
导致 `event:` 和 `data:` 之间被插入空行，违反 SSE 协议规范。

**修复**: 改为事件级缓冲——累积行直到空行，然后一次 yield 完整事件。

### Task 4: 请求体大小限制提升 [High]

**问题**: `tool_forward.py` L120 和 `tool_forward_stream.py` L25 的 100KB 限制过于保守。
IDE 工具请求携带完整文件内容时经常超过 100KB。

**修复**: 提升到 512KB（524288 字节），并通过环境变量 `LIMA_TOOL_BODY_LIMIT` 可配置。

### Task 5: 工具请求统计记录 [Medium]

**问题**: `chat_endpoints.py` 中工具请求直接走 tool_forward 管道，不调用 `record_request`，
导致管理面板看不到工具调用统计。

**修复**: 在工具请求处理前后添加 `record_request` 调用。

### Task 6: _extract_text_tools_from_response 去重 [Low]

**问题**: `tool_forward.py` L334-389 的 `_extract_text_tools_from_response` 与
`text_tool_extractor.py` 的 `extract_tool_calls_from_text` 功能重叠。

**修复**: 删除 `_extract_text_tools_from_response`，改为调用 `text_tool_extractor.extract_tool_calls_from_text`。

### Task 7: 添加/更新测试 [验证]

为 Task 1-6 添加测试用例：
- `test_tool_choice_passthrough`: 验证 tool_choice 从客户端传递到后端请求
- `test_tool_body_size_limit_env`: 验证环境变量配置
- `test_tool_request_recording`: 验证统计记录
- 修复 `test_tier2_sse_format`: 验证 SSE 格式正确性

## 执行顺序

```
Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7（验证）
```

Task 1-3 为 Critical/High 优先级，必须修复。
Task 4-6 为 Medium/Low，可渐进处理。
Task 7 为所有改动的测试验证。

## 预期影响

- IDE 工具调用准确性提升（tool_choice 尊重客户端意图）
- 大型项目工具请求不再被错误跳过 Tier1（512KB 限制）
- Tier2 流式不再产生协议违规 SSE
- 管理面板可见工具调用统计
