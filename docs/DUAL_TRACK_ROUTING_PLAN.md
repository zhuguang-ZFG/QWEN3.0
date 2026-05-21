# 编程/聊天场景分离路由方案

## Context

当前 LiMa 路由引擎已有基础分类能力（smart_router.py 的 4 层分类），但编程和聊天场景的分离不够彻底：
- 编程请求可能被路由到快但代码能力弱的后端（如 groq_llama8b）
- 聊天请求可能被路由到慢但代码能力强的后端（如 nvidia_qwen_coder）
- IDE 来源（Claude Code/Cursor）没有强制走代码路径
- 免费聊天页（chat.donglicao.com）没有优先走快速廉价后端

**目标**: 编程走质量路径（代码专家模型），聊天走速度路径（快速通用模型），最大化利用模型差异。

---

## 现状分析

### 已有的分类机制
- `smart_router.py:803-907` — 信号字典分类器，100+ 关键词规则
- `speculative.py:133-167` — classify_complexity() 区分 simple/code/complex
- `capability_matrix.py:173-185` — select_backends() 按维度评分选后端
- `backends.py:198` — IDE_SOURCES 检测

### 已有的后端池
- `AFFINITY["code"]` — nvidia_qwen_coder, cf_qwen_coder, opencode_stealth...
- `AFFINITY["simple_fast"]` — longcat_lite, groq_llama70b, cerebras_gptoss...
- `FALLBACK_CHAINS["code_generation"]` — groq_gptoss → mistral_codestral → nvidia_qwen_coder

### 问题
1. 分类准确率不够 — 短代码问题（"python sort list"）可能被归为 trivial
2. IDE 来源没有强制路由 — Claude Code 请求可能走 trivial 路径
3. 聊天场景没有专属优化 — 没有 "chat" intent，默认走 unknown
4. 后端池重叠 — code 和 simple_fast 有交集（groq_llama70b 两边都有）

---

## 方案设计

### 核心改动：双轨路由

```
请求进入
  ├─ 场景判定（编程 or 聊天）
  │   ├─ IDE 来源 → 强制编程路径
  │   ├─ 代码信号 → 编程路径
  │   └─ 其他 → 聊天路径
  │
  ├─ 编程路径（质量优先）
  │   ├─ 后端池: 代码专家模型
  │   ├─ 策略: 选最强代码能力，容忍较高延迟
  │   └─ Fallback: code_experts → general_strong → any
  │
  └─ 聊天路径（速度优先）
      ├─ 后端池: 快速通用模型
      ├─ 策略: 选最快响应，容忍较低代码能力
      └─ Fallback: fast_chat → medium → any
```

---

## 实现步骤

### Step 1: 新增场景判定函数

**文件**: `smart_router.py`（新增函数）

```python
def classify_scenario(query: str, messages: list, ide: str = "") -> str:
    """
    判定请求场景: 'coding' | 'chat'
    
    强制规则（优先级最高）:
    - IDE 来源 → coding
    - 含代码块(```) → coding
    - 含错误堆栈(Traceback/Error) → coding
    
    信号规则:
    - 代码关键词密度 > 阈值 → coding
    - 其他 → chat
    """
```

**判定逻辑**:
| 信号 | 场景 | 置信度 |
|------|------|--------|
| IDE ∈ IDE_SOURCES | coding | 1.0 |
| 消息含 ``` 代码块 | coding | 0.95 |
| 含 Traceback/Error/TypeError | coding | 0.9 |
| 含 def/class/import/function | coding | 0.85 |
| 含 "代码/实现/重构/debug/fix" | coding | 0.8 |
| system_prompt 含 "code/developer" | coding | 0.8 |
| 纯中文短问题 (<50字) | chat | 0.9 |
| 含 "你好/帮我/解释/什么是" | chat | 0.85 |
| 默认 | chat | 0.5 |

### Step 2: 定义双轨后端池

**文件**: `smart_router.py`（修改 FALLBACK_CHAINS）

```python
# 编程路径 — 质量优先，容忍 2-5s 延迟
CODE_BACKENDS = [
    # Tier 1: 代码专家 (code score ≥ 9)
    "nvidia_qwen_coder",    # code:9, 2.1s
    "scnet_ds_pro",         # code:10, 3.7s
    "or_qwen3_coder",       # code:9, 3s
    "cf_qwen_coder",        # code:9, 1.1s ← 快且强
    "mistral_codestral",    # code:9, 586ms
    "oldllm_gpt54",         # code:10, 3s
    # Tier 2: 通用强模型 (code score ≥ 7)
    "longcat_thinking",     # code:9, reasoning:9
    "scnet_qwen235b",       # code:9, 1.4s
    "groq_llama70b",        # code:7, 376ms (快速兜底)
]

# 聊天路径 — 速度优先，1s 内响应
CHAT_BACKENDS = [
    # Tier 1: 极速 (<1s, 通用能力足够)
    "groq_llama70b",        # speed:9, 376ms
    "groq_qwen32b",         # speed:9, 400ms
    "cerebras_gptoss",      # speed:9, 500ms
    "scnet_ds_flash",       # speed:8, 1.0s, chinese:9
    "longcat_lite",         # speed:8, 800ms
    # Tier 2: 中速 (1-2s, 质量更好)
    "longcat_chat",         # chinese:8, 1.5s
    "kimi",                 # chinese:10, 1.6s
    "scnet_qwen30b",        # chinese:9, 1.1s
    # Tier 3: 兜底
    "cfai_llama70b",        # 2.3s
    "pollinations_openai",  # 2s
]
```

### Step 3: 修改路由入口

**文件**: `smart_router.py` 的 `select_backend()` 函数

```python
def select_backend(query, prefer=None, system_prompt="", ide="unknown", messages=None):
    # 1. 场景判定
    scenario = classify_scenario(query, messages or [], ide)
    
    # 2. 选择后端池
    if scenario == "coding":
        pool = CODE_BACKENDS
    else:
        pool = CHAT_BACKENDS
    
    # 3. 健康过滤（去掉 cooldown 中的后端）
    available = [b for b in pool if not health_tracker.is_cooled_down(b)]
    
    # 4. 如果可用池为空，fallback 到全量
    if not available:
        available = pool  # force-try
    
    # 5. 返回第一个可用后端
    return available[0], scenario
```

### Step 4: 投机执行适配

**文件**: `speculative.py` 的 `get_affinity_backends()`

```python
def get_affinity_backends(complexity: str, scenario: str = "chat") -> list[str]:
    if scenario == "coding":
        return list(CODE_BACKENDS[:5])  # 代码场景不投机太多
    else:
        return list(CHAT_BACKENDS[:8])  # 聊天场景多投机，取最快
```

### Step 5: 响应元数据标注

**文件**: `server.py` 的 `build_response()`

在 `x_lima_meta` 中加入 `scenario` 字段：
```python
"x_lima_meta": {
    "backend": backend,
    "total_ms": total_ms,
    "scenario": scenario  # "coding" | "chat"
}
```

---

## 关键文件清单

| 文件 | 改动 |
|------|------|
| `smart_router.py` | 新增 classify_scenario() + 修改 select_backend() + 定义 CODE/CHAT_BACKENDS |
| `speculative.py` | get_affinity_backends() 接收 scenario 参数 |
| `server.py` | _handle_chat() 传递 scenario + build_response() 加 scenario 元数据 |
| `capability_matrix.py` | select_backends() 支持 scenario 过滤（可选优化） |

---

## 验证方案

### 单元测试
```python
# test_scenario_classification.py
def test_ide_always_coding():
    assert classify_scenario("hello", [], ide="Claude Code") == "coding"
    assert classify_scenario("你好", [], ide="Cursor") == "coding"

def test_code_signals():
    assert classify_scenario("python sort a list", []) == "coding"
    assert classify_scenario("def fibonacci(n):", []) == "coding"
    assert classify_scenario("TypeError: cannot read property", []) == "coding"

def test_chat_signals():
    assert classify_scenario("你好", []) == "chat"
    assert classify_scenario("今天天气怎么样", []) == "chat"
    assert classify_scenario("帮我解释一下量子力学", []) == "chat"
```

### 端到端验证
```bash
# 编程场景 — 应路由到代码专家
curl -X POST https://chat.donglicao.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"lima-1.3","messages":[{"role":"user","content":"写一个python快速排序"}]}'
# 预期: x_lima_meta.scenario = "coding", backend ∈ CODE_BACKENDS

# 聊天场景 — 应路由到快速模型
curl -X POST https://chat.donglicao.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"lima-1.3","messages":[{"role":"user","content":"你好，介绍一下自己"}]}'
# 预期: x_lima_meta.scenario = "chat", backend ∈ CHAT_BACKENDS
```

### 性能对比
| 场景 | 改前 | 改后 | 提升 |
|------|------|------|------|
| 编程请求延迟 | ~2s (可能走快但弱的后端) | ~2s (走强代码后端) | 质量↑ |
| 编程请求质量 | 不稳定 | 稳定高质量 | 准确率↑ |
| 聊天请求延迟 | ~2s (可能走慢但强的后端) | <1s (走快速后端) | 速度↑50% |
| 聊天请求质量 | 过剩 | 足够 | 成本↓ |

---

## 风险与回退

1. **分类错误**: 编程问题被归为聊天 → 用户收到低质量代码回答
   - 缓解: 宁可多归为 coding（false positive 代价低于 false negative）
2. **代码后端全挂**: CODE_BACKENDS 全部 cooldown
   - 缓解: fallback 到 CHAT_BACKENDS（有代码能力只是不是最强）
3. **回退方案**: 如果分类器出问题，一行代码可禁用：
   ```python
   scenario = "chat"  # 禁用分离，回退到原有逻辑
   ```
