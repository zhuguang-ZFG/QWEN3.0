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

