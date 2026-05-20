# Server 拆分重构设计

> 日期: 2026-05-20
> 目标: server.py (2100行) + smart_router.py (2276行) → 14个独立模块，每个 ≤300行
> 原则: Superpowers — 文件小/职责单一/渐进替换/本地验证

## 零、问题诊断

### server.py (2100行)
```
Routes (9)     ████████████████████ 200行  /v1/chat, /v1/messages, /admin/*...
Streaming (4)  ██████████████ 150行  _real_stream, _speculative_stream, _anthropic_stream...
Tool call (4)  ████████████ 120行  _tool_call_forward, _tool_call_stream, 3 converters...
Vision (3)     ████████████ 120行  _vision_route, _call_vision_backend...
Admin HTML/JS  ████████████████████ 200行  inline HTML+CSS+JS in ADMIN_HTML/ADMIN_JS...
Response (4)   ██████ 60行  build_response, build_anthropic_response, build_stream_chunk...
Fallback (6)   ██████ 60行  _try_backend, _quality_check, _get_same_tier_backends...
Stats (3)      ██████ 60行  _stats, _record_request, _record_fallback...
Instant (2)    ██████ 60行  _INSTANT_REPLIES, _try_instant_reply (待删除)
Helpers (5)    ██████ 60行  extract_query, _detect_ide, make_chat_id...
Format (8)     ██████████████ 140行  Anthropic↔OpenAI 转换
```

### smart_router.py (2276行)
```
Backends       ██████████████ 300行  BACKENDS dict + 配置
API call (4)   ████████████ 200行  call_api, call_api_stream, _build_request_body...
Routing (8)    ████████ 150行  classify→select→route (重复实现)
CB (3)         ████████ 50行   断路器
Local model (4) ████████ 80行   本地 Qwen3-1.7B 路由
Vision (3)     ██████ 60行   视觉检测/转换
Clean (4)      ██████ 40行   clean_response, qa_check...
Intent (5)     ██████ 60行   detect_thinking, detect_image...
Fallback (2)   ██████ 50行   get_fallback_chain...
Other          ████████████ 200行  DevToolBox, CLI, pressure_test...
```

## 一、拆分目标

| # | 新文件 | 行数 | 来源 | 职责 |
|---|--------|------|------|------|
| 1 | `server.py` | ~120 | 原server.py | FastAPI app + 路由注册(只注册，不含逻辑) |
| 2 | `backends.py` | ~200 | smart_router | BACKENDS 配置 + 后端启用/禁用 |
| 3 | `circuit_breaker.py` | ~80 | smart_router | 熔断器(cb_allow, cb_record, cb_status) |
| 4 | `routing_engine.py` | ~250 | smart_router | 统一路由(signal+rule+model分类→选择→执行) |
| 5 | `response_builder.py` | ~120 | server.py | OpenAI/Anthropic 响应格式构造 |
| 6 | `streaming.py` | ~200 | server.py | 真流式 + speculative streaming |
| 7 | `vision_handler.py` | ~150 | both | 视觉请求路由(合并两处vision逻辑) |
| 8 | `tool_handler.py` | ~120 | server.py | Tool call 转发 + Anthropic↔OpenAI 转换 |
| 9 | `fallback_chain.py` | ~130 | server.py | Fallback: 同级降级 + 跨级升级 + 质量检查 |
| 10 | `admin_routes.py` | ~250 | server.py | Admin API + stats 端点 |
| 11 | `admin_ui.html` | ~200 | server.py | Admin 页面的 HTML/CSS/JS (从字符串常量中提取) |
| 12 | `stats_collector.py` | ~100 | server.py | 请求统计收集+日志 |
| 13 | `sys_prompt_logger.py` | ~60 | server.py | System prompt 去重记录 |
| 14 | `skills_injector.py` | ~207 | 新建 | ✅ 已完成 |

## 二、各模块详细设计

### 2.1 server.py (~120行)
```python
# 只做: FastAPI app 创建 + 路由注册
app = FastAPI()
app.post("/v1/chat/completions")(chat_routes.chat_completions)
app.post("/v1/messages")(chat_routes.anthropic_messages)
app.get("/v1/models")(admin_routes.list_models)
app.get("/health")(admin_routes.health)
app.get("/v1/status")(admin_routes.router_status)
app.get("/admin")(admin_routes.admin_page)
# ...其他 admin 路由
# startup: warmup + run uvicorn
```

### 2.2 backends.py (~200行)
- 从 smart_router.py 迁移 BACKENDS 字典
- 后端启用/禁用状态 `_backend_enabled`
- 后端元数据查询(供应商/层级/协议/能力自动检测)
- 不包含路由逻辑

### 2.3 routing_engine.py (~250行)
- 合并 router_v3.py + smart_router 的路由逻辑
- `classify_request()` → V3 三层分类
- `select_backend()` → 健康感知 + P2C
- `execute()` → 执行 + fallback
- 删除旧的 `smart_router.route()` (已有 V3 替代)

### 2.4 response_builder.py (~120行)
- `build_response()` — OpenAI 非流式
- `build_anthropic_response()` — Anthropic 非流式
- `build_stream_chunk()` — OpenAI SSE chunk
- `make_chat_id()`, `_split_sentences()`

### 2.5 streaming.py (~200行)
- `_real_stream_chunks()` — 真流式桥接
- `_speculative_stream_chunks()` — 预测流式
- `_stream_response()` — OpenAI 流式
- `_anthropic_stream()` — Anthropic 流式

### 2.6 vision_handler.py (~150行)
- 合并 server.py 的 `_vision_route` + smart_router 的 `detect_vision_request` + `convert_openai_vision_to_anthropic`
- `route_vision()` — 视觉请求路由
- `detect_vision()` — 检测是否视觉请求
- `convert_vision_format()` — Anthropic↔OpenAI 视觉格式

### 2.7 tool_handler.py (~120行)
- `_tool_call_forward()` — 非流式工具转发
- `_tool_call_stream()` — 流式工具转发
- `convert_tools_anthropic_to_openai()`
- `convert_messages_anthropic_to_openai()`
- `convert_response_openai_to_anthropic()`

### 2.8 fallback_chain.py (~130行)
- `quality_check()` — 质量检查
- `get_same_tier_backends()` — 同级后端
- `get_upgrade_chain()` — 升级链
- `try_backend()` — 单后端尝试
- `default_route()` — 默认路由

## 三、迁移策略 (渐进式，零停机)

### Phase 1: 提取独立模块 (不删除旧代码)
1. 创建 `response_builder.py` → server.py import 使用
2. 创建 `streaming.py` → server.py import 使用
3. 创建 `vision_handler.py` → server.py import 使用
4. 创建 `tool_handler.py` → server.py import 使用
5. 创建 `backends.py` → smart_router.py import 使用
6. 创建 `fallback_chain.py` → server.py import 使用
7. 创建 `stats_collector.py` + `sys_prompt_logger.py`

### Phase 2: 清理 server.py
8. 替换 server.py 内联代码为 import 调用
9. server.py 从 2100 → ~400 行 (路由注册+App)

### Phase 3: 统一路由
10. 创建 `routing_engine.py`，合并 V3 + smart_router 路由
11. server.py 的 `_handle_chat` 改用 routing_engine

### Phase 4: Admin 分离
12. 提取 `admin_ui.html` 为独立文件
13. 创建 `admin_routes.py`

## 四、不可变规则

- server.py 的 API 签名不变 (IDE 侧零感知)
- 所有现有测试通过后才进入下一 phase
- 每 phase 一个 commit
- `patch_server_v3.py` 随重构更新

## 五、删除清单

| 删除内容 | 原因 |
|---------|------|
| `_INSTANT_REPLIES` + `_try_instant_reply` | preset replies interfere with routing |
| `smart_router.route()` 旧路由 | V3 routing_engine 替代 |
| `smart_router.classify_request()` 旧分类 | router_v3.classify_request 替代 |
| server.py ADMIN_HTML/ADMIN_JS 内联字符串 | 移到 admin_ui.html |
| smart_router DevToolBox/call_devtoolbox | 无用代码 |
| smart_router pressure_test | 开发工具，移到 scripts/ |
| smart_router CLI/MCP entry | 如果不再使用 |

## 六、目标最终结构

```
D:/GIT/
├── server.py               ~120行  FastAPI app
├── routing_engine.py       ~250行  统一路由
├── backends.py             ~200行  后端配置
├── circuit_breaker.py      ~80行   熔断器
├── response_builder.py     ~120行  响应格式
├── streaming.py            ~200行  流式处理
├── vision_handler.py       ~150行  视觉路由
├── tool_handler.py         ~120行  工具转发
├── fallback_chain.py       ~130行  Fallback
├── stats_collector.py      ~100行  统计收集
├── sys_prompt_logger.py    ~60行   Prompt记录
├── admin_routes.py         ~250行  Admin API
├── admin_ui.html           ~200行  Admin UI
├── router_v3.py            ✅ 226行  三层分类+P2C
├── health_tracker.py       ✅ 120行  健康追踪
├── sticky_session.py       ✅ 65行   会话亲和
├── key_pool.py             ✅ 143行  Key轮转
├── semantic_cache.py       ✅ 104行  精确缓存
├── probe_loop.py           ✅ 81行   主动探活
├── skills_injector.py      ✅ 207行  智能补缺
├── v3_integration.py       ✅ 112行  统一入口
├── deploy_v3.py            ✅ 91行   一键部署
├── patch_server_v3.py      ✅ 135行  服务器patch
└── skills/                 ✅ 6个skill文件
```

总模块数: 20 | 平均行数: ~140 | 最大行数: ~250
