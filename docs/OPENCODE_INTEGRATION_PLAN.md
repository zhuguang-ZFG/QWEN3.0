# OpenCode 新模块集成计划

## 集成点映射

### 1. opencode_session_cache.py → routing_engine.py (Line 108-120)
**位置**: `select()` 之前
**作用**: 根据 session ID 获取缓存的后端，跳过 select() 逻辑

```python
# Line 108 之后添加
if ide_source.lower() == "opencode":
    from opencode_session_cache import get_cached_backend
    session_id = (headers or {}).get("x-opencode-session-id", "")
    cached_backend = get_cached_backend(session_id)
    if cached_backend and cached_backend in health_tracker.get_health_map():
        # 使用缓存的后端
        backends = [cached_backend] + backends
```

### 2. opencode_predictive_context.py → routing_engine_context.py (inject_all_context)
**位置**: `inject_all_context()` 函数内
**作用**: 根据消息内容预加载相关文件

```python
# 在 retrieval 注入之后
if ide_source.lower() == "opencode":
    from opencode_predictive_context import load_predictive_context, format_context_injection
    context_files = load_predictive_context(messages, project_root=None)
    if context_files:
        context_str = format_context_injection(context_files)
        # 注入到第一个 user 消息
```

### 3. opencode_skill_optimizer.py → routing_engine_skills.py (inject_skills)
**位置**: `inject_skills()` 函数内
**作用**: 优化 skill 列表，跳过已内置类别

```python
# 在 skill 注入之前
if ide_source.lower() == "opencode":
    from opencode_skill_optimizer import optimize_skills_for_opencode
    skills = optimize_skills_for_opencode(skills, ide_source, has_tools=bool(tools))
```

### 4. opencode_tool_schema_simplifier.py → http_body_builder.py (build_body)
**位置**: `build_body()` 函数内，工具注入时
**作用**: 简化工具 schema

```python
# 在 tools 添加到 body 之前
if ide_source.lower() == "opencode" and tools:
    from opencode_tool_schema_simplifier import simplify_tools_array
    tools = simplify_tools_array(tools, user_agent=headers.get("user-agent", ""), backend_name=backend)
```

### 5. opencode_reasoning_budget.py → routing_engine.py 或 http_body_builder.py
**位置**: 请求体构建时
**作用**: 根据任务复杂度推荐 reasoning_effort

```python
# 在构建请求体时
if ide_source.lower() == "opencode" and "reasoning" in backend.lower():
    from opencode_reasoning_budget import recommend_reasoning_effort
    effort = recommend_reasoning_effort(query, messages, tools)
    # 设置到请求参数中
```

---

## 集成顺序

1. **会话缓存** (最简单，影响最小)
2. **Skill 优化** (已有 inject_skills，容易集成)
3. **Tool Schema 简化** (已有 http_body_builder，容易集成)
4. **Reasoning Budget** (需要传递参数)
5. **预测性上下文** (最复杂，需要文件系统访问)

---

## 测试策略

每集成一个模块后：
1. 运行 `pytest tests/test_routing_engine.py -v`
2. 运行 `pytest tests/test_opencode_optimization.py -v`
3. 验证日志输出（logger.info 应该显示优化信息）

---

## 环境变量开关

所有新模块都应该通过环境变量控制：
- `LIMA_OPENCODE_SESSION_CACHE=1` - 启用会话缓存
- `LIMA_OPENCODE_PREDICTIVE_CONTEXT=1` - 启用预测性加载
- `LIMA_OPENCODE_SKILL_SIMPLIFY=1` - 启用 Skill 精简
- `LIMA_OPENCODE_TOOL_SIMPLIFY=1` - 启用 Tool Schema 简化
- `LIMA_OPENCODE_REASONING_BUDGET=1` - 启用 Reasoning Budget

---

## 回滚计划

如果某个模块导致问题：
1. 设置对应的环境变量为 `0`
2. 模块内部会自动跳过逻辑
3. 不需要修改代码
