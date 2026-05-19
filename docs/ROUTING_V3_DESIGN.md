# 路由 V3 设计文档 — IDE 识别 + 双层架构 + 代码能力路由

> 基于 Cursor Auto Mode 深度分析 + 免费 AI API 生态调研 (2026-05-20)

## 一、核心改进方向

### 1.1 IDE 识别（通过 System Prompt 指纹）

不同 IDE/编码工具的 system prompt 有明显特征差异：

| IDE | 检测关键词 | prompt 长度 | 路由策略 |
|-----|-----------|-------------|----------|
| Cursor | `"intelligent programmer"` | ~642 tokens | 代码模型优先 |
| Claude Code | `"CLAUDE.md"`, `"EnterPlanMode"` | ~8000 tokens | 强推理模型 |
| Aider | `"SEARCH/REPLACE"`, `"RepoMap"` | ~2000 tokens | 代码模型 |
| Cline | `"<environment_details>"` | ~3000 tokens | 代码模型 |
| Continue | `"Continue is an open-source"` | ~1500 tokens | 通用模型 |
| 普通 Chat | 无 system 或短 system | <100 tokens | 通用模型 |

**实现方式：** 在请求处理入口检测 messages[0] 的 role 和 content。

### 1.2 双层路由架构（借鉴 Cursor）

Cursor 的核心架构：
- **Core Model**（强模型）：负责推理、规划、架构设计
- **Apply Model**（快速模型）：负责执行文件操作、格式化

LiMa Router 对应实现：

```
请求入口
  ├─ IDE 识别 (system prompt 指纹)
  ├─ 意图分类 (regex + signal scoring)
  ├─ 复杂度判断 (token 数 + 文件数 + 关键词)
  │
  ├─ 推理层 (复杂任务)
  │   → DeepSeek-V4-Pro / Kimi-K2.5 / Claude
  │   信号: 长上下文>4000tok, 多文件, "refactor"/"design"/"explain"
  │
  └─ 执行层 (简单任务)
      → Groq (376ms) / Cerebras / NagaAI
      信号: 短请求, "complete"/"format"/"fix typo"
```

### 1.3 代码能力路由

检测请求中的代码特征，优先路由到代码专用模型：

| 信号 | 检测方式 | 路由目标 |
|------|----------|----------|
| 文件扩展名 `.py`/`.ts`/`.rs`/`.go` | 正则匹配 messages 内容 | codestral / DeepSeek Coder |
| 代码关键词 `function`/`class`/`import` | 词频统计 | 代码模型 |
| IDE 来源 Cursor/Claude Code | system prompt 指纹 | 代码模型优先 |
| 含 diff/patch 格式 | `@@`/`+++`/`---` 检测 | 强推理模型 |

## 二、新供应商集成计划

### 2.1 优先级排序

| 优先级 | 供应商 | 端点 | 免费额度 | 特点 |
|--------|--------|------|----------|------|
| P0 | NVIDIA NIM | nim.nvidia.com/v1 | 40 RPM 无日限 | Nemotron 120B 高质量 |
| P1 | Together AI | api.together.xyz/v1 | $25 额度 | 200+ 开源模型 |
| P2 | Cohere | api.cohere.com/v2 | 1000次/月 | Command R+ |
| P3 | OVHcloud | oai.endpoints.kepler.ai.cloud.ovh.net/v1 | 无限 | 2 RPM 太低 |

### 2.2 已集成的社区免费服务

| 服务 | 状态 | 限制 | 用途 |
|------|------|------|------|
| NagaAI | ✅ 运行中 | 无明确限制 | gpt-4.1-mini, llama-70b, llama-4 |
| FreeTheAI | ✅ 运行中 | 10 RPM, 每日签到 | DeepSeek-V4, Kimi-K2.5, swe-1.6 |
| pekpik | ⚠️ daemon 监控 | key 24h 过期 | 共享 key 池 |

### 2.3 评估后放弃的服务

| 服务 | 原因 |
|------|------|
| Featherless | 太慢 (15-35s)，容量经常满 |
| zukijourney | 只有 Mistral 系列，已有官方 |
| AgentRouter | key 无效，"unauthorized client" |

## 三、实现路线图

### Phase 1: IDE 识别 (当前)
- 在 smart_router.py 请求入口加 `detect_ide()` 函数
- 检测 system prompt 特征关键词
- 标记 `request.ide_source` 字段
- 日志记录 IDE 分布统计

### Phase 2: 代码路由增强
- 加入文件扩展名检测信号
- 代码请求优先路由到 codestral / DeepSeek Coder
- IDE 来源作为路由权重因子

### Phase 3: 双层架构
- 实现复杂度评分 (token 数 + 文件数 + 关键词)
- 推理层/执行层分流
- 监控两层的延迟和质量差异

### Phase 4: 新供应商
- 集成 NVIDIA NIM (P0)
- 集成 Together AI (P1)
- 集成 Cohere (P2)

### Phase 5: 动态排名 + 消除死模型
- 同层轮转替代固定优先级
- 实时 score 计算 (成功率 × 0.4 + 速度 × 0.3 + 质量 × 0.3)
- 健康检查 + 金丝雀流量

## 五、动态排名机制（消除"死模型"问题）

### 5.1 问题描述

当前 fallback 链是严格优先级：
```
Groq → Cerebras → GitHub → ... → NagaAI → FreeTheAI → Pollinations
```

如果顶部模型永远稳定，底部模型永远不会被调用。导致：
- 不知道后备模型是否还活着
- 无法积累质量数据
- 免费额度浪费
- 真正需要时可能已经挂了

### 5.2 解决方案：同层轮转 + 动态评分

#### 层级定义（同层内轮转，不固定顺序）

```
T0 超快层 (目标 <500ms):  Groq, Cerebras
T1 快速层 (目标 <2s):     GitHub, Cloudflare, Mistral, NagaAI
T2 标准层 (目标 <5s):     DeepSeek, Zhipu, Aliyun, LongCat, Volcengine
T3 慢速层 (目标 <15s):    FreeTheAI, OpenRouter, Google
T4 兜底层 (无限制):       Pollinations, LLM7, Chat.ubi
```

同层内随机选择（加权随机，权重 = score），而不是固定顺序。

#### 动态评分公式

```python
score = success_rate * 0.4 + speed_score * 0.3 + quality_score * 0.3

# success_rate: 最近 100 次请求的成功率 (0-1)
# speed_score: 1 / (avg_latency_ms / tier_target_ms), capped at 1
# quality_score: 基于简单启发式 (0-1):
#   - 响应非空: +0.3
#   - 含代码块: +0.3 (如果是代码请求)
#   - 长度合理 (>50 chars): +0.2
#   - 无错误标志 ("sorry", "I cannot"): +0.2
```

#### 冷启动 + 探索

- 新加入的后端初始 score = 0.5（中间值）
- 每 50 个请求强制 1 个发到最低 score 后端（探索）
- score 使用指数滑动平均，最近的请求权重更大

### 5.3 健康检查（后台，不影响用户）

```
每 5 分钟:
  对所有后端发 ping 请求 ("hi", max_tokens=1)
  更新 is_alive 状态
  连续 3 次失败 → 标记为 dead，从路由池移除
  恢复后自动重新加入（score = 0.3 低权重起步）
```

### 5.4 指标记录

每个请求记录：
- backend_name
- latency_ms
- success (bool)
- quality_score
- ide_source (如果检测到)
- intent (路由分类结果)

存储在 `/opt/lima-router/metrics.jsonl`，滑动窗口保留最近 10000 条。

### 5.5 预期效果

| 指标 | 当前 | 改进后 |
|------|------|--------|
| 后端利用率 | ~30% (多数从不被调用) | ~90% (同层轮转) |
| 故障发现时间 | 不确定（可能永远不知道） | <5 分钟（健康检查） |
| 路由准确性 | 固定规则 | 数据驱动，自动优化 |
| 模型质量对比 | 无数据 | 有实时对比数据 |

## 四、Skills 注入机制（减少幻觉 + 增强代码能力）

### 4.1 核心思路

当检测到用户在进行编程工作（IDE 来源 或 代码特征），在转发请求前动态注入
编程 skills 到 system prompt 中。这相当于给模型加了"专业知识库"：

```
用户请求 → IDE/语言检测 → 选择 skills 集 → 注入 system prompt → 转发模型
```

### 4.2 Skills 分层

| 层级 | 触发条件 | 注入内容 |
|------|----------|----------|
| L0 通用编程 | 任何 IDE 来源 | 错误处理、安全编码、类型安全 |
| L1 语言专用 | 检测到 .py/.ts/.go 等 | 语言最佳实践、惯用写法 |
| L2 框架专用 | 检测到 React/Django 等 | 框架约定、组件模式 |
| L3 项目专用 | 检测到 CLAUDE.md/cursorrules | 项目自定义规则 |

### 4.3 通用编程 Skills (L0)

检测到编程场景时始终注入：

```
- 优先写安全代码：参数化查询、输入验证、正确的错误处理
- 不要吞掉异常，不要用空 catch
- 函数保持单一职责，不超过 50 行
- 变量命名要有语义，不用 a/b/tmp
- 不要生成占位符代码（TODO/FIXME），要写完整实现
- 不要编造不存在的 API/库/函数（减少幻觉的关键）
- 如果不确定某个 API 是否存在，明确说明而不是猜测
```

### 4.4 语言专用 Skills (L1)

| 语言 | Skills 要点 |
|------|-------------|
| Python | type hints, f-string, pathlib, dataclass, 不用 bare except |
| TypeScript | strict mode, const 优先, async/await, 不用 any |
| Go | error wrapping, defer, context propagation, 不用 panic |
| Rust | ownership, Result<T,E>, 不用 unwrap in production |

### 4.5 IDE 感知 Skills (L3)

| IDE | 额外注入 |
|-----|----------|
| Cursor | "输出代码时使用 edit markers 格式" |
| Claude Code | "可以使用工具调用，优先 Read/Edit/Bash" |
| Aider | "使用 SEARCH/REPLACE 格式输出修改" |
| Cline | "使用 XML 工具调用格式" |

### 4.6 实现方式

在 smart_router.py 的请求处理中：

```python
def inject_skills(messages, ide_source, language):
    """检测到编程场景时注入 skills"""
    skills = []
    
    # L0: 通用编程 skills
    if ide_source or language:
        skills.append(CODING_SKILLS_L0)
    
    # L1: 语言专用
    if language in LANGUAGE_SKILLS:
        skills.append(LANGUAGE_SKILLS[language])
    
    # 注入方式：追加到 system prompt 末尾
    if skills and messages and messages[0].get("role") == "system":
        messages[0]["content"] += "\n\n" + "\n".join(skills)
    elif skills:
        messages.insert(0, {"role": "system", "content": "\n".join(skills)})
    
    return messages
```

### 4.7 关键原则

1. **不要过度注入** — skills 总长度控制在 200 tokens 以内，不占用用户上下文
2. **减少幻觉的核心** — 明确告诉模型"不要编造不存在的 API"
3. **IDE 格式适配** — 不同 IDE 期望不同的输出格式，注入对应格式指令
4. **可配置** — skills 存储在独立文件中，方便更新不需要改代码

