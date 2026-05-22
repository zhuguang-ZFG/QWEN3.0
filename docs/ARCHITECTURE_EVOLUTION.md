# LiMa 架构进化文档 — 多项目深度集成记录

> 本文档记录 LiMa 从"API 路由器"升级为"上下文感知自进化智能编码后端"的完整过程，
> 包括所有参考项目、论文、实施阶段和架构决策。

## 一、参考项目清单

### 1.1 核心参考项目

| 项目 | GitHub | 核心贡献 | 集成 Phase |
|------|--------|---------|-----------|
| Google ADK Python | google/adk-python | Processor Pipeline, Context Compaction, Artifact Handle, Narrative Casting, Event Session | P0, P2, P5, P6, 8, 9, 11, 12 |
| piia-engram | Patdolitse/piia-engram | 用户身份层, 经验教训, 知识继承, MCP 集成 | 7 |
| claude-mem | thedotmack/claude-mem | 渐进式披露, 生命周期钩子, AI 摘要压缩 | P1, 8 |
| all-agentic-architectures | FareedKhan-dev/all-agentic-architectures | Reflection, Ensemble, PEV, Meta-Controller | P3, P4 |
| vibe-coding-cn | (内部) | 五层 Prompt 框架, 质量门控 | P0 (prompt_engineering) |
| GenericAgent | lsdefine/GenericAgent | 5层分级记忆, Skill 结晶, Token 效率 (6x) | 16, 17, 21 |
| Evolver | EvoMap/evolver | GEP 进化策略, Signal Extraction, 审计追踪 | 18, 20 |
| OpenAI Agents Python | openai/openai-agents-python | Guardrails, Tracing, Sessions, Handoffs | 19, 22 |
| LightRAG | zhuguang-ZFG/LightRAG | 双层检索, 知识图谱, Entity Extraction, Reranking | 23, 24, 25 |
| agency-agents | msitarzewski/agency-agents | Agent-as-Router 专业化, 成功指标 | 架构参考 |

### 1.2 参考论文

| 论文 | 来源 | 核心创新 | 集成 Phase |
|------|------|---------|-----------|
| AgentConductor | arXiv 2025 | 任务自适应动态协作, Token 消耗降低 68% | 14 |
| Solvita | 南京大学+清华 2026 | 4-Agent 闭环 + 可学习知识网络, 解题率 40%→82.4% | 15 |
| RecursiveMAS | Stanford+NVIDIA 2026 | 潜空间递归, 推理速度 2.4x | 评估后未集成 (不适用) |
| Qoder | 阿里通义 2026 | 自主软件工程 Agent, 大规模代码处理 | 架构参考 |

---

## 二、实施阶段详细记录

### Phase P0: Processor Pipeline (Google ADK)

**文件:** `context_pipeline/pipeline.py`, `context_pipeline/processors.py`, `context_pipeline/factory.py`

**设计决策:** 采用 Google ADK 的 Callable 函数式处理器模式，而非类继承。
每个处理器是 `(RequestContext) -> RequestContext` 的纯函数，通过 Pipeline 类有序链接。

**5 个默认处理器:**
1. `ide_detection_processor` — 从 User-Agent 和 system prompt 标记检测 IDE
2. `scenario_classification_processor` — 分类为 coding/chat/vision
3. `code_context_processor` — 语义搜索相关代码文件
4. `prompt_composition_processor` — 构建结构化 system prompt
5. `cache_optimization_processor` — 重排 prompt 以优化前缀缓存

### Phase P1: Session Memory (Google ADK + claude-mem)

**文件:** `session_memory/store.py`, `session_memory/processor.py`

**设计决策:** SQLite 存储 + 内存向量索引。每条记忆有 summary（短）和 detail（全），
检索时只返回 summary（渐进式披露）。Session ID 由 IP+User-Agent 哈希生成。

### Phase P2: Context Caching (Google ADK)

**文件:** `context_pipeline/cache.py`

**设计决策:** 相同 IDE+scenario 组合产生相同的 stable prefix bytes，
利用 LLM 提供商的前缀缓存机制。CacheMetrics 追踪唯一前缀数/总请求数估算命中率。

### Phase P3: Reflection (all-agentic-architectures)

**文件:** `context_pipeline/reflection.py`

**设计决策:** 路由决策后、发送请求前的自检。检查后端能力与请求场景的匹配：
- IDE coding 不应路由到弱后端
- Vision 请求需要 vision-capable 后端
- Coding 请求优先 coding-capable 后端

### Phase P4: Ensemble (all-agentic-architectures)

**文件:** `context_pipeline/ensemble.py`

**设计决策:** 对关键 IDE coding 请求，同时发送到 2-3 个后端，取最快成功响应（race 策略）。使用 asyncio.as_completed 实现，第一个成功后取消其余任务。

### Phase P5: Artifact Handle (Google ADK)

**文件:** `context_pipeline/artifact.py`

**设计决策:** 大文件（>200 行或 >10KB）不内联注入 prompt，而是用轻量句柄引用（路径 + 行数 + top-5 符号）。减少 token 浪费，保留上下文信息密度。

### Phase P6: Event Log (Google ADK)

**文件:** `context_pipeline/event_log.py`

**设计决策:** 10 种结构化事件类型，环形缓冲区（500 事件上限），支持 filter/summary/last 查询。Phase 11 升级为 contextvars 异步安全。

### Phase 7: User Identity (piia-engram)

**文件:** `user_identity/profile.py`, `user_identity/lessons.py`, `user_identity/adapter.py`

**设计决策:** 持久化用户身份层。Profile 按 session_id 存 JSON，Lessons 记录路由失败经验，Adapter 根据 tech_level 动态调整 prompt（senior 简洁 / beginner 详细）。

### Phase 8: AI Compactor (Google ADK + claude-mem)

**文件:** `session_memory/compactor.py`, `session_memory/hooks.py`

**设计决策:** 记忆超 20 条时触发压缩。滑动窗口取最旧 10 条用 LLM 摘要替换。生命周期钩子：on_request_start / on_response_complete / on_error。

### Phase 9: Response Pipeline (Google ADK)

**文件:** `context_pipeline/response_pipeline.py`, `context_pipeline/response_processors.py`

**设计决策:** 与 Request Pipeline 对称的响应后处理管线。4 个处理器：quality_check、memory_capture、event_recording、lesson_extraction。

### Phase 11: EventLog Async Safety

**文件:** `context_pipeline/event_log.py` (修改)

**设计决策:** 全局变量替换为 contextvars.ContextVar，确保并发 async 请求隔离。

### Phase 12: Narrative Casting (Google ADK)

**文件:** `context_pipeline/narrative.py`

**设计决策:** Backend fallback 时将前一个 assistant 消息标记为参考，防止新后端身份混淆。

### Phase 14: Complexity Assessor (AgentConductor 论文)

**文件:** `context_pipeline/complexity.py`

**设计决策:** 5 因子复杂度评分（1-10）驱动动态拓扑：score<=3 direct, 4-6 single_strong, 7-10 ensemble_race。

### Phase 15: Routing Weights (Solvita 论文)

**文件:** `context_pipeline/routing_weights.py`

**设计决策:** 每 backend+scenario 维护权重。成功 +0.05（上限 2.0），失败 -0.1（下限 0.1）。JSON 持久化。

### Phase 16: Hierarchical Memory (GenericAgent)

**文件:** `context_pipeline/hierarchical_memory.py`

**设计决策:** 5 层分级记忆：L0 规则 / L1 性能 / L2 事实 / L3 技能 / L4 归档。

### Phase 17: Skill Crystallization (GenericAgent)

**文件:** `context_pipeline/skill_store.py`

**设计决策:** 成功路由结晶为技能（SHA256 key），TTL 72h，LRU 淘汰。相似请求直接复用。

### Phase 18: Evolution Strategies (Evolver GEP)

**文件:** `context_pipeline/evolution.py`

**设计决策:** 4 种策略（balanced/innovate/harden/repair），基于错误率和后端可用性自动切换。

### Phase 19: Guardrails (OpenAI Agents)

**文件:** `context_pipeline/guardrails.py`

**设计决策:** 输入验证（注入检测 6 模式、长度 200K、格式）+ 输出验证（危险命令）。三级严重度。

### Phase 20: Signal Extraction (Evolver)

**文件:** `context_pipeline/signal_extraction.py`

**设计决策:** 从 EventLog 提取进化信号：critical_error_rate / backend_repeated_failure / latency_spike。

### Phase 21: Token Budget (GenericAgent)

**文件:** `context_pipeline/token_budget.py`

**设计决策:** 粗略估算（4 chars/token EN, 2 CJK）。按场景分配预算，超预算推荐 truncate 或 downgrade。

### Phase 22: Request Tracing (OpenAI Agents)

**文件:** `context_pipeline/tracing.py`

**设计决策:** 每请求 trace_id + Span 嵌套追踪。contextvars 作用域，export() 输出结构化 dict。

### Phase 23: Entity Extraction (LightRAG)

**文件:** `context_pipeline/entity_extraction.py`

**设计决策:** 正则提取 6 类代码实体（文件/函数/类/模块/错误/技术），驱动图检索。

### Phase 24: Graph-aware Retrieval (LightRAG)

**文件:** `context_pipeline/graph_retrieval.py`

**设计决策:** CodeGraph BFS 遍历 + 向量结果合并。双通道命中 +0.3 boost。

### Phase 25: Reranking (LightRAG)

**文件:** `context_pipeline/reranking.py`

**设计决策:** Entity overlap +0.4, dual-source +0.3, relation count +0.1。format_for_injection 带字符预算。

---

## 三、完整架构图

```
HTTP Request
  |
  +-- [Phase 19: Guardrails] injection/format/length validation
  |
  +-- [Phase 22: Tracing] new_trace() -> trace_id assigned
  |
  +-- [Phase 20: Signal Extraction] -> auto_select_strategy()
  |     -> balanced / innovate / harden / repair
  |
  +-- [Request Pipeline (P0)]
  |   +-- IDE Detection (12 IDEs)
  |   +-- [Phase 23] Entity Extraction (files, funcs, classes, errors)
  |   +-- Scenario Classification (coding/chat/vision)
  |   +-- [Phase 7] User Identity (tech_level -> prompt adaptation)
  |   +-- Code Context: dual-layer retrieval
  |   |   +-- [P1] Vector Search (cosine similarity)
  |   |   +-- [Phase 24] Graph Search (structural relations)
  |   |   +-- [Phase 25] Reranking (entity overlap + dual-source boost)
  |   +-- Prompt Composition (vibe-coding 4-layer)
  |   +-- [Phase 21] Token Budget Check (truncate/downgrade if over)
  |   +-- [P2] Cache Optimization (stable prefix first)
  |
  +-- [Phase 17: Skill Recall] -> cached routing skill? -> direct reuse
  |
  +-- [Phase 14: Complexity Assessment] -> score 1-10 -> parallelism
  |
  +-- [P3: Reflection] -> pre-routing self-check
  |
  +-- [Phase 15: Routing Weights] -> experience-ranked backend list
  |
  +-- [Phase 18: Evolution Strategy] -> filter backends by mode
  |
  +-- [P4: Ensemble / Direct] -> execute routing
  |
  +-- [Phase 12: Narrative Casting] -> fallback handoff reframing
  |
  +-- [Response Pipeline (Phase 9)]
      +-- Quality Check (empty/garbled/truncated/HTTP error)
      +-- Memory Capture (response summary -> session memory)
      +-- [P6/11] Event Recording (structured observability)
      +-- Lesson Extraction (failure -> routing lesson)
      +-- [Phase 17] Skill Crystallization (success -> cached skill)
      +-- [Phase 15] Routing Weight Update (success +0.05 / failure -0.1)
      +-- [Phase 8] Session Compaction (>20 entries -> LLM summarize)
```

---

## 四、设计原则 (superpowers)

1. **函数式处理器** -- 每个处理器是纯函数 (Context) -> Context，无类继承
2. **渐进式披露** -- 记忆系统先返回摘要，按需加载详情
3. **经验驱动** -- 路由权重从历史成功/失败中学习，无需人工调参
4. **自进化** -- 系统根据健康状态自动切换进化策略
5. **双层检索** -- 向量相似度 + 结构关系图，比纯向量提升 21%
6. **Token 效率** -- 预算控制 + Artifact Handle + 压缩，目标 6x 降本
7. **异步安全** -- 所有全局状态使用 contextvars，支持并发请求
8. **可观测性** -- Event Log + Tracing + Signal Extraction 全链路追踪

---

## 五、测试覆盖

总计 308 tests passed, 0 failed (含原有测试 + 147 新增测试)

---

## 六、未来方向

| 方向 | 来源 | 描述 |
|------|------|------|
| Phase 10: PEV Loop | all-agentic-architectures | Plan-Execute-Verify 闭环 |
| Phase 13: MCP Server | piia-engram + OpenSkills | 暴露 LiMa 能力为 MCP 工具 |
| LightRAG Server 集成 | LightRAG | 接入 REST API 做真实知识图谱检索 |
| RecursiveMAS 向量路由 | Stanford+NVIDIA | 请求向量相似度匹配历史成功路由 |
| Qoder 大代码分块 | 阿里通义 | 超长代码自动分块 + 摘要 |
| AgentConductor 深度集成 | arXiv 2025 | 动态工作流拓扑生成 |
| Solvita 知识网络 | 南京大学+清华 | 可学习权重网络替代线性权重 |

---

*文档生成时间: 2026-05-22*
*分支: codex/free-web-ai-probe*
*最终回归: 308 passed, 0 failed*

