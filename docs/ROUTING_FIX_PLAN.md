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

### 11.1 直接对标项目（最值得参考）

| 项目 | 语言 | Stars | 核心参考点 |
|------|------|-------|-----------|
| **Olla** github.com/thushan/olla | Rust/Go | - | Sticky Sessions(KV-cache亲和), lock-free stats, circuit breaker |
| **LunarGate** github.com/lunargate-ai/gateway | Go | - | Weighted+Conditional路由, Circuit Breaker, YAML热重载 |
| **OmniRoute** github.com/diegosouzapw/OmniRoute | TypeScript | - | 6种路由策略, Combo Fallback, Semantic Cache, 健康仪表盘 |

### 11.2 架构级参考

| 项目 | 语言 | Stars | 核心参考点 |
|------|------|-------|-----------|
| **LiteLLM** github.com/BerriAI/litellm | Python | 47.6k | 3种Fallback类型, Cooldown TTL, 指数退避+抖动 |
| **RouteLLM** github.com/lm-sys/RouteLLM | Python | 4.9k | 复杂度阈值路由, 4种路由器, 成本-质量权衡 |
| **Portkey** github.com/Portkey-AI/gateway | TypeScript | 11.8k | 条件路由, Hooks(MUTATOR), onStatusCodes白名单 |

### 11.3 Key 管理 & 免费池参考

| 项目 | 语言 | Stars | 核心参考点 |
|------|------|-------|-----------|
| **GPT-Load** github.com/tbphp/gpt-load | Go+Vue3 | 5.5k | 分组Key池+自动轮换+故障拉黑恢复, 权重负载均衡 |
| **One Balance** github.com/glidea/one-balance | CF Workers | - | 分钟级vs天级配额冷却, 403永久拉黑Key |

### 11.4 痛点 → 参考映射

| LiMa 痛点 | 首选参考 | 次选参考 |
|-----------|---------|---------|
| 上下文丢失(多轮对话) | **Olla** Sticky Sessions | LiteLLM 同模型多Provider fallback |
| 偶发空响应(流式Bug) | **LiteLLM** Cooldown+重试 | Olla 健康检查+熔断 |
| 免费Key过期/限流 | **One Balance** 分级冷却 | GPT-Load Key池自动拉黑恢复 |
| 路由策略单一 | **OmniRoute** 6种策略 | RouteLLM 复杂度阈值 |
| 强模型浪费 | **RouteLLM** 成本-质量权衡 | OmniRoute Cost Optimized |
| Key管理弱 | **GPT-Load** 分组+权重+热重载 | One Balance 过期自动刷新 |
| 改配置要重启 | **LunarGate** YAML热重载 | GPT-Load 热重载 |

## 十二、源码分析关键发现

### 12.0 第二批源码分析（Olla/OmniRoute/GPT-Load/One Balance/LunarGate）

#### Olla — Sticky Sessions（解决上下文丢失）

```python
# 核心：对话前缀 hash → 粘在同一后端
def compute_sticky_key(model, messages_json, prefix_bytes=512):
    prefix = messages_json[:prefix_bytes].encode()
    h = hashlib.blake2b(prefix, digest_size=8).hexdigest()
    return f"{model}:{h}"

# 流程：查缓存 → 命中且健康 → 直接路由 → 未命中 → 正常选路 → 写入缓存
# TTL 5分钟滑动续期（每次命中刷新过期时间）
# 后端死亡时 repin（删旧key，重新选路写入新key）
```

#### Olla — Circuit Breaker 参数

| 参数 | 值 | 含义 |
|------|-----|------|
| FailureThreshold | 5 | 连续 5 次失败 → Open |
| SuccessThreshold | 2 | Half-Open 成功 2 次 → Closed |
| OpenDuration | 60s | Open 持续 60s 后转 Half-Open |
| HalfOpenRequests | 3 | Half-Open 最多放行 3 个探测 |

Half-Open 单次失败立即重回 Open（防级联）。

#### OmniRoute — P2C (Power of Two Choices) 算法

```python
# 比纯随机更好的负载均衡：随机选2个，取更健康的
def p2c_select(targets, get_score):
    i, j = random.sample(range(len(targets)), 2)
    return targets[i] if get_score(targets[i]) >= get_score(targets[j]) else targets[j]

# 健康分 = 成功率/100 + 1/log10(延迟+10) - 熔断惩罚
```

#### OmniRoute — Semantic Cache（精确匹配，非向量）

```python
# key = SHA-256(model + messages + temperature + top_p)
# 仅缓存 temperature=0 的请求（确定性输出）
# 两级存储：LRU内存(100条/4MB) + SQLite持久化
def cache_key(model, messages, temperature=0):
    payload = json.dumps({"model": model, "messages": messages,
                          "temperature": temperature}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
```

#### OmniRoute — 三层 Fallback 隔离

| 层级 | 粒度 | 失败影响范围 |
|------|------|-------------|
| Provider Circuit Breaker | 供应商级 | 整个供应商暂停 |
| Connection Cooldown | 账号级 | 单个 key 冷却 |
| Model Lockout | 模型级 | 单个模型锁定 |

关键：一个 key 429 不会导致整个供应商被封。

#### GPT-Load — SWRR 权重轮转（和 Nginx 一致）

```python
# Smooth Weighted Round-Robin
# 每轮: currentWeight += weight, 选最大者, 然后 -= totalWeight
items = [{"name": "A", "weight": 5, "current": 0},
         {"name": "B", "weight": 3, "current": 0}]
```

#### GPT-Load — Key 池管理

- 分组 Key 管理：每个 group 维护 active_keys 列表
- 轮换：RPOPLPUSH 语义（尾部取出推回头部）
- 拉黑：failure_count 达阈值 → 移出 active list
- 恢复：后台线程每 5 分钟扫描，验证通过推回 active

#### One Balance — 分级冷却

```python
# 分钟级冷却：解析 Retry-After header
# 天级冷却：连续 N 次 429 → 冷却到次日 0 点
# 永久拉黑：401/403 → status='blocked'，不自动恢复
```

#### LunarGate — Circuit Breaker

直接用 `pybreaker` 库（Go 版用 `sony/gobreaker`），不需要自研。
参数：5 次连续失败触发，30s Open，3 次 Half-Open 探测。

### 12.1 第一批源码分析（LiteLLM/RouteLLM/Portkey）

**核心设计：用 Cache TTL 代替定时器**

```python
# 冷却期 = 往 Cache 写一条带 TTL 的记录，到期自动解除
cache.set_cache(
    key="deployment:{model_id}:cooldown",
    value={"exception": error, "status_code": 429, "timestamp": now},
    ttl=cooldown_time,  # 默认 5 秒
)
# 路由时检查：key 存在 = 冷却中，跳过
```

**触发条件（不是所有错误都冷却）：**

| 错误码 | 是否冷却 | 原因 |
|--------|----------|------|
| 429 | ✅ 冷却 | 限流 |
| 401/404/408 | ✅ 冷却 | 认证/不存在/超时 |
| 400 | ❌ 不冷却 | 请求格式错误是调用方问题 |
| 5xx | ✅ 冷却 | 后端内部错误 |
| 失败率>50% 且请求≥5 | ✅ 冷却 | 统计触发 |

**默认参数：**
```python
DEFAULT_COOLDOWN_TIME_SECONDS = 5   # 冷却 5 秒（不是 60 秒！）
DEFAULT_FAILURE_THRESHOLD_PERCENT = 0.5
DEFAULT_FAILURE_THRESHOLD_MINIMUM_REQUESTS = 5
```

**可直接借鉴：**
- 用 dict + timestamp 代替 Redis，TTL 到期自动恢复
- 冷却时间只有 5 秒（我们之前设 60 秒太长了）
- 400 不冷却（是我们的 bug，不是后端的问题）
- 单后端组提高阈值（避免唯一后端被误杀）

### 12.2 LiteLLM — 延迟路由策略

```python
# 滑动窗口 10 条 + 失败惩罚 1000s + buffer 随机化
latency_window = [...]  # 最近 10 次延迟
# 失败时写入 1000s 惩罚
latency_window.append(1000.0)
# 选择时：最低延迟 + buffer 范围内随机选
buffer = 0.2 * lowest_latency
valid = [d for d in sorted if d.latency <= lowest + buffer]
chosen = random.choice(valid)
```

**可直接借鉴：**
- 失败惩罚 1000s 简洁有效
- buffer 随机化防止流量集中到单一后端
- 滑动窗口 10 条，不需要复杂的统计

### 12.3 LiteLLM — Fallback 链

```python
# 递归深度控制，默认 max_fallbacks=5
if fallback_depth >= max_fallbacks:
    raise original_exception
for mg in fallback_model_group:
    if mg == original_model_group:
        continue  # 跳过原始组
    try:
        response = await router.async_function_with_fallbacks(...)
        return response
    except:
        continue
```

**可直接借鉴：**
- `max_fallbacks=5` 防止无限递归
- 跳过原始失败的组

### 12.4 RouteLLM — 分层路由（极简设计）

```python
# 所有策略只需实现一个方法
class Router:
    def calculate_strong_win_rate(self, prompt) -> float:
        """返回 0~1，强模型胜率预测"""
        ...
    
    def route(self, prompt, threshold):
        if self.calculate_strong_win_rate(prompt) >= threshold:
            return strong_model
        else:
            return weak_model
```

**阈值校准：** 用分位数从真实流量反推
```python
# 希望 30% 请求走强模型 → 取胜率分布的 70% 分位数
threshold = data.quantile(q=1 - strong_model_pct)
```

**可直接借鉴：**
- 统一抽象接口：新策略只需实现 `calculate_strong_win_rate`
- 阈值不是拍脑袋，从流量数据反推
- 模型名编码路由参数：`router-bert-0.7`

### 12.5 Portkey — 条件路由 + Hooks

**条件路由：MongoDB 查询语法**
```typescript
conditions: [
  { query: {"metadata.env": {$eq: "prod"}}, then: "gpt4-target" },
  { query: {"params.model": {$regex: "claude"}}, then: "anthropic-target" }
],
default: "fallback-target"
```

**Hooks 系统：GUARDRAIL + MUTATOR**
- GUARDRAIL: 检查请求/响应，可 deny 拦截
- MUTATOR: 修改请求/响应内容（= 我们的 Skills 注入）

**Retry：**
- 支持读取 provider 的 `retry-after` header
- 全局上限 `MAX_RETRY_LIMIT_MS`
- `onStatusCodes` 白名单触发（比硬编码 5xx 更灵活）

**熔断器：** Portkey 开源版无内置实现（依赖云端服务），不参考。

**可直接借鉴：**
- `onStatusCodes` 白名单触发 fallback
- MUTATOR hook = Skills 注入的设计模式
- `retry-after` header 支持（429 时后端告诉你等多久）

## 十三、对我们设计的修正

基于两批源码分析（8个项目），修正原方案：

| 原设计 | 修正为 | 来源 |
|--------|--------|------|
| 冷却时间 30s | **5s** | LiteLLM 默认 5s |
| 连续 5 次失败 → dead | **失败率>50% 且请求≥5** | LiteLLM 统计触发 |
| 400 错误 → suspicious | **不冷却** | LiteLLM (调用方问题) |
| 固定优先级选后端 | **P2C + 延迟滑动窗口** | OmniRoute + LiteLLM |
| 自己实现熔断器 | **用 pybreaker 库** | LunarGate (包装 gobreaker) |
| max retries 无限制 | **max_fallbacks=5** | LiteLLM |
| 多轮对话路由到不同后端 | **Sticky Sessions (prefix_hash)** | Olla |
| 纯随机选后端 | **P2C (随机2选1更健康的)** | OmniRoute |
| 无缓存 | **Semantic Cache (SHA-256精确匹配)** | OmniRoute |
| Key 管理简单 | **SWRR权重轮转 + 分级冷却 + 自动恢复** | GPT-Load + One Balance |
| 一个 key 429 封整个供应商 | **三层隔离 (供应商/账号/模型)** | OmniRoute |
| 改配置要重启 | **watchdog 文件监听热重载** | LunarGate |
| 429 统一处理 | **解析 Retry-After header + 分钟/天级区分** | One Balance |

## 十四、并发支持

### 14.1 当前问题

```
FastAPI (async)
  → asyncio.to_thread(smart_router.route, ...)
    → urllib.request.urlopen(timeout=30)  ← 同步阻塞
```

- `smart_router.py` 全部用 `urllib.request`（同步阻塞）
- 靠 `asyncio.to_thread()` 丢到线程池，默认约 40 线程
- 每个请求占一个线程 3-15 秒
- 无连接池，每次新建 TCP 连接
- 共享状态（health_map）无锁保护
- 单进程，无法利用多核

**瓶颈：** ~40 并发上限，超过排队。每请求额外 50-200ms 建连开销。

### 14.2 目标

- 支持 200+ 并发请求
- 单请求延迟不因并发增加
- 共享状态线程安全
- 连接复用减少建连开销

### 14.3 方案：httpx.AsyncClient 替换 urllib

```python
import httpx

# 全局连接池（启动时创建，进程生命周期内复用）
_client = httpx.AsyncClient(
    timeout=httpx.Timeout(30.0, connect=5.0),
    limits=httpx.Limits(
        max_connections=100,       # 最大连接数
        max_keepalive_connections=20,  # 保活连接数
    ),
    follow_redirects=True,
)

# 需要代理的客户端
_proxy_client = httpx.AsyncClient(
    proxy="http://127.0.0.1:7897",
    timeout=httpx.Timeout(30.0, connect=5.0),
    limits=httpx.Limits(max_connections=50),
)

async def call_backend_async(backend_name, messages, max_tokens):
    """非阻塞后端调用"""
    b = BACKENDS[backend_name]
    body, headers = build_request(backend_name, messages, max_tokens)
    
    client = _proxy_client if b.get("needs_proxy") else _client
    
    resp = await client.post(b["url"], content=body, headers=headers)
    resp.raise_for_status()
    return parse_response(resp.json(), b["fmt"])
```

### 14.4 改动范围

| 文件 | 改动 |
|------|------|
| smart_router.py | `call_api()` → `call_api_async()`，urllib → httpx |
| server.py | 去掉 `asyncio.to_thread()` 包装，直接 await |
| server.py | 启动时创建 `_client`，关闭时 `await _client.aclose()` |

### 14.5 共享状态线程安全

```python
import asyncio

# 用 asyncio.Lock 保护共享状态（比 threading.Lock 更适合 async）
_health_lock = asyncio.Lock()
_health_map: dict[str, str] = {}

async def update_health(backend, success, error_code=None):
    async with _health_lock:
        # 更新逻辑...
        pass

async def get_healthy_backends(pool) -> list:
    async with _health_lock:
        return [b for b in pool if _health_map.get(b) != "dead"]
```

### 14.6 并发 fallback（同时尝试多个后端）

```python
async def execute_with_fallback(backends, messages, max_tokens):
    """按顺序尝试，但可以并发探测多个"""
    for backend in backends:
        try:
            return await asyncio.wait_for(
                call_backend_async(backend, messages, max_tokens),
                timeout=15.0
            )
        except (httpx.HTTPStatusError, asyncio.TimeoutError) as e:
            await update_health(backend, success=False, 
                              error_code=getattr(e.response, 'status_code', None))
            continue
    return None  # 全部失败
```

### 14.7 可选：竞速模式（最快响应）

```python
async def race_backends(backends, messages, max_tokens):
    """同时发给多个后端，取最快返回的（浪费配额但延迟最低）"""
    tasks = [
        asyncio.create_task(call_backend_async(b, messages, max_tokens))
        for b in backends[:3]  # 最多同时 3 个
    ]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    # 取消未完成的
    for t in pending:
        t.cancel()
    # 返回第一个成功的
    for t in done:
        if not t.exception():
            return t.result()
    return None
```

注意：竞速模式浪费配额，只在"延迟敏感 + 配额充足"时使用。

### 14.8 实施步骤

```
Step 1: pip install httpx (服务器)
Step 2: 创建全局 AsyncClient (带连接池)
Step 3: 新建 call_backend_async() 替代 call_api()
Step 4: server.py 去掉 asyncio.to_thread，直接 await
Step 5: health_map 加 asyncio.Lock
Step 6: 测试并发 (ab -n 100 -c 20)
Step 7: 可选: 竞速模式
```

### 14.9 预期效果

| 指标 | 当前 | 改进后 |
|------|------|--------|
| 最大并发 | ~40 (线程池) | 200+ (async) |
| 每请求建连开销 | 50-200ms | ~0ms (连接池复用) |
| 内存占用/请求 | ~8MB (线程栈) | ~几KB (协程) |
| CPU 利用率 | 低(大量等待IO) | 高效(事件循环) |

### 14.10 百万级并发架构（分布式）

单机 async 能到 200+ 并发，但百万级需要分布式：

```
                    ┌─────────────────┐
                    │   Nginx / SLB   │  ← 百万连接入口
                    │  (负载均衡)      │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Worker 1 │  │ Worker 2 │  │ Worker N │  ← 无状态应用节点
        │ (uvicorn │  │ (uvicorn │  │ (uvicorn │
        │  async)  │  │  async)  │  │  async)  │
        └────┬─────┘  └────┬─────┘  └────┬─────┘
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                    ┌───────────────┐
                    │     Redis     │  ← 共享状态
                    │ health_map    │
                    │ cooldown_cache│
                    │ rate_limits   │
                    └───────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        [后端池 A]    [后端池 B]    [后端池 C]
        Groq/Cerebras  DeepSeek     NagaAI/FreeTheAI
```

#### 关键组件

| 组件 | 作用 | 技术选型 |
|------|------|----------|
| 入口负载均衡 | 百万连接分发 | Nginx (C10M) / 阿里云 SLB |
| 应用节点 | 请求处理 | uvicorn + httpx async，水平扩展 |
| 共享状态 | health_map / cooldown / 统计 | Redis (单实例够用) |
| 请求队列 | 削峰填谷 | Redis Stream / RabbitMQ (可选) |
| 连接池 | 复用后端连接 | httpx 每节点独立连接池 |

#### 无状态设计原则

```python
# 所有状态存 Redis，应用节点无状态
import redis.asyncio as redis

_redis = redis.Redis(host="127.0.0.1", port=6379)

async def get_health(backend) -> str:
    return await _redis.get(f"health:{backend}") or "healthy"

async def set_cooldown(backend, ttl=5):
    await _redis.setex(f"cooldown:{backend}", ttl, "1")

async def is_cooled_down(backend) -> bool:
    return await _redis.exists(f"cooldown:{backend}")
```

#### 扩容路径

```
阶段 1 (当前): 单机 async → 200 QPS
阶段 2: 单机多 worker (uvicorn --workers 4) → 800 QPS
阶段 3: 多机 + Nginx → 5000 QPS
阶段 4: 多机 + Redis + SLB → 50000 QPS
阶段 5: 多机 + 消息队列 + 自动扩缩 → 100万+ QPS
```

#### 现实约束

| 层级 | 瓶颈 | 解法 |
|------|------|------|
| 我们的服务器 | 单机 ~200 QPS | 多 worker / 多机 |
| 免费后端 rate limit | Groq 40RPM, Mistral 10RPM | 多 key 轮转 / 更多供应商 |
| 后端总吞吐 | 所有免费后端加起来 ~500 RPM | 加入付费后端 / 本地模型 |
| 网络带宽 | 阿里云 5Mbps 出口 | 升级带宽 / CDN |

**结论：百万级并发的瓶颈不在我们的路由层，而在后端供应商的 rate limit。**
路由层做好水平扩展准备（无状态 + Redis），后端容量通过加供应商/加 key/加本地模型来扩。
