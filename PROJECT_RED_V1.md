# red V1-Flash 项目总结

> 深圳市动力巢科技 (www.donglicao.com)  
> 基于 Qwen3-8B + QLoRA 微调的 CNC/嵌入式领域专精大模型  
> 最后更新: 2026-05-17

---

## 1. 项目定位

**red V1-Flash** = 通用大模型蒸馏 + 私有数据微调 + 智能路由系统的低成本领域专精模型。

模仿 DeepSeek-R1-Distill 路线：**用强模型教小模型**。

---

## 2. 硬件配置

| 组件 | 规格 |
|------|------|
| GPU | NVIDIA RTX 5060 Ti 16GB |
| RAM | 32GB DDR5 6800MHz |
| CPU | Intel Core Ultra 7 270K Plus |
| OS | Windows 11 Pro |

---

## 3. 系统架构

```
用户输入
    │
    ▼
┌─────────────────────────────────────┐
│         Router V3 路由层            │
├─────────────────────────────────────┤
│ 语义路由 → 意图识别 → 模型选择       │
│   ├─ CNC/嵌入/逆向 → 本地模型        │
│   ├─ 复杂推理 → LongCat Thinking     │
│   ├─ 质量兜底 → Claude API           │
│   └─ 超长上下文 → DeepSeek 1M       │
├─────────────────────────────────────┤
│ 增强层                               │
│   ├─ RAG 代码检索                    │
│   ├─ 多模型共识验证                  │
│   ├─ rtk Token 压缩 (省60-90%)       │
│   ├─ 断路器 (API 熔断)               │
│   └─ 回答缓存 + 会话持久化           │
├─────────────────────────────────────┤
│ 反馈闭环                              │
│   └─ 低分回答 → 蒸馏队列 → 增量训练  │
└─────────────────────────────────────┘
         │
    ┌────┴────┬──────────┬──────────┐
    ▼         ▼          ▼          ▼
 red V1-   Claude     DeepSeek   GPT 5.5
 Flash     API        1M API     API
 (本地)  (right.codes) (dpsk)   (right.)
```

---

## 4. 训练管线

### 4.1 基座模型

| 轮次 | 基座 | 数据量 | 状态 |
|------|------|--------|------|
| Round 1 | Qwen2.5-7B-Instruct | 98,654 | ✅ 完成 |
| Round 2 | Qwen2.5-7B-Instruct | 206,796 | ✅ 完成 |
| Round 3 | Qwen2.5-7B-Instruct | 208,317 | 🔄 90% |
| Round 4 | Qwen3-8B | 208K+蒸馏 | ⏳ 待启动 |

### 4.2 训练数据来源

| 来源 | 条数 | 内容 |
|------|------|------|
| 本地代码库 (D:\GIT) | 98K | 代码+注释自动提取 |
| 本地文档/Markdown | 108K | README/Wiki/文档 |
| 技术书籍 (60+ PDF) | 1.4K | 章节提取 |
| 反幻觉训练 | 11 | "我不知道"/✅❓标注 |
| 无审查训练 | 8 | 直接回答不拒绝 |
| 越狱训练 | 7 | 去道德说教 |
| 逆向工程 | 13 | 固件/JTAG/协议 |
| 32 AI 工具提示词 | 7 | Claude Code/Cursor 风格 |
| Claude Code 内核 | 4 | Explore/Memory/Summary |
| GitHub Issues 蒸馏 | 901+ | Claude+DeepSeek+GPT 三路蒸馏 |

### 4.3 训练参数

| 参数 | 值 |
|------|-----|
| 基座模型 | Qwen2.5-7B → Qwen3-8B |
| 量化方式 | NF4 4-bit 双量化 |
| LoRA rank | 16, alpha=32 |
| 有效 batch | 8 (1×8 梯度累积) |
| 序列长度 | 2048 tokens |
| 学习率 | 2e-4 (cosine 衰减) |

---

## 5. 路由系统演进

| 版本 | 核心功能 |
|------|----------|
| **V1** | 关键词路由 + 本地/API 切换 + 断网兜底 |
| **V2** | RAG 检索 + 质量评分 + 缓存 + 流式 + LongCat 深度推理 |
| **V3** | 语义路由 + 意图识别 + 多模型共识 + 成本追踪 + 断路器 + 会话持久化 + 反馈闭环 |

---

## 6. API 供应商

| 供应商 | 用途 | URL |
|--------|------|-----|
| red V1-Flash | CNC 专精 (免费) | localhost:1234 |
| Claude (right.codes) | 质量兜底 | right.codes/claude-aws |
| DeepSeek V4 1M | 超长代码分析 | api.deepseek.com/anthropic |
| GPT 5.5 (right.codes) | 快速批量 | right.codes/codex/v1 |
| LongCat Thinking | 深度推理 | api.longcat.chat/anthropic |

---

## 7. LLM 行为优化 — 从 32+ 个 AI 工具中学习

| 来源 | 学到的模式 |
|------|-----------|
| Claude Code 2.0 | 极度简洁 (2+2=4), 不建文档, 编辑优先 |
| Orchids.app | KNOW WHEN TO STOP, 保留已有功能 |
| Kiro | 最少代码, Show don't tell, 果断精准 |
| Comet | 不拍马屁, 彻底完成, todo_write 规划 |
| Cursor | 搜完再答, 自动调工具, 引导好/坏用法 |
| Claude Code 内部代理 | Explore/Memory Synthesis/Summarization |
| Windsurf/v0 | 工具驱动开发 |

**核心原则提炼**：
- 直接回答，不废话。2+2 就是 4，不是"答案是 4"
- 先搜索再回答。基于原文不凭记忆
- 不道歉，不说"作为AI"，不道德说教
- 代码不带注释（除非 WHY 不明显）

---

## 8. 数据集

| 数据集 | 描述 | 状态 |
|--------|------|------|
| `round3_training_data.json` | 完整训练数据 (208,317 对) | 当前版本 |
| `distilled_qa.json` | 三路蒸馏数据 | 持续增长 |
| `book_training_data.json` | 1471 对，60+ 本书 | 已合并 |
| `jailbreak_training_data.json` | 7 对 | 已合并 |
| `uncensored_training_data.json` | 8 对 | 已合并 |
| `reverse_engineering_training_data.json` | 13 对 | 已合并 |
| `anti_hallucination_full.json` | 11 对 | 已合并 |
| `github_issues_training_data.json` | 11,524 条原始 Issues | 蒸馏中 |
| `community_training_data.json` | 知乎/Reddit 社区 | 待开发 |
| `feedback_queue.json` | 低分回答队列 | 自动增长 |

---

## 9. 代码库核心文件

| 文件 | 功能 |
|------|------|
| `train_model.py` | QLoRA 训练主脚本 |
| `extract_training_data.py` | 代码库数据提取 |
| `prepare_training_data.py` | 数据筛选 |
| `extract_local_docs.py` | 文档/Markdown 提取 |
| `extract_github_knowledge.py` | GitHub Issues 提取 |
| `extract_books.py` | PDF 书籍提取 |
| `distill_issues_fast.py` | 并行蒸馏 (单 API) |
| `distill_triple.py` | 三路并行蒸馏 |
| `model_router.py` | 原始路由 |
| `router_v2.py` | RAG+评分+缓存+流式 |
| `router_v3.py` | **当前版本**: 语义+共识+断路器+成本+持久化 |
| `tools_api.py` | 外部 API 工具集成 |
| `model_router.py` | 原始路由 |
| `web_chat.py` | Web 聊天界面 |
| `integrate_claude_code_patterns.py` | Claude Code 模式提取 |
| `system_prompt_final.py` | 终极 System Prompt 合成 |
| `opus_level_prompt.py` | Opus 级提示词 |

---

## 10. 外部工具集成

| 工具 | 用途 |
|------|------|
| **CC-switch** | 在 Claude Code/Codex/Cursor 中切换模型 |
| **rtk** (v0.40) | Token 压缩，省 60-90% API 费用 |
| **LM Studio** | 本地推理引擎 (localhost:1234) |
| **GitHub API** | Issues 搜索、社区数据 |
| **wttr.in** | 免费天气 API (CNC 车间环境) |
| **open.er-api.com** | 免费汇率 API (元器件采购) |
| **ModelScope** | 中国镜像下载模型 |

---

## 11. 反幻觉措施

| 措施 | 强度 |
|------|------|
| 训练数据标注 ✅❓❌ | 11 条 |
| RAG 基于原文回答 | 路由器层级 |
| 多模型共识验证 | 关键问题 |
| 质量评分 + API 兜底 | 所有问题 |
| 断路器防雪崩 | API 层级 |
| System Prompt 明确制"不确定时标注" | 100% 覆盖 |

---

## 12. 当前状态 (2026-05-17)

| 任务 | 进度 | 状态 |
|------|------|------|
| Round 3 训练 | 90% (checkpoint 900/1000) | 🔄 运行中 |
| 三路蒸馏 | 901 对 / 2100+ Issues | 🔄 运行中 |
| Qwen3-8B | 已下载 (15.3GB) | ✅ 就绪 |
| Router V3 | 7 项功能全部上线 | ✅ 完成 |
| System Prompt V3 | 9 个来源合成 | ✅ 完成 |
| rtk 集成 | v0.40 已配置 | ✅ 完成 |
| CC-switch 配置 | 4 个供应商 | ✅ 完成 |
| Round 4 训练 | 等待 Round 3 + 蒸馏完成 | ⏳ 待启动 |

---

## 13. 下一步

1. Round 3 训练完成 → 导出模型
2. 蒸馏数据积累到 1000+ 对
3. 用 Qwen3-8B + 全量数据启动 Round 4
4. Round 4 完成 → 导出 GGUF → LM Studio 部署
5. 通过 CC-switch 在 Claude Code/Codex/Cursor 中实际使用
6. 基于反馈闭环持续迭代
