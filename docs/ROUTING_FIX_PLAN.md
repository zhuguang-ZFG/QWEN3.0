# 路由重新设计方案 — 三层架构

> 2026-05-20 完整重设计（替代原有 fallback 链逻辑）

## 一、当前问题（为什么要重设计）

| 问题 | 根因 | 影响 |
|------|------|------|
| 预设直答误触发 | 正则匹配用户内容 | Claude Code 收到无关回复 |
| 路由到 chat_ubi | 单一 fallback 链末端是弱后端 | 回复质量极差 |
| 多后端熔断 | 熔断器太激进(3次) | 可用后端骤减 |
| IDE 无差异化 | 所有请求走同一逻辑 | IDE 用户体验差 |
| 死模型 | 固定优先级 | 底部后端从不被调用 |
| 职责混乱 | 逻辑散落两个文件 | 难以维护和理解 |

## 二、新架构：三层分离

```
┌───────────────────────────────────────────────┐
│ Layer 1: 请求分类器 (Request Classifier)       │
│   输入: 路径 + UA + body                       │
│   输出: request_type + language + complexity   │
│   耗时: <1ms (纯本地计算)                      │
└───────────────────┬───────────────────────────┘
                    ▼
┌───────────────────────────────────────────────┐
│ Layer 2: 后端选择器 (Backend Selector)         │
│   输入: request_type + health_map             │
│   逻辑: 从对应 Pool 选健康后端(同层随机)       │
│   输出: [backend1, backend2, ...] 有序列表     │
│   耗时: <1ms                                   │
└───────────────────┬───────────────────────────┘
                    ▼
┌───────────────────────────────────────────────┐
│ Layer 3: 执行器 (Executor)                     │
│   逻辑: Skills注入 → 模型专属prompt → 调用     │
│   失败: 换下一个后端重试                       │
│   全失败: 诚实告知"暂时不可用"                 │
│   耗时: 取决于后端(300ms-5s)                   │
└───────────────────────────────────────────────┘
```

## 三、Layer 1: 请求分类器

### 3.1 分类逻辑（看元数据，不看内容）

```python
def classify_request(path: str, headers: dict, body: dict) -> dict:
    """分类请求，不依赖正则匹配内容"""
    # 1. 请求格式判断
    if path.startswith("/v1/messages"):
        request_type = "ide"
    elif "claude-code" in headers.get("user-agent", "").lower():
        request_type = "ide"
    elif "cursor" in headers.get("user-agent", "").lower():
        request_type = "ide"
    elif has_image_blocks(body):
        request_type = "vision"
    elif is_image_gen_intent(body):
        request_type = "image"
    else:
        request_type = "chat"

    # 2. 语言检测（用于 Skills 注入）
    language = detect_language(body.get("messages", []))

    # 3. 复杂度估算
    total_tokens = estimate_tokens(body)
    complexity = "high" if total_tokens > 4000 else "low"

    return {
        "type": request_type,
        "language": language,
        "complexity": complexity,
    }
```

### 3.2 不再有预设直答

删除 `_try_instant_reply()` 和 `_INSTANT_REPLIES`。
所有请求走真实模型。有快速模型(Groq 376ms)兜底。

## 四、Layer 2: 后端池（Pool）+ 健康感知选择

### 4.1 后端池定义

```python
POOLS = {
    "ide": {
        "strong": ["longcat_chat", "deepseek_flash", "naga_llama70b"],
        "medium": ["naga_gpt41mini", "freetheai_ds", "unclose_hermes"],
        "floor":  ["longcat_lite"],
        # 永远不含: chat_ubi, pollinations
    },
    "chat": {
        "strong": ["longcat_chat", "deepseek_flash"],
        "medium": ["naga_llama70b", "unclose_hermes", "freetheai_ds"],
        "floor":  ["chat_ubi", "pollinations"],
    },
    "vision": {
        "strong": ["longcat_omni"],
        "floor":  ["pollinations"],
    },
    "image": {
        "strong": ["pollinations"],
    },
}
```

### 4.2 选择逻辑

```python
def select_backends(request_type: str, health_map: dict) -> list:
    """从对应 Pool 选健康后端，同层随机"""
    pool = POOLS[request_type]
    result = []
    for tier in ["strong", "medium", "floor"]:
        candidates = pool.get(tier, [])
        healthy = [b for b in candidates if health_map.get(b) != "dead"]
        random.shuffle(healthy)  # 同层随机，消除死模型
        result.extend(healthy)
    return result
```

### 4.3 关键设计决策

| 决策 | 原因 |
|------|------|
| IDE floor 是 longcat_lite 不是 chat_ubi | IDE 用户永远不该收到垃圾回复 |
| 同层随机 | 避免固定优先级导致底部后端从不被调用 |
| 只选非 dead 后端 | 不浪费时间尝试已知挂掉的后端 |
| 全部失败返回诚实错误 | 不降级到不可接受的质量 |

## 五、Layer 3: 执行器

### 5.1 执行流程

```python
def execute(backends: list, messages: list, context: dict) -> str:
    # 1. Skills 注入
    if context["type"] == "ide" or context["language"]:
        messages = inject_skills(messages, context["language"])

    # 2. 按顺序尝试后端
    for backend in backends:
        # 模型专属 prompt 调整
        final_msgs = apply_model_hints(messages, backend)
        response = call_backend(backend, final_msgs)

        # 质量检查
        if response and len(response.strip()) > 10:
            update_health(backend, success=True)
            return response
        else:
            update_health(backend, success=False)

    # 3. 全部失败
    return "当前服务暂时不可用，请稍后重试。"
```

### 5.2 Skills 注入（零延迟）

```python
def inject_skills(messages, language):
    skills = CODING_SKILLS_L0  # 通用编程规范
    if language in LANG_SKILLS:
        skills += LANG_SKILLS[language]
    # 追加到 system prompt
    if messages[0]["role"] == "system":
        messages[0]["content"] += "\n" + skills
    else:
        messages.insert(0, {"role": "system", "content": skills})
    return messages
```

## 六、健康检查（后台线程）

```python
health_map = {}  # backend_name -> "healthy" | "degraded" | "dead"

def health_check_loop():
    """每 30 秒 ping 所有后端"""
    while True:
        for backend in ALL_BACKENDS:
            try:
                call_backend(backend, [{"role":"user","content":"hi"}],
                           max_tokens=1, timeout=8)
                health_map[backend] = "healthy"
            except:
                if health_map.get(backend) == "degraded":
                    health_map[backend] = "dead"  # 连续2次失败
                else:
                    health_map[backend] = "degraded"
        time.sleep(30)
```

## 七、熔断器调优

| 参数 | 旧值 | 新值 | 原因 |
|------|------|------|------|
| 失败阈值 | 3 | 5 | 减少误熔断 |
| 恢复超时 | 60s | 30s | 更快恢复 |
| half-open 成功阈值 | 2 | 1 | 更快关闭 |

## 八、验证标准

| 测试 | 预期 |
|------|------|
| Anthropic + "什么？？" | 走真实模型，不返回预设 |
| Anthropic + "学习这个项目" | 走真实模型，不返回图片分析 |
| Anthropic + 代码请求 | 路由到 strong 池 |
| 后端全熔断 | IDE 返回诚实错误，不走 chat_ubi |
| 普通聊天 | 走 chat 池，chat_ubi 可作兜底 |
| 同一请求多次 | 同层内不同后端被选中（随机） |

## 九、实施步骤

```
Step 1: 删除 _try_instant_reply + _INSTANT_REPLIES (5min)
Step 2: 新建 classify_request() (10min)
Step 3: 定义 POOLS 字典 (5min)
Step 4: 新建 select_backends() + health_map (15min)
Step 5: 修改 _handle_chat 用新三层逻辑 (20min)
Step 6: 启动后台健康检查线程 (15min)
Step 7: 熔断器参数调优 (5min)
Step 8: 重启 + 验证全部测试通过 (10min)
```

总计约 1.5 小时。
