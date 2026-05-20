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

### 6.1 双轨设计：被动追踪 + 主动探活

```
真实请求流量 ───→ 被动追踪 ───→ health_map 实时更新
                                       ↑
后台探活线程 ───→ 主动探针 ───→ 只对 dead/suspicious 后端
```

### 6.2 健康状态定义

| 状态 | 权重 | 含义 | 探活间隔 |
|------|------|------|----------|
| healthy | 1.0 | 正常工作 | 不探活(靠真实流量) |
| degraded | 0.5 | 偶尔失败/慢 | 不探活(还有真实流量) |
| suspicious | 0.0 | 疑似key失效 | 5 分钟 |
| dead | 0.0 | 确认不可用 | 15 分钟 |

### 6.3 被动追踪（零成本，每次请求自动更新）

```python
consecutive_failures = {}  # backend -> int

def update_health(backend, success, error_code=None):
    """每次真实请求后自动调用"""
    if success:
        health_map[backend] = "healthy"
        consecutive_failures[backend] = 0
        return

    consecutive_failures[backend] = consecutive_failures.get(backend, 0) + 1
    n = consecutive_failures[backend]

    if error_code == 429:
        health_map[backend] = "degraded"  # 限流≠死，服务是活的
    elif error_code in (401, 403):
        health_map[backend] = "suspicious"  # 可能key废了，待确认
    elif n >= 5:
        health_map[backend] = "dead"
    else:
        health_map[backend] = "degraded"
```

### 6.4 主动探活（低频，只探 dead/suspicious）

```python
def probe_loop():
    """后台线程：只对非 healthy 后端发探针"""
    while True:
        for backend, state in health_map.items():
            if state == "healthy" or state == "degraded":
                continue  # 有真实流量，不需要探活
            interval = 300 if state == "suspicious" else 900
            if time_since_last_probe(backend) < interval:
                continue
            # 最小化探针：max_tokens=1
            try:
                call_backend(backend,
                    [{"role": "user", "content": "1"}],
                    max_tokens=1, timeout=8)
                health_map[backend] = "healthy"
                log(f"[PROBE] {backend} recovered!")
            except HTTPError as e:
                if e.code == 429:
                    health_map[backend] = "degraded"  # 限流=活着
                # 否则保持 dead/suspicious
        time.sleep(60)  # 主循环每分钟跑一次
```

### 6.5 错误分级表

| HTTP 错误 | 含义 | 标记为 | 恢复策略 |
|-----------|------|--------|----------|
| 超时 | 网络/后端慢 | degraded | 下次降权但不排除 |
| 429 | 限流 | degraded | 等60s自动恢复 |
| 401 | key无效 | suspicious | 探针确认key是否废了 |
| 403 | 被封/地区限制 | suspicious | 探针用代理重试 |
| 500 | 后端内部错误 | degraded | 多数是临时的 |
| 连接拒绝 | 完全挂了 | dead | 15min探活 |

### 6.6 select_backends 集成健康状态

```python
def select_backends(request_type: str) -> list:
    pool = POOLS[request_type]
    result = []
    for tier in ["strong", "medium", "floor"]:
        candidates = pool.get(tier, [])
        # 只选 healthy + degraded(降权)
        usable = []
        for b in candidates:
            state = health_map.get(b, "healthy")
            if state == "healthy":
                usable.append((b, 1.0))
            elif state == "degraded":
                usable.append((b, 0.5))
            # suspicious/dead 不选
        # 加权随机排序
        random.shuffle(usable)
        usable.sort(key=lambda x: -x[1])  # 健康的优先
        result.extend([b for b, _ in usable])
    return result
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

## 十、永不"不可用"保证

### 10.1 问题

80+ 后端、24 供应商，不可能全部同时挂。
如果出现"不可用"，一定是我们自己的问题（代理挂了/熔断级联/代码bug）。

### 10.2 真正导致"全部失败"的原因

| 原因 | 本质 | 解法 |
|------|------|------|
| 代理(7897)挂了 | 需代理的后端全连不上 | 检测代理状态，切直连后端 |
| 熔断器级联 | 3次失败就熔断，连锁反应 | 提高阈值 + 批量熔断检测 |
| DNS 故障 | 域名解析失败 | 缓存 DNS / IP 直连 |
| 服务器出口被封 | 阿里云 IP 被封 | 走代理绕过 |
| 代码 bug | patch 破坏请求格式 | 冒烟测试 |

### 10.3 批量熔断检测

```python
def detect_mass_failure():
    """超过 50% 后端同时 dead = 我们自己的问题"""
    dead_count = sum(1 for s in health_map.values() if s == "dead")
    total = len(health_map)
    if dead_count > total * 0.5:
        log("[ALERT] 批量熔断！可能是代理/网络问题")
        reset_all_circuit_breakers()
        switch_to_direct_backends()  # 只用不需要代理的后端
        return True
    return False
```

### 10.4 三级保底机制

```
正常路径:
  IDE: strong池 → medium池 → floor池(longcat_lite)
  Chat: strong池 → medium池 → floor池(chat_ubi)

异常路径 (批量熔断触发):
  → 重置熔断器
  → 切换到"无代理后端池":
    zhipu(国内直连) / aliyun(国内直连) / volcengine(国内直连)

极端路径 (连国内直连都挂了):
  → chat_ubi (零key零代理零限制，永远能用)
  → pollinations (零key零限制)

永远不返回"不可用"。
```

### 10.5 无代理后端池（国内直连，不依赖代理）

```python
DIRECT_BACKENDS = [
    'zhipu_flash',      # 智谱 (国内直连)
    'aliyun_turbo',     # 阿里云 (国内直连)
    'volcengine_lite',  # 火山引擎 (国内直连)
    'deepseek_flash',   # DeepSeek (国内直连)
    'chat_ubi',         # ch.at (零依赖)
    'pollinations',     # Pollinations (零依赖)
]
```

### 10.6 代理健康检测

```python
_proxy_healthy = True

def check_proxy():
    """每 60s 检测代理是否可用"""
    global _proxy_healthy
    try:
        # 用最轻量的请求测试代理
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"https": PROXY_URL}))
        opener.open("https://httpbin.org/status/200", timeout=5)
        _proxy_healthy = True
    except:
        _proxy_healthy = False
        log("[ALERT] 代理不可用，切换到直连模式")
```

### 10.7 select_backends 最终版（集成所有保障）

```python
def select_backends(request_type: str) -> list:
    pool = POOLS[request_type]
    result = []

    # 正常选择：从池中选健康后端
    for tier in ["strong", "medium", "floor"]:
        candidates = pool.get(tier, [])
        # 如果代理不可用，过滤掉需要代理的后端
        if not _proxy_healthy:
            candidates = [b for b in candidates if b in DIRECT_BACKENDS]
        usable = [b for b in candidates
                  if health_map.get(b, "healthy") in ("healthy", "degraded")]
        random.shuffle(usable)
        result.extend(usable)

    # 保底：如果正常池全空，用无代理后端
    if not result:
        detect_mass_failure()  # 触发批量熔断检测
        result = [b for b in DIRECT_BACKENDS
                  if health_map.get(b, "healthy") != "dead"]

    # 极端保底：如果连直连都空，强制加 chat_ubi
    if not result:
        result = ["chat_ubi", "pollinations"]

    return result
```

## 十一、参考项目

| 项目 | 地址 | 参考点 |
|------|------|--------|
| LiteLLM | github.com/BerriAI/litellm | Router健康检查+fallback+格式转换 |
| RouteLLM | github.com/lm-sys/RouteLLM | 强/弱模型分流策略 |
| Portkey Gateway | github.com/Portkey-AI/gateway | 语义缓存+重试策略 |
| One-API | github.com/songquanpeng/one-api | 多渠道负载均衡(已在用) |
| Helicone | github.com/Helicone/helicone | 指标记录+可观测性 |
