# OpenCode 工具调用诊断报告

**日期**: 2026-06-07  
**测试环境**: 本地开发环境（127.0.0.1:8090）

---

## 关键发现

### ❌ 问题不是"超时"，而是性能极差 + 格式错误

| 指标 | 实测值 | 目标值 | 状态 |
|------|--------|--------|------|
| **工具调用 TTFB** | **13.25秒** | 3秒 | ❌ 超标 4.4倍 |
| **功能可用性** | ✅ 成功返回 | ✅ 可用 | ✅ 通过 |
| **响应格式** | ❌ Anthropic SSE | ✅ OpenAI SSE | ❌ 错误 |

---

## 详细测试数据

### 对照组：无工具请求
```
TTFB: 4.55s
格式: OpenAI SSE
```

### 工具调用请求
**请求**:
```json
{
  "messages": [{"role": "user", "content": "What is 2+2?"}],
  "tools": [{
    "type": "function",
    "function": {
      "name": "calculate",
      "description": "Calculate math",
      "parameters": {...}
    }
  }]
}
```

**响应时间线**:
```
[0.00s] 发送请求
[0.98s] 客户端创建
[1.01s] HTTP 200 响应头到达
[13.25s] 首个 SSE 事件到达 ⚠️ 12秒延迟
[13.91s] 流式完成
```

**响应格式**（错误）:
```json
{
  "type": "message_start",  // ❌ 这是 Anthropic 格式
  "message": {
    "id": "msg_660c7caee28447eeabdd63a4",
    "model": "agnes-1.5-flash",  // ⚠️ 实际后端不是 scnet_ds_pro
    ...
  }
}
```

**期望格式**（OpenAI）:
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion.chunk",
  "choices": [{
    "delta": {"content": "2"},
    "index": 0,
    "finish_reason": null
  }]
}
```

---

## 根因分析

### 问题 1: TTFB 13秒（vs 无工具 4.5秒）

**可能原因**:
1. **路由到了慢后端**
   - 实际使用的是 `agnes-1.5-flash`（某个 Anthropic 后端）
   - 不是配置的 `scnet_ds_pro`
   - 说明工具调用触发了不同的路由路径

2. **工具处理开销**
   - Text-tool 转换？
   - 工具 schema 验证？
   - 后端初始化？

3. **后端冷启动或负载**

### 问题 2: 返回 Anthropic 格式而非 OpenAI

**根因**:
- `opencode_direct_stream.py` 中的 `stream_openai_passthrough` 没有生效
- 或者返回的 SSE 没有经过格式转换
- 请求可能走了非 OpenCode 专用路径

**代码路径疑点**:
```python
# routes/opencode_direct_stream.py
async def stream_openai_passthrough(...):
    # 这个函数应该保证返回 OpenAI 格式
    # 但实际返回了 Anthropic 格式
```

**可能的分支**:
1. 工具请求没有被识别为 OpenCode 请求
2. 路由到了不兼容 OpenAI 格式的后端
3. SSE 转换器（`opencode_sse_adapter.py`）没有生效

---

## 修复方向

### 🔴 P0: 修复 SSE 格式错误

**目标**: 确保工具调用请求返回 OpenAI 格式 SSE

**Steps**:
1. 检查 `opencode_sse_adapter.py` 的转换逻辑
2. 确认 `stream_openai_passthrough` 是否被调用
3. 验证后端响应格式检测逻辑

**代码疑点**:
```python
# opencode_sse_adapter.py 应该有类似这样的转换：
def rewrite_sse_model(chunk: dict, backend: str) -> dict:
    if is_anthropic_format(chunk):
        return convert_anthropic_to_openai(chunk)
    return chunk
```

---

### 🔴 P0: 优化工具调用路由

**目标**: 工具调用 TTFB < 3秒

**Steps**:
1. 确认为什么路由到 `agnes-1.5-flash` 而非 `scnet_ds_pro`
2. 检查 `OPENCODE_TOOL_STABLE_BACKENDS` 是否包含正确后端
3. 增加路由日志查看决策过程

**配置检查**:
```python
# opencode_config.py
OPENCODE_PREFERRED_BACKEND = "scnet_ds_pro"  # 期望
OPENCODE_TOOL_STABLE_BACKENDS = [            # 期望
    "scnet_ds_pro",
    "scnet_ds_flash",
    "scnet_qwen235b",
    "scnet_qwen30b"
]
```

---

### 🟡 P1: 工具调用专用 fast-path

**目标**: 跳过不必要的路由开销

**优化点**:
1. 预编译工具 schema
2. 缓存路由决策
3. 并行健康检查

---

## 下一步行动

### 立即执行（2小时）

1. **定位 SSE 格式转换失败点**
   ```bash
   # 在 opencode_sse_adapter.py 中增加日志
   _log.info(f"[SSE] input format: {chunk.get('type')}")
   _log.info(f"[SSE] output format: {converted.get('object')}")
   ```

2. **定位路由到错误后端的原因**
   ```bash
   # 在 resolve_opencode_backend 中增加日志
   _log.info(f"[ROUTE] candidates: {candidates}")
   _log.info(f"[ROUTE] selected: {selected_backend}")
   ```

3. **重新测试并验证修复**

---

## 对比之前的理解

| 之前认为 | 实际情况 |
|----------|----------|
| 工具调用"超时" | 实际是"极慢"（13s） |
| 完全不可用 | 功能可用，但性能差 |
| 配置问题 | 路由 + 格式转换问题 |
| 后端不支持 | 后端支持，但格式不对 |

**结论**: 工具调用的核心逻辑是通的，但有两个严重问题需要修复：
1. 路由到了慢后端（或有额外开销）
2. 返回格式未转换（Anthropic → OpenAI）

修复这两个问题后，工具调用应该能达到 < 3s 目标。
