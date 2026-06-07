# chat.donglicao 功能问题诊断报告

**日期**: 2026-06-07  
**状态**: 🔴 已诊断，待修复

---

## 问题总结

chat.donglicao 两个核心功能不可用：
1. ❌ **深度思考模式**（thinking mode）- 500 错误
2. ❌ **视频/图片模式**（vision mode）- 500 错误

---

## 根因分析

### 深度思考模式失败

**调用链**：
```
POST /v1/chat/completions (thinking: true)
  ↓
routes/chat_endpoints.py:144 - ChatRequest 解析 ✅
  ↓
routes/chat_handler.py:95 - maybe_thinking_response()
  ↓
routes/chat_support.py - thinking_route()
  ↓
router_intent.py:33 - get_thinking_backend() → "or_deepseek_r1"
  ↓
http_caller.call_api("or_deepseek_r1", ...)
  ↓
❌ 401 Unauthorized - OpenRouter API key 无效
```

**根因**：
- `THINKING_BACKENDS = ['or_deepseek_r1']`（唯一选项）
- `or_deepseek_r1` 使用 OpenRouter API（https://openrouter.ai/api/v1/chat/completions）
- **OpenRouter API key 返回 401 Unauthorized**
- 异常未被正确捕获，导致 500 错误返回给客户端

**证据**：
```bash
$ python -c "import http_caller; http_caller.call_api('or_deepseek_r1', [{'role':'user','content':'test'}], 100)"
httpx.HTTPStatusError: Client error '401 Unauthorized'
```

---

### 视频模式失败

**初步分析**：
- 视频模式通过 `detect_vision_request()` 检测
- 路由到 `vision_route()` → `VISION_BACKENDS`
- 可能也依赖失效的后端

**需要进一步诊断**：
1. VISION_BACKENDS 列表
2. 是否也有 401/403 错误
3. 是否有备用后端可用

---

## 影响范围

### 受影响功能
1. ✅ **普通对话** - 正常工作
2. ❌ **深度思考** - 完全不可用
3. ❌ **图片识别** - 完全不可用
4. ✅ **工具调用**（OpenCode）- 已修复

### 受影响用户
- chat.donglicao 所有用户
- 依赖 thinking/vision 模式的场景

---

## 解决方案

### 方案 A：修复 OpenRouter Key（推荐）

**步骤**：
1. 检查 OpenRouter 账户状态（https://openrouter.ai/）
2. 验证 API key 有效性
3. 如过期，生成新 key 并更新 `backends.py` 或环境变量
4. 重启服务

**优点**：
- 彻底解决问题
- 保留 DeepSeek R1 的深度思考能力

**缺点**：
- 需要 OpenRouter 账户访问权限

---

### 方案 B：切换到本地/免费后端（临时）

**深度思考模式**：
```python
# backends_constants.py
THINKING_BACKENDS = [
    'scnet_ds_pro',      # 已有 key，支持深度思考
    'kimi_thinking',      # Kimi 思考模式
    'or_deepseek_r1',    # 最后备选
]
```

**视频模式**：
```python
# 检查 VISION_BACKENDS 并添加本地可用后端
VISION_BACKENDS = [
    'scnet_qwen_vl',     # 如有视觉能力
    # ... 其他视觉后端
]
```

**优点**：
- 立即可用
- 不依赖外部 API key

**缺点**：
- 可能性能不如 DeepSeek R1
- 需要验证本地后端的思考/视觉能力

---

### 方案 C：优雅降级 + 错误提示

**改进错误处理**：
```python
# routes/chat_support.py - thinking_route()
async def thinking_route(...):
    thinking_backend = routing_facade.get_thinking_backend()
    try:
        result = await asyncio.to_thread(...)
        if result:
            return {"answer": result, "backend": thinking_backend}
    except BackendError as e:
        if e.status_code == 401:
            # 返回友好错误而非 500
            return {
                "answer": "[深度思考模式暂不可用：API 认证失败。请使用普通模式或联系管理员。]",
                "backend": "error",
                "error": str(e)
            }
        raise
    # 尝试备用后端...
```

**优点**：
- 用户体验更好（明确错误提示）
- 不会导致整个请求失败

**缺点**：
- 功能仍然不可用
- 治标不治本

---

## 推荐执行顺序

### 立即（< 15分钟）
1. ✅ **确认根因**（已完成）
2. 🔧 **方案 C** - 添加错误处理，防止 500 错误
3. 📊 **方案 B** - 临时切换到可用后端

### 短期（< 1小时）
4. 🔑 **方案 A** - 修复 OpenRouter key（如有访问权限）
5. ✅ 完整测试验证

---

## 技术细节

### 相关文件
- `backends_constants.py` - THINKING_BACKENDS / VISION_BACKENDS 定义
- `router_intent.py` - get_thinking_backend() 选择逻辑
- `routes/chat_support.py` - thinking_route() 调用
- `routes/chat_handler_dispatch.py` - maybe_thinking_response() 入口
- `vision_handler.py` - 视觉模式处理

### OpenRouter Backends
```
发现 12 个 OpenRouter 后端，全部使用同一个 key
示例: or_deepseek_r1, or_qwen3_coder, or_llama70b, ...
Key 前缀: sk-or-...
```

### 错误传播链
```
BackendError(401) 
  → thinking_route() 返回 None
  → maybe_thinking_response() 返回 None
  → 继续常规路由（但参数可能错误）
  → 最终 500 错误
```

---

## 后续行动

### 下一步
1. 实现方案 C（错误处理）
2. 检查 VISION_BACKENDS 是否有同样问题
3. 提供临时备用后端（方案 B）
4. 如可能，修复 OpenRouter key（方案 A）

### 验证清单
- [ ] thinking=true 请求返回友好错误（而非 500）
- [ ] 视频请求正常处理
- [ ] 备用后端可用
- [ ] 错误日志清晰明确
- [ ] VPS 环境验证
