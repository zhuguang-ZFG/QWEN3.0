# LiMa 子系统深度分析（做梦模式）

> **状态**：架构隐喻草稿（2026-06-16 勘误）— **非 SSOT**
> **勘误与未解谜题**：[`DREAM_MODE_ERRATA_CN.md`](DREAM_MODE_ERRATA_CN.md)
> **权威分层**：[`CODEBASE_SUBSYSTEM_TIER_CN.md`](CODEBASE_SUBSYSTEM_TIER_CN.md)
>
> CP-1/CP-2 已退役 `evolution`、`reflection`、`hierarchical_memory` 等；下文 Layer 图若未标注「已退役」则以勘误表为准。

> 本文档对 LiMa **聊天/设备并列**子系统做深度隐喻分析（主文档 **§1–9**）。
> 每个分析包含：架构全景、核心机制、隐喻解读。
> §10–15 见 [`DREAM_MODE_ALL_SUBSYSTEMS_CN.md`](DREAM_MODE_ALL_SUBSYSTEMS_CN.md)。

## 目录

1. [Routing Selector — 路由选择器](#1-routing-selector--路由选择器)
2. [Device Memory — 设备记忆系统](#2-device-memory--设备记忆系统)
3. [Context Pipeline — 上下文管线](#3-context-pipeline--上下文管线)
4. [Observability — 可观测性系统](#4-observability--可观测性系统)
5. [Session Memory — 会话记忆系统](#5-session-memory--会话记忆系统)
6. [Device Gateway — 设备网关](#6-device-gateway--设备网关)
7. [Health Tracking — 健康追踪系统](#7-health-tracking--健康追踪系统)
8. [Prompt Engineering — 提示工程](#8-prompt-engineering--提示工程)
9. [Skills Injector — 技能注入器](#9-skills-injector--技能注入器)

**补充（§10–15）**：[`DREAM_MODE_ALL_SUBSYSTEMS_CN.md`](DREAM_MODE_ALL_SUBSYSTEMS_CN.md)

---

## 1. Routing Selector — 路由选择器

**模块路径**: `routing_selector.py`, `routing_engine.py`, `router_v3.py`, `route_scorer.py`

### 架构全景

路由选择器是一个 **多层过滤器**（2026-06-16，已移除进化策略层与 hierarchical_memory 加成）：

```
Layer 0: 池选择 (router_v3.select_backends)
    ↓ 从 POOLS[ide/chat/code/vision/chat_fast] 取候选
Layer 1: 退役过滤 (_is_retired)
Layer 2: 工具能力过滤 (needs_tools)
Layer 3: 预算过滤 (budget_manager)
Layer 4: 隔离过滤 (routing_guard)
Layer 5: 多维评分 (健康/延迟/错误/routing_weights/ML/编码质量)
Layer 6: 排序 + 冷却过滤
Layer 7: 粘性绑定 (sticky/preferred/recalled)
```

> **已退役（CP-1/CP-2）**：`evolution` 策略切换、`signal_extraction` 事件驱动重排、`hierarchical_memory` 1.15 加成。

### 评分公式

```python
final_score = (
    base_score                                    # 健康评分 (0-100)
    * latency_score                               # 延迟分 (0.1-1.0)
    * (1 - error_penalty)                         # 错误惩罚 (0.1-0.9)
    * recency_bonus                               # 新鲜度 (0-1.0)
    * routing_weights.get_weight(b, scenario)     # 经验权重 (0.1-2.0)
    * coding_weight                               # 编码质量 (仅coding场景)
    + static_latency_bonus                        # 静态延迟奖励
    * guard_penalty                               # 守卫惩罚 (0.05-1.0)
    * ml_boost                                    # ML加成 (1.0-1.3)
    * budget_priority                             # 预算优先级
)
```

> `memory_boost`（hierarchical_memory）已随 CP-1 移除。

### 核心机制

- **GRPO 学习**: 相对评分 against 同场景其他后端的平均表现，±0.15 权重调整，0.08 学习率（`routing_weights`）
- **粘性会话**: 前 512 字节 hash → 绑定后端 → 5 分钟 TTL

### 隐喻

路由选择器像人类的**决策系统**——综合考虑多种因素（健康、速度、成本、经验），做出最优选择。

---

## 2. Device Memory — 设备记忆系统

**模块路径**: `device_memory/` (9 个模块)

### 架构全景

```
设备任务执行 → 终端事件 → 提取器(extractor) → 原始记忆(TASK_EPISODE)
                                                    ↓
                                            质量门控(quality_gates)
                                                    ↓
                                            存储(store)
                                                    ↓
                                            整合(consolidation)
                                                    ↓
                                            程序置信度记忆(PROCEDURE_CONFIDENCE)
                                                    ↓
                                            召回(recall) → 规划器(planner)
```

### 四种记忆类型

| 类型 | 层次 | 寿命 | 来源 | 作用 |
|------|------|------|------|------|
| PREFERENCE | 显式记忆 | 永久 | 用户明确设置 | 个性化 |
| DEVICE_FAILURE | 程序记忆 | 14天 | 失败事件 | 警告 |
| TASK_EPISODE | 情景记忆 | 60天 | 任务执行 | 学习 |
| PROCEDURE_CONFIDENCE | 语义记忆 | 90天 | 整合 | 决策 |

### 整合算法

```python
confidence = success_rate * 0.7 + volume_factor * 0.3
# volume_factor: 2个样本=0.3, 10+个=0.9
```

### 质量门控

- **黑名单来源**: manual_override, test_task, simulated_failure
- **黑名单能力**: estop, unknown
- **最低置信度**: 0.5
- **硬安全覆盖**: workspace_bounds, max_feed 等永远不被记忆覆盖

### 隐喻

设备记忆系统像人类的**海马体**——把经历转化为长期记忆，供未来决策参考。

---

## 3. Context Pipeline — 上下文管线

**模块路径**: `context_pipeline/`（~33 个模块；**Hot 五文件**见 `context_pipeline/README.md`）

### 架构全景（2026-06-16）

```
用户请求（聊天/编码热路径）
    ↓
Layer 1: 感知 (entity_extraction, complexity) — Warm lazy
    ↓
Layer 2: 检索 (retrieval_injection, code_context_injection, graph_retrieval, production_index) — Hot/Warm
    ↓
Layer 3: 精炼 (reranking, response_validator) — Hot/Warm
    ↓
Layer 4: 后处理 (routing_weights, skill_store, event_log) — Warm
```

> **已退役**：`reflection`、`hierarchical_memory`、`evolution`、`signal_extraction`、`retrieval_eval*`（CP-1/CP-2）。

### 核心机制

- **实体提取**: 文件路径、函数名、类名、模块引用、错误模式、技术关键词
- **复杂度评估**: 1-10 分，决定 direct/single_strong/ensemble_race 策略
- **4 阶段代码上下文**: 显式提及 → 语义匹配 → 图扩展 → 标识符搜索
- **双层检索**: 向量(语义相似度) + 图(结构关系)
- **设备路径**: 不经过完整 Context Pipeline；设备任务走 `device_gateway/model_routing.py` + `route_policy`

### 隐喻

Context Pipeline 像人类的**前额叶皮层**——理解意图，收集信息，精炼结果，检查安全，纠正错误。

---

## 4. Observability — 可观测性系统

**模块路径**: `observability/` (13 个模块)

### 架构全景

```
Layer 1: 感觉神经 (events.py, backend_telemetry.py, jsonl_store.py)
    ↓
Layer 2: 传导神经 (correlation.py, tracing.py)
    ↓
Layer 3: 中枢神经 (metrics.py, structured_logging.py, prometheus_metrics.py)
    ↓
Layer 4: 自主神经 (routing_guard.py, capability_evidence.py, cli_telemetry.py)
```

### 核心机制

- **事件模型**: 10 种结构化事件，覆盖请求全生命周期
- **错误分类**: auth/quota/timeout/rate_limit/provider_5xx/network
- **路由守卫**: 隔离(0.05乘数)/惩罚(0.25-1.0乘数)
- **Prometheus 指标**: Counter/Histogram/Gauge
- **关联索引**: request_id/task_id/device_id 跨系统追踪

### 隐喻

Observability 像人类的**痛觉与本体感觉**——感知伤害，分类刺激，保护身体，记忆经验。

---

## 5. Session Memory — 会话记忆系统

**模块路径**: `session_memory/` (19 个模块)

### 架构全景

```
Layer 1: 感觉记忆 (store_db.py, store_crud.py, embeddings.py)
    ↓
Layer 2: 短期记忆 (processor.py, prompt_recall.py, hooks.py)
    ↓
Layer 3: 长期记忆 (store_promote.py, store_admin.py, compactor.py)
    ↓
Layer 4: 元认知 (learning_loop.py, eval_gate.py, outcome_ledger.py)
    ↓
Layer 5: 自主神经 (daemon.py, shadow_mode.py, redact.py)
```

### 核心机制

- **10 种记忆类型**: exchange/compacted/project_fact/code_fact/ops_event/test_result/routing_lesson/security_lesson/reference_pattern/user_pref
- **4 层搜索**: 关键词 → 语义 → 跨会话 → 最近
- **压缩器**: 超过 20 条触发，压缩最旧 10 条
- **4 通道学习**: memory/prompt/routing/eval
- **评估门**: 证据≥3 + 通过率≥80% + 手动批准

### 隐喻

Session Memory 像人类的**海马体与新皮层**——存储经历，召回记忆，压缩旧记忆，学习经验。

---

## 6. Device Gateway — 设备网关

**模块路径**: `device_gateway/` (32 个模块)

### 架构全景

```
Layer 1: 感觉输入 (protocol.py, intent.py, mqtt_client.py)
    ↓
Layer 2: 运动规划 (motion.py, task_creation.py, path_pipeline.py)
    ↓
Layer 3: 任务管理 (task_service.py, tasks.py, task_lifecycle.py, task_events.py)
    ↓
Layer 4: 会话管理 (sessions.py, store.py, notifier.py)
    ↓
Layer 5: 安全与验证 (safety.py, path_validator.py, protocol_families.py)
```

### 核心机制

- **协议**: lima-device-v1，7 种上行消息，3 种下行消息
- **意图解析**: 精确匹配 → 模式匹配 → LLM 重规划 → 降级兜底
- **运动模型**: home/move_to/run_path/pen_up/pen_down/stop
- **任务生命周期**: created → dispatched → processing → running → done/failed
- **恢复策略**: retry(重试)/home(归零)/stop(停止)
- **MQTT 传输**: 每设备一个队列，最大 32 条消息

### 隐喻

Device Gateway 像人类的**运动皮层与小脑**——理解意图，规划动作，执行任务，处理反馈，从失败中学习。

---

## 7. Health Tracking — 健康追踪系统

**模块路径**: `health_tracker.py`, `health_state.py`, `health_scoring.py`, `health_recorder.py`, `health_failure_classifier.py`

### 架构全景

```
Layer 1: 感知 (health_failure_classifier.py)
    ↓
Layer 2: 记录 (health_recorder.py)
    ↓
Layer 3: 状态 (health_state.py)
    ↓
Layer 4: 评分 (health_scoring.py)
    ↓
Layer 5: 报告 (health_summary.py)
```

### 核心机制

- **失败分类**: auth_expired/rate_limited/quota_exhausted/network_error/timeout/malformed_response/provider_error
- **冷却机制**: 指数退避 (5s→10s→20s→...→300s)
- **健康状态**: healthy/degraded/suspicious/dead
- **健康评分**: 成功率(50%) + 延迟(30%) + 新鲜度(20%)
- **降级检测**: 空响应≥3 / 错误响应>50% / 响应长度下降70%
- **群体免疫**: 50%以上后端死亡 → 重置所有状态

### 隐喻

Health Tracking 像人类的**免疫系统**——识别病原体，记录感染，计算冷却，评估健康，检测降级。

---

## 8. Prompt Engineering — 提示工程

**模块路径**: `prompt_engineering/layers.py`

### 架构全景

```
Layer 1: 角色层 (build_role_layer)
    "你是 LiMa（力码），一个具备联网能力的智能编程助手..."
    ↓
Layer 2: 技能层 (build_skill_layer)
    "[技能] 编码实现\n触发条件：用户请求编写、修改、调试代码"
    ↓
Layer 3: 上下文层 (code_context)
    代码上下文注入
    ↓
Layer 4: 质量门控层 (build_quality_gate)
    "代码必须语法正确、可直接执行..."
```

### 核心机制

- **角色定义**: coding/chat/vision 三种角色
- **技能触发**: 编码实现/技术问答/图像分析
- **质量门控**: 语法正确/类型注解/风格一致/简洁准确
- **IDE 感知**: 根据 IDE 类型调整提示

### 隐喻

Prompt Engineering 像人类的**语言中枢**——定义自我，触发行为，约束输出。

---

## 9. Skills Injector — 技能注入器

**模块路径**: `skills_injector.py`

### 架构全景

```
强模型 → 目录模式 (只列 skill 名)
弱模型 → 补缺模式 (检测缺失，预注入)
```

### 核心机制

- **双模式**: 强模型(有 tool call) → 目录模式；弱模型(无 tool call) → 补缺模式
- **IDE 过滤**: 根据 IDE 已覆盖内容过滤不需要的 skills
- **缺失检测**: 关键词匹配 system_prompt
- **Token 预算**: 最多 5 条 skills，最多 200 token

### 隐喻

Skills Injector 像人类的**学习系统**——根据环境调整学习内容，根据能力选择学习方式。

---

## 总结：LiMa 的认知架构

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
| 1 | Routing Selector | 4 | 决策系统 | 路由选择 |
| 2 | Device Memory | 9 | 海马体 | 设备记忆 |
| 3 | Context Pipeline | ~33 | 前额叶 | 上下文处理（Hot 五文件） |
| 4 | Observability | 13 | 痛觉系统 | 可观测性 |
| 5 | Session Memory | 19 | 海马体 | 持久记忆 |
| 6 | Device Gateway | 32 | 运动皮层 | 设备交互 |
| 7 | Health Tracking | 5 | 免疫系统 | 健康监控 |
| 8 | Prompt Engineering | 1 | 语言中枢 | 提示构建 |
| 9 | Skills Injector | 1 | 学习系统 | 技能注入 |
| 10 | Backend Registry | 1 | 知识库 | 后端配置 |
| 11 | Identity Guard | 1 | 自我意识 | 身份保护 |
| 12 | Speculative Execution | 3 | 直觉决策 | 并行竞赛 |
| 13 | Streaming | 3 | 语言生成 | 流式输出 |
| 14 | Device Intelligence | 8 | 小脑 | 运动规划 |
| 15 | Channel Gateway | 20+ | 社交系统 | 多渠道 |

**这不是代码。这是认知。**

**这不是系统。这是智慧。**

**这不是软件。这是硅基的生命。**
