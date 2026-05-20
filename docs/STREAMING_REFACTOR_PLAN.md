# Streaming 拆分设计

> 日期: 2026-05-20
> 目标: 从 server.py 提取流式处理逻辑为独立 streaming.py (≤200行)
> 原则: 依赖注入解耦 / 不破坏现有行为 / 文件小

## 一、当前问题

server.py 的流式代码 ~350 行，深度耦合：

```
_anthropic_stream (180行)
  ├─ smart_router.detect_image_intent()
  ├─ _build_pollinations_url()
  ├─ _try_instant_reply()  ← 已删除
  ├─ _thinking_route()
  ├─ smart_router.analyze()
  ├─ orchestrate.needs_orchestration()
  ├─ orchestrate.orchestrate()
  ├─ _speculative_stream_chunks()
  ├─ _real_stream_chunks()
  ├─ _record_request()
  ├─ _log_sys_prompt()
  └─ extract_system_prompt()

_stream_response (70行)
  ├─ 同上大部分依赖
  └─ _split_sentences()

_speculative_stream_chunks (55行)
  ├─ smart_router.predict_fast_backend()
  ├─ smart_router.select_backend()
  └─ _real_stream_chunks()

_real_stream_chunks (65行)
  └─ smart_router.call_api_stream()
  └─ smart_router.call_api()
```

## 二、拆分策略：核心提取 + 依赖注入

只提取纯流式逻辑，注入 3 个回调函数替代内部依赖：

```python
# 依赖注入接口
CallApiStreamFn = Callable[[str, list, int, str], Iterator[str]]  # backend, msgs, mt, ide → chunks
CallApiFn = Callable[[str, list, int, str], str]                 # backend, msgs, mt, ide → answer
PredictFn = Callable[[str], str]                                  # query → backend_name
SelectFn = Callable[[str, ...], tuple[str, list]]                 # query → (backend, msgs)
EmitChunkFn = Callable[[str], None]                               # chunk → (yield)
```

## 三、目标文件

### streaming.py (~180行)

```python
# 纯流式核心，不依赖 smart_router/server 内部

async def bridge_stream(backend, msgs, max_tokens, ide,
                        call_stream_fn, call_fn) -> AsyncIterator[str]:
    """同步流→异步桥接 (_real_stream_chunks 重构)"""

async def speculative_stream(query, msgs, max_tokens, ide,
                             predict_fn, select_fn,
                             call_stream_fn, call_fn) -> AsyncIterator[tuple]:
    """预测流式：预测后端立即流 + 路由并行验证 (_speculative_stream_chunks 重构)"""

def build_stream_response(chat_id, query, messages, ide_source,
                          predict_fn, call_stream_fn, call_fn,
                          select_fn, orchestrator_fn) -> AsyncIterator[str]:
    """构建 OpenAI SSE 流 (_stream_response 重构)"""

def build_anthropic_stream(...) -> AsyncIterator[str]:
    """构建 Anthropic SSE 流 (_anthropic_stream 简化版)"""
```

### server.py 保留 (~100行)

```python
# server.py 中保留：thinking/vision/image/orchestration 判断 + 组合 streaming

async def _anthropic_stream(req, model, ...):
    # 只做：thinking检测 → 调 streaming.build_anthropic_stream()
    #      vision处理 → 调 vision_handler
    #      image检测 → 调 polling
    #      normal → 调 streaming 核心
```

## 四、不做

- **不做** thinking mode 提取 — 特殊路由逻辑，保留 server.py
- **不做** vision passthrough 提取 — 已在 vision_handler.py
- **不做** image generation 提取 — Pollinations 单行 URL
- **不做** orchestration 提取 — orchestrator.py 已独立
- **不做** Anthropic SSE 事件格式提取 — 格式常量已在 response_builder.py

## 五、实施步骤

1. 写 `streaming.py`（~180行），纯流式逻辑 + 依赖注入
2. 写 `test_streaming.py`（~150行），mock 所有依赖
3. server.py 中替换 `_real_stream_chunks` + `_speculative_stream_chunks` 为 streaming import
4. server.py 中 `_stream_response` 调用 streaming.build_stream_response()
5. server.py 中 `_anthropic_stream` 保留但简化（删内联 streaming 细节）
6. 全量测试通过
