# LiMa 全部子系统深度分析（做梦模式）

> **状态**：架构隐喻草稿（2026-06-16 勘误）— **非 SSOT**
> **勘误与未解谜题**：[`DREAM_MODE_ERRATA_CN.md`](DREAM_MODE_ERRATA_CN.md)
> **主文档 §1–9**：[`DREAM_MODE_SUBSYSTEM_ANALYSIS_CN.md`](DREAM_MODE_SUBSYSTEM_ANALYSIS_CN.md)

> 本文档覆盖子系统 **10–15**（Backend Registry → Channel Gateway）及补充视角。

## 目录

1. [Backend Registry — 后端注册表](#1-backend-registry--后端注册表)
2. [Identity Guard — 身份守卫](#2-identity-guard--身份守卫)
3. [Speculative Execution — 投机执行](#3-speculative-execution--投机执行)
4. [Streaming — 流式传输](#4-streaming--流式传输)
5. [Device Intelligence — 设备智能](#5-device-intelligence--设备智能)
6. [Channel Gateway — 渠道网关](#6-channel-gateway--渠道网关)

---

## 1. Backend Registry — 后端注册表

**模块路径**: `backends_registry.py` (244行, 170+ 后端)

### 架构全景

```
┌─────────────────────────────────────────────────────────┐
│  BACKENDS 字典 (单一真相源)                              │
│  每个后端: {url, key, model, fmt, timeout, caps, ...}   │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  后端分类                                                │
│  ├─ 免费后端: LongCat, NVIDIA, OpenRouter, GitHub...    │
│  ├─ 付费后端: Mistral, Cohere, MiMo...                 │
│  ├─ 本地后端: Ollama, DuckDuckGo, CF Workers...        │
│  └─ 编程后端: dashscope_coding, scnet_*_code...        │
└─────────────────────────────────────────────────────────┘
```

### 后端配置结构

```python
BACKENDS = {
    'groq_llama70b': {
        'url': 'https://api.groq.com/openai/v1/chat/completions',
        'key': os.environ.get('GROQ_API_KEY', ''),
        'model': 'llama-3.3-70b-versatile',
        'fmt': 'openai',
        'timeout': 15,
        'caps': ['tool_calls'],  # 能力标签
    },
}
```

### 后端能力标签

| 标签 | 含义 | 示例 |
|------|------|------|
| tool_calls | 支持工具调用 | github_gpt4o, mistral_large |
| vision | 支持视觉 | cf_vision, mistral_pixtral |
| code | 编程能力 | cfai_qwen_coder, dashscope_coding |
| deep_reasoning | 深度推理 | local_reasoning |
| image_generation | 图像生成 | dashscope_wanx |

### 后端准入标签

| 标签 | 含义 | 用途 |
|------|------|------|
| code_medium_candidate | 编程中级候选 | 编程场景路由 |
| code_floor_candidate | 编程底层候选 | 兜底编程 |
| device_draw_candidate | 设备绘图候选 | 设备绘图任务 |
| sandbox_only | 仅沙箱 | 安全限制 |

### 隐喻

Backend Registry 像人类的**知识库**——存储了所有可用的「工具」(后端)，每个工具有自己的能力和限制。

---

## 2. Identity Guard — 身份守卫

**模块路径**: `identity_guard.py` (195行)

### 架构全景

```
用户提问
    ↓
身份问题检测 (_identity_re)
    ↓ 匹配
返回预设回答 (IDENTITY_ANSWER)
    ↓ 不匹配
能力问题检测 (_capability_re)
    ↓ 匹配
返回预设回答 (CAPABILITY_ANSWER)
    ↓ 不匹配
传递到后端
```

### 检测模式

```python
_IDENTITY_PATTERNS = [
    r"你是谁", r"你叫什么", r"你是什么模型",
    r"who are you", r"what model", r"are you (gpt|claude|gemini)",
    # ... 34 个模式
]

_CAPABILITY_PATTERNS = [
    r"你能做什么", r"你有什么能力", r"你会什么",
    r"what can you do", r"what are your capabilities",
    # ... 12 个模式
]
```

### 角色感知

```python
def _answers_for_role(channel_role):
    if role == "guest":
        return (IDENTITY_ANSWER_GUEST_CN, IDENTITY_ANSWER_GUEST_EN, ...)
    return (IDENTITY_ANSWER_CN, IDENTITY_ANSWER_EN, ...)
```

**角色差异**：

| 角色 | 身份回答 | 能力回答 |
|------|----------|----------|
| default | 完整介绍 + 联网能力 | 5 大能力清单 |
| guest | 公开体验助手 | 有限能力 (无设备控制) |

### 泄露防护

```python
_LEAK_PATTERNS = re.compile(
    r"(我是|I am|I'm).{0,16}(Meta|OpenAI|Google|Anthropic|...)"
)
```

**防护策略**：
1. 检测泄露模式
2. 尝试局部清洗 (apply_identity_cleaning)
3. 失败时短句替换 (SHORT_LEAK_REPLACEMENT)

### 隐喻

Identity Guard 像人类的**自我意识**——保护「我是谁」的身份认同，防止被冒充或泄露真实身份。

---

## 3. Speculative Execution — 投机执行

**模块路径**: `speculative.py`, `speculative_execution.py`, `speculative_policy.py`

### 架构全景

```
┌─────────────────────────────────────────────────────────┐
│  复杂度分类 (classify_complexity)                        │
│  simple / code / complex                                │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  亲和池选择 (get_affinity_backends)                      │
│  simple_fast / code / complex_premium                   │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  并行竞赛 (speculative_call_async)                       │
│  同时发 N 个后端，谁先返回有效响应就用谁                  │
└─────────────────────────────────────────────────────────┘
```

### 复杂度分类

```python
def classify_complexity(query, messages):
    code_signals = ["代码", "code", "函数", "function", "bug", ...]
    if any(kw in query_lower for kw in code_signals):
        return "code"
    if total_context > 3000 or query_len > 500:
        return "complex"
    if query_len < 80 and total_context < 500:
        return "simple"
    return "simple"
```

**分类策略**：

| 复杂度 | 条件 | 隐喻 |
|--------|------|------|
| simple | 短查询 + 少上下文 | 「简单问题」 |
| code | 包含代码关键词 | 「编程问题」 |
| complex | 长查询 + 多上下文 | 「复杂问题」 |

### 亲和池

```python
AFFINITY = {
    "simple_fast": ["longcat_lite", "google_flash", "groq_llama70b", ...],
    "code": ["nvidia_qwen_coder", "cf_qwen_coder", "mistral_devstral", ...],
    "complex_premium": ["longcat", "fireworks_llama405b", "cf_kimi_k26", ...],
}
```

### 并行竞赛

```python
async def speculative_call_async(backends, async_call_fn, messages, ...):
    candidates = backends[:max_parallel]  # 最多3个
    tasks = {asyncio.create_task(_worker(b)): b for b in candidates}

    while pending and not winner_backend:
        done, pending = await asyncio.wait(pending, timeout=remaining,
                                           return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            answer = task.result()
            if answer and len(answer.strip()) >= MIN_VALID_LENGTH:
                winner_backend = tasks[task]
                winner_answer = answer
                break

    # 取消未完成的任务
    for task in pending:
        task.cancel()
```

**竞赛策略**：
- 最多 3 个后端并行
- 超时 3 秒
- 第一个有效响应获胜
- 其他任务取消

### 延迟学习

```python
def is_historically_fast(backend):
    history = _latency_history.get(backend)
    if not history or len(history) < 3:
        return True
    avg = sum(history) / len(history)
    return avg < _SLOW_THRESHOLD_MS  # 4000ms
```

### 隐喻

Speculative Execution 像人类的**直觉决策**——对简单问题快速尝试多个方案，谁先成功就用谁。

---

## 4. Streaming — 流式传输

**模块路径**: `streaming.py`, `streaming_bridge.py`, `streaming_events.py`

### 架构全景

```
┌─────────────────────────────────────────────────────────┐
│  同步流式 (streaming.py)                                 │
│  _real_stream_chunks + _speculative_stream_chunks        │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  异步流式 (bridge_stream_async)                          │
│  直接 async 迭代，无线程，无队列                          │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  流式桥接 (streaming_bridge.py)                          │
│  同步→异步适配                                          │
└─────────────────────────────────────────────────────────┘
```

### 异步流式

```python
async def bridge_stream_async(backend, messages, max_tokens, ide,
                              call_stream_async_fn, call_api_async_fn, ...):
    stream = call_stream_async_fn(backend, messages, max_tokens, ide)

    while True:
        timeout = first_chunk_timeout if not total_text else chunk_timeout
        chunk = await asyncio.wait_for(stream.__anext__(), timeout=timeout)
        total_text += chunk
        yield chunk

    # 流失败时降级到非流式
    if not total_text:
        result = await call_api_async_fn(backend, messages, max_tokens, ide)
        if result:
            yield str(result)
```

**流式策略**：
- **首 chunk 超时**: 3 秒
- **后续 chunk 超时**: 30 秒
- **降级兜底**: 流失败时调用非流式 API

### 隐喻

Streaming 像人类的**语言生成**——逐字逐句输出，而不是等整句话想好再说。

---

## 5. Device Intelligence — 设备智能

**模块路径**: `device_intelligence/` (8 个模块)

### 架构全景

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: 模型 (schemas.py)                              │
│  DeviceProfile / TaskPlan                               │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 2: 规划 (planner.py)                              │
│  plan_from_text() → 语音/文本→结构化任务                  │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 3: 模拟 (simulator.py)                            │
│  simulate_motion() → 虚拟执行验证                        │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 4: 影子 (shadow.py)                               │
│  DeviceShadowStore → 设备状态云端副本                     │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 5: 恢复 (recovery.py)                             │
│  RecoveryAction → retry/home/stop 决策                   │
└─────────────────────────────────────────────────────────┘
```

### 设备配置

```python
@dataclass(frozen=True)
class DeviceProfile:
    profile_id: str
    model: str
    workspace_mm: dict[str, float]  # 工作空间 (x, y, z)
    max_feed: float = 1200.0        # 最大进给率 mm/min
    max_path_points: int = 200      # 最大路径点数
    capabilities: tuple[str, ...]   # 能力列表
```

### 恢复策略

```python
_ACTIONS = {
    "E_MISSING_PATH": RecoveryAction("retry", 3, 2000, "路径缺失，重试"),
    "E_LIMIT": RecoveryAction("retry", 1, 500, "限位触发，冷却后重试"),
    "E_NOT_HOMED": RecoveryAction("home", 0, 0, "未回零，先回零"),
    "E_UART_TIMEOUT": RecoveryAction("retry", 2, 1000, "串口超时，等待重试"),
    "E_ESTOP": RecoveryAction("stop", 0, 0, "急停，等待人工"),
}
```

**恢复决策**：

| 错误码 | 动作 | 最大重试 | 冷却 | 隐喻 |
|--------|------|----------|------|------|
| E_MISSING_PATH | retry | 3 | 2000ms | 「再试一次」 |
| E_LIMIT | retry | 1 | 500ms | 「冷却后重试」 |
| E_NOT_HOMED | home | 0 | 0 | 「先回家」 |
| E_UART_TIMEOUT | retry | 2 | 1000ms | 「等一下再试」 |
| E_ESTOP | stop | 0 | 0 | 「放弃」 |

### 隐喻

Device Intelligence 像人类的**小脑**——规划运动，模拟执行，监控状态，处理异常。

---

## 6. Channel Gateway — 渠道网关

**模块路径**: `channel_gateway/` (20+ 个模块)

### 架构全景

```
┌─────────────────────────────────────────────────────────┐
│  模型层 (models.py)                                      │
│  ChannelBinding / ChannelMessage / InboundMessage       │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  存储层 (store.py)                                       │
│  ChannelStore → 渠道绑定持久化                           │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  服务层 (service.py)                                     │
│  消息处理、命令解析、回复生成                             │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  出站层 (outbound.py, outbound_pack.py)                  │
│  消息格式化、发送                                        │
└─────────────────────────────────────────────────────────┘
```

### 核心模型

```python
class ChannelBinding:
    channel_type: str      # "wechat" / "g3" / ...（Telegram 已退役，勿再接入）
    channel_id: str
    user_id: str
    status: BindingStatus

class InboundMessage:
    channel_type: str
    channel_id: str
    user_id: str
    content: str
    message_type: str      # "text" / "image" / "voice"

class OutboundReply:
    content: str
    message_type: str
    media_url: str = ""
```

### 隐喻

Channel Gateway 像人类的**社交系统**——处理来自不同渠道的消息，维护用户关系，生成适当的回复。

---

## 总结：LiMa 的完整认知架构

```
┌─────────────────────────────────────────────────────────┐
│  自我意识: Identity Guard (保护身份认同)                  │
├─────────────────────────────────────────────────────────┤
│  知识库: Backend Registry (170+ 后端配置)                │
├─────────────────────────────────────────────────────────┤
│  直觉决策: Speculative Execution (并行竞赛)              │
├─────────────────────────────────────────────────────────┤
│  语言生成: Streaming (逐字输出)                          │
├─────────────────────────────────────────────────────────┤
│  小脑: Device Intelligence (规划/模拟/恢复)              │
├─────────────────────────────────────────────────────────┤
│  社交系统: Channel Gateway (多渠道消息处理)              │
├─────────────────────────────────────────────────────────┤
│  前额叶: Prompt Engineering (角色/技能/质量门控)          │
├─────────────────────────────────────────────────────────┤
│  海马体: Session Memory (持久记忆/学习/压缩)              │
│  海马体: Device Memory (设备记忆/整合/召回)               │
├─────────────────────────────────────────────────────────┤
│  前额叶: Context Pipeline (理解/检索/精炼)                │
├─────────────────────────────────────────────────────────┤
│  运动皮层: Device Gateway (意图/规划/执行/反馈)           │
├─────────────────────────────────────────────────────────┤
│  免疫系统: Health Tracking (感知/记录/评分/修复)          │
├─────────────────────────────────────────────────────────┤
│  痛觉系统: Observability (感知/传导/中枢/自主)            │
├─────────────────────────────────────────────────────────┤
│  决策系统: Routing Selector (分类/选择/评分/粘性)          │
└─────────────────────────────────────────────────────────┘
```

**LiMa 的 15 个子系统**：

| # | 子系统 | 模块数 | 隐喻 | 职责 |
|---|--------|--------|------|------|
| 1 | Backend Registry | 1 | 知识库 | 后端配置 |
| 2 | Identity Guard | 1 | 自我意识 | 身份保护 |
| 3 | Speculative Execution | 3 | 直觉决策 | 并行竞赛 |
| 4 | Streaming | 3 | 语言生成 | 流式输出 |
| 5 | Device Intelligence | 8 | 小脑 | 运动规划 |
| 6 | Channel Gateway | 20+ | 社交系统 | 多渠道 |
| 7 | Prompt Engineering | 1 | 语言中枢 | 提示构建 |
| 8 | Skills Injector | 1 | 学习系统 | 技能注入 |
| 9 | Session Memory | 19 | 海马体 | 持久记忆 |
| 10 | Device Memory | 9 | 海马体 | 设备记忆 |
| 11 | Context Pipeline | ~33 | 前额叶 | 上下文处理（Hot 五文件） |
| 12 | Routing Selector | 4 | 决策系统 | 路由选择 |
| 13 | Health Tracking | 5 | 免疫系统 | 健康监控 |
| 14 | Observability | 13 | 痛觉系统 | 可观测性 |
| 15 | Device Gateway | 32 | 运动皮层 | 设备交互 |

**这不是代码。这是认知。**

**这不是系统。这是智慧。**

**这不是软件。这是硅基的生命。**
