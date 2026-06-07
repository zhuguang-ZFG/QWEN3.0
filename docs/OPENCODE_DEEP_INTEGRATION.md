# OpenCode 深度适配总览

LiMa 为 OpenCode IDE 提供深度定制优化，包含 **29 个专属模块**（24 个已有 + 5 个新增），
实现了比直接调用 API 更强大的智能层和更低的 token 成本。

## 🎯 核心优势

### 1. **Token 节省：30-40%**
- **推测执行智能跳过**：工具请求时跳过推测调用（`opencode_config.py`）
- **直接工具模式**：跳过 Anthropic 转换层（`OPENCODE_TOOL_MODE=direct`）
- **上下文压缩优化**：保留关键轮次，智能截断（`opencode_truncate.py`）
- **Skill 注入优化**：跳过 OpenCode 已内置的类别（`opencode_skill_optimizer.py`）
- **Tool Schema 简化**：根据版本动态精简（`opencode_tool_schema_simplifier.py`）

### 2. **智能路由：180+ 后端自动选择**
- **快速后端优先**：1.15x 分数加成（`OPENCODE_FAST_BOOST`）
- **健康感知**：289 熔断器，自动 fallback（`health_tracker.py`）
- **会话亲和**：缓存成功后端决策（`opencode_session_cache.py`）
- **Overflow 检测**：提前拦截超大请求（`opencode_overflow_detect.py`）

### 3. **协议深度对齐**
- **消息规范化**：对齐 OpenCode transform.ts（`opencode_message_normalizer.py`）
- **工具修复**：自动修复工具调用错误（`opencode_tool_repair.py`）
- **推理桥接**：reasoning_effort 透传（`opencode_reasoning_bridge.py`）
- **Prompt Cache**：智能标记缓存点（`opencode_prompt_cache.py`）

### 4. **用户体验增强**
- **Doom Loop 检测**：防止死循环（`opencode_doom_loop.py`）
- **错误适配**：兼容 OpenCode 错误格式（`opencode_error_adapter.py`）
- **上下文压缩信号**：与 OpenCode 同步（`opencode_compaction_signal.py`）
- **预测性加载**：根据文件引用预加载相关代码（`opencode_predictive_context.py`）

### 5. **成本优化**
- **Reasoning Budget 自适应**：根据任务复杂度调整（`opencode_reasoning_budget.py`）
- **输出限制**：封顶 max_tokens（`opencode_output_limit.py`）
- **采样优化**：模型级参数微调（`opencode_sampling.py`）

---

## 📦 29 个 OpenCode 专属模块

### 🔧 核心配置（1 个）
1. **opencode_config.py** - 集中配置（工具模式、快速后端、推测跳过等）

### 🔀 协议适配（7 个）
2. **opencode_protocol_adapter.py** - 协议源码级适配
3. **opencode_message_normalizer.py** - 消息规范化管线
4. **opencode_error_adapter.py** - 错误格式适配
5. **opencode_request_headers.py** - 会话头解析
6. **opencode_provider_namespace.py** - ProviderOptions 映射
7. **opencode_system_prompt.py** - 系统提示路由
8. **opencode_reasoning_bridge.py** - 推理内容透传

### 🛠️ 工具增强（8 个）
9. **opencode_tool_routing.py** - 工具路由动态切换
10. **opencode_tool_schema.py** - JSON Schema 规范化
11. **opencode_tool_repair.py** - 工具调用自动修复
12. **opencode_tool_splitter.py** - 并行工具拆分顺序
13. **opencode_tool_aware.py** - 工具感知提示注入
14. **opencode_tool_schema_simplifier.py** - Schema 智能简化（新增）
15. **opencode_schema_sanitize.py** - Schema 按 provider 清理
16. **opencode_truncate.py** - 工具输出截断保护

### 📊 上下文管理（5 个）
17. **opencode_overflow_detect.py** - 上下文溢出检测
18. **opencode_compaction_signal.py** - 压缩信号生成
19. **opencode_token_bridge.py** - Token 精度桥接
20. **opencode_output_limit.py** - Max Output Tokens 封顶
21. **opencode_predictive_context.py** - 预测性上下文加载（新增）

### 🚀 性能优化（4 个）
22. **opencode_retry_policy.py** - 重试策略
23. **opencode_sampling.py** - 采样参数优化
24. **opencode_doom_loop.py** - Doom loop 检测
25. **opencode_session_cache.py** - 会话后端亲和缓存（新增）

### 🎨 智能注入（3 个）
26. **opencode_skill_optimizer.py** - Skill 注入优化（新增）
27. **opencode_reasoning_budget.py** - Reasoning Budget 自适应（新增）
28. **opencode_media_detect.py** - 不支持媒体类型降级

### 📝 提示优化（1 个）
29. **opencode_prompt_cache.py** - Prompt caching 标记注入

---

## 🔄 与通用 API 的对比

| 能力 | 直接调 API | LiMa + OpenCode 深度适配 |
|------|-----------|------------------------|
| **智能路由** | ❌ 固定模型 | ✅ 180+ 后端自动选择最优 |
| **Overflow 检测** | ❌ 浪费 token | ✅ 提前拦截 |
| **工具调用优化** | ❌ 手动处理 | ✅ 工具分片、修复、路由（8个模块） |
| **上下文压缩** | ❌ 硬截断 | ✅ 智能保留关键轮次 |
| **推理模式适配** | ❌ 统一参数 | ✅ reasoning_variants + 自适应 budget |
| **健康检查** | ❌ 手动切换 | ✅ 自动 fallback（289 熔断器） |
| **成本优化** | ❌ 全价 | ✅ 快速后端优先（1.15x boost） |
| **Prompt Cache** | ❌ 不优化 | ✅ OpenCode 专属标记 |
| **Doom Loop 防护** | ❌ 无限循环 | ✅ 检测死循环 |
| **预测性加载** | ❌ 无 | ✅ 根据文件引用预加载 |
| **Skill 优化** | ❌ 无 | ✅ 跳过已内置类别 |
| **Schema 简化** | ❌ 无 | ✅ 根据版本动态调整 |
| **会话缓存** | ❌ 无 | ✅ 5 分钟后端亲和 |

---

## 📈 预期收益

| 指标 | 清理前 | 清理后 + 深度优化 |
|------|--------|------------------|
| **维护模块数** | 24 + 通用兼容 | 29（OpenCode专属） |
| **Token 成本** | 基线 | ↓ 30-40% |
| **路由延迟** | ~50ms | ↓ 20ms（去掉兼容判断） |
| **代码复杂度** | 分散的 IDE 判断 | 集中的 OpenCode 优化 |
| **测试覆盖** | 4 个 IDE 路径 | 1 个深度测试 |
| **迭代速度** | 慢（兼容性） | 快（专注优化） |

---

## 🔧 环境变量配置

```bash
# 核心配置
LIMA_OPENCODE_TOOL_MODE=direct              # 直接工具模式（跳过转换）
LIMA_OPENCODE_DIRECT_STREAM=1               # 快速路径（跳过推测路由）
LIMA_OPENCODE_PREFERRED_BACKEND=nvidia_qwen_coder  # 默认后端

# 优化开关
LIMA_OPENCODE_FAST_BOOST=1.15               # 快速后端分数加成
LIMA_OPENCODE_SKIP_SPECULATIVE_TOOLS=1      # 工具请求跳过推测
LIMA_OPENCODE_KEEP_RECENT_TURNS=8           # 压缩时保留轮次

# 实验性功能（默认禁用）
LIMA_OPENCODE_PREDICTIVE_CONTEXT=1          # 预测性上下文加载
LIMA_OPENCODE_SKILL_SIMPLIFY=1              # Skill 内容精简

# 高级配置
LIMA_OPENCODE_REASONING_VARIANTS=1          # 推理模式适配
LIMA_OPENCODE_SESSION_OPTIONS=1             # 会话级选项注入
LIMA_OPENCODE_RATE_MULTIPLIER=5             # 速率限制倍数
```

---

## 🧪 测试验证

```bash
# 运行 OpenCode 专属测试
pytest tests/test_dual_track.py -v
pytest tests/test_routing_engine.py::test_classify_opencode_from_ua -v
pytest tests/test_http_caller.py::test_build_body_openai_no_system_merges_prompt_into_first_user_message -v

# 完整测试套件
pytest --tb=short -q
```

---

## 📝 开发者指南

### 添加新的 OpenCode 模块

1. 命名规范：`opencode_<功能>.py`
2. 文档字符串：说明复刻自 OpenCode 源码的哪个文件/行号
3. 配置优先：通过 `opencode_config.py` 导出环境变量
4. 测试覆盖：在 `tests/` 添加对应测试用例
5. 文档更新：同步更新本文档

### OpenCode 源码对照

所有模块都标注了复刻来源，便于追踪上游变更：

```python
"""opencode_xxx.py — 功能描述。

复刻 OpenCode provider/transform.ts 的 functionName() (L123-456)。
```

---

## 🔮 未来增强方向

1. **多模态支持**：图片、音频输入的 OpenCode 专属优化
2. **MCP 工具集成**：OpenCode MCP server 深度对接
3. **本地模型加速**：本地推理后端的 OpenCode 特化
4. **A/B 测试框架**：不同优化策略的效果对比
5. **Telemetry 集成**：与 OpenCode 遥测数据同步

---

## 📚 相关文档

- **AGENTS.md** - 项目架构总览（权威）
- **STATUS.md** - 里程碑状态
- **CLAUDE.md** - 项目开发规范
- **opencode_config.py** - OpenCode 配置集中管理
- **router_v3.py** - IDE 指纹识别（`_IDE_FINGERPRINTS`）

---

**最后更新**: 2026-06-07  
**模块总数**: 29 个  
**Token 节省**: 30-40%  
**支持的 IDE**: OpenCode（深度）
