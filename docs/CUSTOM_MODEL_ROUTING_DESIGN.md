# 客户端自定义模型路由设计文档

> Created: 2026-06-03 · Milestone: M23 (proposed)

## 背景

当前 LiMa 的 `model` 参数在请求中被忽略——路由引擎完全自主选择后端。用户无法指定使用某个特定模型或后端。

**目标**: 让客户端能通过 `model` 参数指定后端，同时保留 LiMa 的自动路由作为默认行为。

## 参考

| 项目 | 做法 | 借鉴 |
|------|------|------|
| OpenRouter | `model=anthropic/claude-3-opus` 格式，直接透传 | 前缀命名空间 |
| LiteLLM | `model=bedrock/claude-3-opus`，路由到对应 provider | 多 provider 统一前缀 |
| vLLM | `--served-model-name` 别名映射 | 别名表 |

## 设计方案

### 模型名匹配规则（优先级从高到低）

```
1. 完全匹配后端名     → 直接使用该后端
2. 前缀匹配后端名     → 匹配到的后端
3. model_alias 映射   → 查别名表
4. 无匹配            → 走自动路由（现有行为）
```

### 模型名格式

| 格式 | 示例 | 行为 |
|------|------|------|
| 直接后端名 | `github_gpt4o` | 直接使用 github_gpt4o 后端 |
| 别名 | `gpt4o` | 查 alias 表 → `github_gpt4o` |
| 通配 | `auto` / 空 / 任意未匹配 | 自动路由（现有行为不变） |

**不采用** OpenRouter 的 `vendor/model` 双层格式，因为 LiMa 已有扁平化的后端名（如 `github_gpt4o`），无需额外命名空间。

### 新增配置：model_alias

在 `backends_constants.py` 中新增：

```python
# 客户端模型别名 → 后端名
MODEL_ALIASES = {
    "gpt-4o": "github_gpt4o",
    "gpt-4o-mini": "github_gpt4o_mini",
    "deepseek-v3": "scnet_ds_pro",
    "deepseek-v2.5": "scnet_ds_flash",
    "qwen-max": "scnet_qwen235b",
    "qwen-plus": "scnet_qwen30b",
    "claude-3-opus": "longcat_chat",
    "claude-3-haiku": "longcat_lite",
    "llama-3-70b": "groq_llama70b",
    "llama-3-8b": "groq_llama8b",
    # ... 可通过 admin 面板动态扩展
}
```

### 代码改动

#### 1. 新增 `resolve_backend()` 函数

文件: `routing_engine.py` 或新建 `model_resolver.py`

```python
def resolve_backend(model: str) -> str | None:
    """解析客户端 model 参数到后端名。
    
    Returns: 后端名或 None（表示走自动路由）
    """
    if not model or model in ("auto", "lima-1.3", ""):
        return None
    
    # 1. 完全匹配后端名
    if model in BACKENDS:
        return model
    
    # 2. 别名匹配
    alias = MODEL_ALIASES.get(model)
    if alias and alias in BACKENDS:
        return alias
    
    # 3. 无匹配 → 自动路由
    return None
```

#### 2. 修改 `routing_engine.route()`

在 `route()` 入口处增加 model → backend 解析：

```python
def route(query, messages, *, model="", ...):
    # 新增: 解析客户端指定的后端
    forced_backend = resolve_backend(model)
    
    if forced_backend:
        # 客户端指定了后端，跳过自动选择
        backends = [forced_backend]
        # 仍然做健康检查，dead 则降级到自动路由
        if health_tracker.is_cooled_down(forced_backend):
            forced_backend = None  # 降级
        else:
            backends = [forced_backend]
    
    if not forced_backend:
        # 原有自动路由逻辑
        backends = select(req_type, hmap, ...)
```

#### 3. 修改 `routing_selector.select()` (可选)

增加 `forced_backend` 参数，在选择前检查健康状态。

#### 4. Admin 面板

- 后端编辑页新增「别名」字段
- `MODEL_ALIASES` 支持通过 `/admin/api/model-aliases` API 动态增删

### 不改动的部分

- `/v1/models` 端点：返回 LiMa 支持的模型列表（含别名）
- 自动路由：未匹配时完全不变
- 工具调用路径：tool_forward 不受影响（工具路径已有独立后端选择逻辑）
- Anthropic 协议 `/v1/messages`：`model` 参数同样适用此逻辑

### 安全边界

- 客户端只能选择**已配置且启用**的后端，不能路由到不存在的后端
- 被 cooldown 的后端即使被指定也降级到自动路由
- `LIMA_ALLOW_MODEL_OVERRIDE=true` 环境变量控制是否启用此功能（默认 true，因为是个人助手非多租户）

### 对 IDE 客户端的影响

LiMa (deepcode-cli) 和 Cursor/Copilot 等客户端通常传 `model=gpt-4o` 或 `model=claude-3-opus`。启用此功能后，这些请求将**自动匹配到对应后端**，无需客户端修改。

### 风险

| 风险 | 缓解 |
|------|------|
| 用户指定已死的后端 | 降级到自动路由 |
| 别名表过时 | Admin 面板可动态更新 |
| 增加路由延迟 | resolve_backend 是 O(1) 字典查找，影响可忽略 |

## 实施计划

| Task | 内容 | 文件 | 优先级 |
|------|------|------|--------|
| T1 | 实现 resolve_backend() | model_resolver.py (新建) | CRITICAL |
| T2 | route() 接入 forced_backend | routing_engine.py | CRITICAL |
| T3 | MODEL_ALIASES 定义 | backends_constants.py | HIGH |
| T4 | /v1/models 返回别名列表 | routes/models.py | MEDIUM |
| T5 | Admin 面板别名管理 | routes/admin_ui.py | LOW |
| T6 | 测试覆盖 | tests/test_model_resolver.py | VERIFY |

预估改动: ~100 行新代码 + ~20 行修改。
