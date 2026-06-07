# OpenCode 工具调用修复进度报告

**日期**: 2026-06-07  
**状态**: 🟡 进行中（格式问题已修复，性能优化中）

---

## ✅ 已完成：格式问题修复

### 问题诊断

1. **格式错误**：返回 Anthropic SSE 格式而非 OpenAI 格式
2. **根因**：
   - Anthropic 后端使用 `event:` + `data:` 两行格式
   - `opencode_direct_stream.py` 只处理 `data:` 行，`event:` 行直接透传
   - 测试脚本缺少 `User-Agent: OpenCode` 头，未走 OpenCode 专用路径

### 修复方案

**1. opencode_protocol_adapter.py** - 新增 Anthropic → OpenAI 转换
```python
def _convert_anthropic_to_openai(chunk: dict) -> dict:
    # 转换 message_start, content_block_delta 等
    # → OpenAI chat.completion.chunk 格式
```

**2. routes/opencode_direct_stream.py** - 跳过 event: 行
```python
if line.startswith("event: "):
    current_event = line[7:].strip()
    continue  # 不透传，只处理 data: 行
```

**3. scripts/diagnose_tool_call.py** - 添加 OpenCode User-Agent
```python
headers = {
    "User-Agent": "OpenCode/1.0",  # 触发专用路径
}
```

### 验证结果

✅ **格式正确**：
```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion.chunk",
  "model": "lima-1.3",
  "choices": [{"index": 0, "delta": {"role": "assistant"}}]
}
```

---

## 🔧 进行中：性能优化

### 当前性能

| 指标 | 实测 | 目标 | 状态 |
|------|------|------|------|
| TTFB（工具调用）| 3.66-5.23秒 | < 3秒 | 🟡 接近 |
| 格式 | OpenAI ✅ | OpenAI | ✅ |
| 功能 | 可用 ✅ | 可用 | ✅ |

### 性能问题诊断中

**可能原因**：
1. 路由到了非最优后端
2. scnet_ds_pro 可能被跳过（健康检查/Key可用性）
3. 需要增加路由日志确认实际选择

**下一步**：
1. 增加详细路由日志（已添加）
2. 重启服务测试
3. 如 scnet_ds_pro 不可用，尝试 groq/cerebras 快速后端
4. 目标：TTFB < 3秒

---

## 📊 修复进度

### 完成度：70%

- ✅ 格式转换（主要问题）
- ✅ User-Agent 检测
- ✅ event: 行过滤
- 🔧 性能优化（进行中）
- ⏳ VPS 验证
- ⏳ 完整测试套件

### 提交记录

1. **commit 2782a43** - 工具调用诊断
2. **commit 77ae537** - 格式修复（Anthropic → OpenAI）
3. **WIP** - 路由优化和性能提升

---

## 🎯 下一步行动

### 立即（< 30分钟）

1. 重启服务查看路由日志
2. 确认实际选择的后端
3. 如需要，切换到更快后端（groq_llama70b/cerebras_qwen235b）
4. 达到 TTFB < 3秒目标

### 短期（1小时）

5. 本地完整测试验证
6. VPS 部署和验证
7. 更新性能基线报告

---

## 📈 对比修复前后

| 项目 | 修复前 | 修复后 |
|------|--------|--------|
| **格式** | Anthropic ❌ | OpenAI ✅ |
| **TTFB** | 13.3秒 ❌ | 3.66-5.23秒 🟡 |
| **功能** | 可用但格式错 | 完全可用 ✅ |

**改进幅度**：
- 格式：从错误 → 正确
- 性能：提升 2.5-3.6倍（13.3s → 3.66s）
- 距离目标：还差 0.66-2.23秒

---

## 🔍 技术洞察

1. **OpenCode 路由关键**：必须有 `User-Agent: OpenCode` 才走专用路径
2. **SSE 格式差异**：Anthropic 用 `event:` + `data:`，OpenAI 只用 `data:`
3. **TEXT_TOOL_BACKENDS**：scnet_ds_pro 在这个列表中，支持文本工具转换
4. **路由优先级**：TOOL_STABLE_BACKENDS → PREFERRED → FAST_BACKENDS
