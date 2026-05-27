# LiMa 延迟优化方案

> 状态：执行中 | 创建：2026-05-19 | 目标：用户感知延迟从 8s → 1-2s

## 现状分析

### 当前延迟分布

| 阶段 | 延迟 | 占比 |
|------|------|------|
| 外部 API 调用 | 1-60s | 80% |
| 本地路由模型 | 500ms-5s | 10% |
| 意图分类链路 | 200-500ms | 5% |
| Fallback 重试 | 2-5s | 5% |

### 核心问题

1. **假流式**：当前 `_stream_response` 先获取完整响应再分块发送，用户等待 = 全部生成时间
2. **冷启动**：Qwen3 路由模型 lazy load，首次请求 1-5s 额外延迟
3. **串行 fallback**：质量检查失败后逐个尝试后端，最坏 case 叠加 3-4 次超时
4. **无延迟感知**：后端选择不考虑实时响应速度

## P0：立即执行（感知延迟降 80%）

### P0-1：真流式透传（Real Streaming Passthrough）

**目标**：将假流式改为真流式，直接透传后端 SSE 流

**改动范围**：`smart_router.py` + `server.py`

**实现方案**：

```python
# smart_router.py 新增 call_api_stream() 函数
def call_api_stream(backend_name, messages, max_tokens=1024):
    """流式调用后端，yield SSE chunks"""
    b = BACKENDS[backend_name]
    # 设置 stream=True，逐 chunk yield
    # OpenAI 格式：data: {"choices":[{"delta":{"content":"..."}}]}
    # Anthropic 格式：event: content_block_delta
```

```python
# server.py 修改 _stream_response()
# 之前：result = await asyncio.to_thread(smart_router.route, ...) → 分块发送
# 之后：async for chunk in smart_router.call_api_stream(...): yield chunk
```

**关键改动**：
1. `smart_router.py` 新增 `call_api_stream()` — 使用 `urllib` 流式读取
2. `server.py` 的 `_stream_response()` 改为真正的 async generator
3. OpenAI 和 Anthropic 两种格式都要支持透传

### P0-2：路由模型预热（Model Warmup on Startup）

**目标**：服务启动时加载模型，消除首次请求冷启动

**改动范围**：`smart_router.py`

**实现方案**：

```python
# smart_router.py 末尾添加
def warmup():
    """启动时预热模型"""
    global _local_model, _local_tokenizer
    _load_local_model()  # 已有的加载函数
    # 跑一次 dummy inference 预热 CUDA kernel
    if _local_model:
        _local_infer("warmup test", max_new_tokens=5)

# 模块加载时自动执行
warmup()
```

**收益**：首次请求延迟从 1-5s → 与后续请求一致（~200ms）

## P1：显著提升（总延迟 -30%）

### P1-1：并行投机调用（Speculative Parallel Calls）

**目标**：路由分析与后端调用并行，隐藏路由延迟

**实现方案**：

```python
async def _speculative_route(query, messages, ...):
    # 同时启动：路由分析 + 最可能后端的预请求
    speculative_backend = _predict_likely_backend(query)
    
    route_task = asyncio.create_task(analyze_async(query))
    spec_task = asyncio.create_task(call_backend_async(speculative_backend, ...))
    
    intent = await route_task
    actual_backend = select_backend(intent)
    
    if actual_backend == speculative_backend:
        # 命中！直接用预请求结果
        return await spec_task
    else:
        # 未命中，取消预请求，走正常路径
        spec_task.cancel()
        return await call_backend_async(actual_backend, ...)
```

### P1-2：后端延迟排序（Latency-Aware Backend Selection）

**目标**：同 tier 内优先选最快的后端

**实现方案**：

```python
# 延迟追踪器
_backend_latency = {}  # {name: deque(maxlen=20)}

def record_latency(backend, ms):
    _backend_latency.setdefault(backend, deque(maxlen=20)).append(ms)

def get_fastest_in_tier(tier_backends):
    """返回同 tier 中 P50 最低的后端"""
    scored = []
    for b in tier_backends:
        samples = _backend_latency.get(b, [])
        p50 = sorted(samples)[len(samples)//2] if samples else 9999
        scored.append((p50, b))
    return sorted(scored)[0][1]
```

## P2：架构升级（路由推理加速）

### P2-1：vLLM 替换 transformers

- 本地 Qwen3 推理从 HuggingFace transformers → vLLM
- PagedAttention + continuous batching
- 路由推理 500ms → 50-100ms
- **前置条件**：需要 vLLM 支持 Windows 或迁移到 Linux

### P2-2：路由决策缓存

```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=512)
def _cached_analyze(query_hash):
    return _raw_analyze(query)
```

## 执行计划

| 阶段 | 任务 | 预计耗时 | 状态 |
|------|------|----------|------|
| P0-1 | 真流式透传 | 3h | ✅ 完成 |
| P0-2 | 模型预热 | 30min | ✅ 完成 |
| P1-1 | 并行投机调用 | 4h | ✅ 完成 |
| P1-2 | 后端延迟排序 | 2h | ✅ 完成 |
| P2-1 | vLLM 替换 | 1-2d | ⏳ 待评估 |
| P2-2 | 路由缓存 | 1h | ⏳ 待开始 |

## 验收结果 (2026-05-19)

| 指标 | 优化前 | 优化后 | 达成 |
|------|--------|--------|------|
| OpenAI 首 Token | 37s | **9.7s** | -74% |
| Anthropic 首 Token | 21s | **8.3s** | -61% |
| 冷启动延迟 | 1-5s | 0ms | ✅ |
| 双重 API 调用 | 108s (route+stream) | ~2s (select_backend only) | ✅ |
| 真流式透传 | 假流式 (按句) | 真流式 (逐 token) | ✅ |
| 同 tier 延迟排序 | 固定顺序 | 实时延迟优先 | ✅ |
| 投机并行调用 | 串行 (route→stream) | 并行 (predict+stream) | ✅ |

### 待改进 (P2)

| 指标 | 当前值 | 目标 |
|------|--------|------|
| 首 token 时间 | 8-10s | < 2s (需更快后端) |
| 路由模型推理 | fallback 无模型 | vLLM 50-100ms |
| 路由决策缓存 | 无 | LRU 512 条 |
