# 路由修复方案 — 解决 Claude Code 接入的根本问题

> 2026-05-20 问题总结 + 修复设计

## 一、当前问题

### 1.1 问题清单

| # | 问题 | 根因 | 影响 |
|---|------|------|------|
| 1 | 预设直答误触发 | `_try_instant_reply` 对所有请求生效，包括 IDE | Claude Code 收到"支持图片分析"等无关回复 |
| 2 | 路由到 chat_ubi | fallback 链末端是 chat_ubi，强后端熔断后 fallback 到它 | 回复质量极差 |
| 3 | 多后端熔断 | Groq/Silicon/Mistral 等返回 403/401 触发熔断器 | 可用后端骤减 |
| 4 | IDE 请求无差异化 | Anthropic 格式和普通聊天走同一路由逻辑 | IDE 用户体验差 |
| 5 | 无后端健康感知 | 不知道哪些后端当前可用 | 盲目尝试已挂的后端 |

### 1.2 请求流程（当前，有问题的）

```
Claude Code 请求 → /v1/messages
  → _try_instant_reply() → 误匹配 → 返回预设回复 ❌
  → 或: smart_router.route()
    → 尝试 groq (熔断) → silicon (熔断) → mistral (熔断)
    → ... 全部失败 ...
    → fallback 到 chat_ubi ❌
```

## 二、修复设计

### 2.1 核心原则

1. **IDE 请求和普通聊天是两条完全不同的路径**
2. **IDE 请求永远不走预设直答**
3. **IDE 请求永远不走弱后端 (chat_ubi/pollinations)**
4. **后端选择基于实时健康状态，不是固定顺序**

### 2.2 新请求流程

```
请求进入
  ├─ 判断来源:
  │   ├─ /v1/messages (Anthropic格式) → IDE 路径
  │   ├─ /v1/chat/completions + IDE UA → IDE 路径
  │   └─ /v1/chat/completions 普通 → Chat 路径
  │
  ├─ IDE 路径:
  │   ├─ 跳过 _try_instant_reply ✅
  │   ├─ 提取 system prompt 上下文
  │   ├─ Skills 注入
  │   └─ 路由到 IDE_BACKENDS (强后端池) ✅
### 2.3 IDE 后端池（强后端，不含 chat_ubi）

```python
IDE_BACKENDS = [
    'longcat_chat',       # LongCat 通用对话（稳定）
    'longcat_lite',       # LongCat 快速（轻量）
    'deepseek_flash',     # DeepSeek（代码强）
    'naga_llama70b',      # NagaAI Llama-70B（免费）
    'naga_gpt41mini',     # NagaAI GPT-4.1-mini（免费）
    'freetheai_ds',       # FreeTheAI DeepSeek-V4
    'unclose_hermes',     # UncloseAI Hermes
    # 永远不包含: chat_ubi, pollinations
]
```

### 2.4 预设直答：全部取消

~~原方案：IDE 跳过，普通聊天保留~~

**新决定：全部取消 `_try_instant_reply`。**

原因：
- 有快速模型（Groq 376ms / Cerebras），不需要预设回复
- 预设回复容易误触发（"学习这个项目" → 图片分析）
- 模型回复更自然、更准确
- 减少维护成本（不用维护正则匹配规则）

实现：直接删除 `_INSTANT_REPLIES` 列表和 `_try_instant_reply()` 函数，
以及所有调用它的地方。

### 2.5 熔断器调优

| 参数 | 当前值 | 新值 | 原因 |
|------|--------|------|------|
| 失败阈值 | 3 次 | 5 次 | 减少误熔断 |
| 恢复超时 | 60s | 30s | 更快恢复 |
| half-open 成功阈值 | 2 次 | 1 次 | 更快关闭熔断 |

## 三、实现清单

### 3.1 server.py 修改

```python
# 1. /v1/messages 入口：跳过 instant reply
@app.post("/v1/messages")
async def anthropic_messages(req: Request):
    ...
    # 删除: instant = _try_instant_reply(last_user_query)
    # IDE 请求永远不走预设直答

# 2. _handle_chat: IDE 请求强制用 IDE_BACKENDS
async def _handle_chat(...):
    if fmt == "anthropic" or ide_source in IDE_SOURCES:
        prefer = None  # 不指定单个，用 IDE 专用链
        use_ide_chain = True
    ...

# 3. 路由调用时传入 use_ide_chain
    if use_ide_chain:
        result = smart_router.route(query, ..., 
            fallback_chain=IDE_BACKENDS)
```

### 3.2 smart_router.py 修改

```python
# 1. route() 支持自定义 fallback_chain 参数
def route(query, prefer=None, ..., fallback_chain=None):
    chain = fallback_chain or FALLBACK_CHAINS.get(intent_name, DEFAULT_CHAIN)
    ...

# 2. 熔断器参数调优
CB_FAILURE_THRESHOLD = 5
CB_RECOVERY_TIMEOUT = 30
CB_SUCCESS_THRESHOLD = 1
```

## 四、验证标准

修复后必须通过以下测试：

| 测试 | 预期结果 |
|------|----------|
| Anthropic 格式 + "什么？？" | 不返回预设直答，走真实模型 |
| Anthropic 格式 + "学习这个项目" | 不返回图片分析，走真实模型 |
| Anthropic 格式 + 代码请求 | 路由到 longcat/deepseek，不走 chat_ubi |
| 普通聊天 + "你好" | 仍然走 instant reply（保留） |
| 后端熔断后 | IDE 请求在 IDE_BACKENDS 内 fallback，不穿透到 chat_ubi |

## 五、实施顺序

```
Step 1: /v1/messages 跳过 _try_instant_reply
Step 2: 定义 IDE_BACKENDS 池
Step 3: _handle_chat 区分 IDE/Chat 路径
Step 4: route() 支持自定义 fallback_chain
Step 5: 熔断器参数调优
Step 6: 重启验证
```
