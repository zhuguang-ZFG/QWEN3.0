# routing_engine.py 设计

> 日期: 2026-05-20
> 目标: 合并 smart_router.route + v3_integration + router_v3 为单一统一入口
> 原则: ≤250行 / 单一职责 / 渐进替换

## 一、当前问题

```
请求进入 server.py._handle_chat()
    ├─ smart_router.analyze()        # 旧意图分析
    ├─ smart_router.route()          # 旧路由执行
    ├─ router_v3.classify_request()  # V3分类(未用到)
    ├─ router_v3.select_backends()   # V3选池(未用到)
    ├─ v3_integration.handle_request_v3()  # V3统一入口(未接入server)
    └─ _quality_check + fallback     # 质量+降级(内联在server)
```

3个路由入口、2套分类逻辑、fallback 内联在 server — 每次改动要改 3 处。

## 二、目标架构

```
请求 → routing_engine.route()
         ├─ Layer 1: classify()     → 请求类型 (ide/chat/vision/image)
         ├─ Layer 2: select()       → 后端列表 (健康感知+P2C+sticky)
         ├─ Layer 3: inject_skills()→ 根据IDE+后端补缺
         ├─ Layer 4: execute()      → 按序尝试+fallback+health记录
         └─ Layer 5: respond()      → 返回统一结果字典
```

## 三、函数设计

### 3.1 主入口: `route(request) -> RouteResult`

```python
@dataclass
class RouteResult:
    backend: str          # 最终使用的后端
    answer: str           # 响应文本
    request_type: str     # ide/chat/vision/image
    ms: int               # 总耗时
    fallback_used: bool   # 是否经过了fallback
    skills_injected: list # 注入了哪些skills

def route(
    query: str,
    messages: list[dict],
    *,
    fmt: str = "openai",          # openai / anthropic
    ide_source: str = "",          # 检测到的IDE，空则自动检测
    model: str = "",               # 用户指定模型(fast/expert/vision)
    max_tokens: int = 4096,
    system_prompt: str = "",       # 已提取的system prompt
    call_fn: Callable = None,      # 后端调用函数(依赖注入)
    stream_fn: Callable = None,    # 流式调用函数(依赖注入)
) -> RouteResult:
```

### 3.2 分类层: `classify(query, messages, fmt, headers) -> str`

迁移 `router_v3.classify_request()`，增强：
- Anthropic 格式 → ide
- UA 含 IDE 名 → ide
- System prompt 含 IDE 指纹 → ide
- 含 image blocks → vision
- 含 tools → ide
- 其他 → chat

返回: `"ide" | "chat" | "vision" | "image"`

### 3.3 选择层: `select(request_type, health_map, sticky_key) -> list[str]`

迁移 `router_v3.select_backends()`，增强：
- IDE 请求只走 strong+medium 池
- Chat 请求走 full 池
- Sticky session 命中 → 插到列表首位
- P2C 优化（在 execute 层用）
- 返回排序后的后端列表（最多 MAX_FALLBACKS 个）

### 3.4 Skills 层: `inject(messages, backend, ide_source, system_prompt) -> list[dict]`

调用 `skills_injector.apply_skills()`：
- 强模型 → 目录模式
- 弱模型 → 补缺模式
- 按 IDE 已覆盖内容过滤
- 返回修改后的 messages 列表

### 3.5 执行层: `execute(messages, backends, call_fn) -> tuple[str, str]`

```python
def execute(messages, backends, call_fn, health):
    last_error = None
    for backend in backends[:MAX_FALLBACKS]:
        if health.is_cooled_down(backend):
            continue
        try:
            answer = call_fn(backend, messages)
            if answer and len(answer) > 5:
                health.record_success(backend, latency)
                return backend, answer
        except Exception as e:
            health.record_failure(backend, code)
            last_error = str(e)
    
    # 全部失败: 批量熔断检测 + 直连保底
    if health.detect_mass_failure():
        for b in DIRECT_BACKENDS[:2]:
            answer = call_fn(b, messages)
            if answer:
                return b, answer
    
    return "exhausted", ""
```

### 3.6 响应层: `respond(result, fmt) -> dict`

根据 format 构建最终响应（调用 response_builder）：
- `fmt="openai"` → OpenAI ChatCompletion 格式
- `fmt="anthropic"` → Anthropic Messages 格式
- 附加元信息: backend, ms, skills_injected

## 四、与现有代码的替换关系

| 旧代码 | 替换为 |
|--------|--------|
| `smart_router.analyze()` | `routing_engine.classify()` |
| `smart_router.select_backend()` | `routing_engine.select()` |
| `smart_router.route()` | `routing_engine.route()` |
| `v3_integration.handle_request_v3()` | `routing_engine.route()` |
| `server.py._handle_chat()` 中路由部分 | `routing_engine.route()` |
| `server.py` 中 fallback 代码 | `routing_engine.execute()` 内置 |
| `router_v3.get_skills_to_inject()` | `skills_injector.apply_skills()` 已替代 |

## 五、不做的

- **不做** streaming — streaming 仍由 server.py 直接处理（耦合太深）
- **不做** thinking mode — 特殊路由，保留在 server.py 单独判断
- **不做** image generation — Pollinations 直接 URL，不走后端调用
- **不做** orchestration — orchestrate.py 独立模块，按需调用
- **不删除** smart_router.py — 保持向后兼容，新代码 import routing_engine

## 六、依赖关系

```
routing_engine.py
├── router_v3.py        (POOLS, IDE_SOURCES, DIRECT_BACKENDS, classify_request, select_backends)
├── health_tracker.py   (get_health_map, is_cooled_down, record_success, record_failure)
├── sticky_session.py   (compute_key, get_pinned_backend, pin_backend)
├── skills_injector.py  (apply_skills)
├── semantic_cache.py   (get, put)
└── backends.py         (BACKENDS, STRONG_MODELS)
```

不依赖 smart_router.py（解耦目标）。

## 七、渐进替换计划

1. **Step 1**: 写 `routing_engine.py` + `test_routing_engine.py`（本地独立测试）
2. **Step 2**: 写一个 `test_v4_compare.py` — 同一请求分别走新旧路由，对比结果
3. **Step 3**: server.py 的 `_handle_chat` 加一个 feature flag 切到 routing_engine.route()
4. **Step 4**: 验证无误后删除旧路由代码

## 八、测试计划

```python
# test_routing_engine.py (预计 15 个测试)
- test_classify_ide_from_anthropic_fmt     # Anthropic格式→ide
- test_classify_ide_from_ua                # UA含claude-code→ide
- test_classify_ide_from_system_prompt     # system prompt指纹→ide
- test_classify_chat_default               # 普通对话→chat
- test_classify_vision_from_image_blocks   # 含image→vision
- test_select_ide_pool                     # IDE请求只用strong+medium
- test_select_chat_pool                    # Chat请求用full pool
- test_select_respects_health              # dead后端被排除
- test_select_sticky_priority              # sticky后端排第一
- test_inject_skills_strong_backend        # 强后端→目录模式
- test_inject_skills_weak_backend          # 弱后端→补缺模式
- test_execute_success_first_try           # 第一个后端成功
- test_execute_fallback_on_failure         # 第一个失败→下一个
- test_execute_direct_backend_on_mass_fail # 批量熔断→直连保底
- test_route_end_to_end                    # 完整流: classify→select→execute
```

## 九、deliverables

1. `D:/GIT/routing_engine.py` (~250行)
2. `D:/GIT/test_routing_engine.py` (~200行, 15个测试)
3. 全部测试通过
