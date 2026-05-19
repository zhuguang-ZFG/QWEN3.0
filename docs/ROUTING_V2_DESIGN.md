# LiMa 路由 V2 设计方案：去本地模型化

## 背景

当前路由架构为两层：
- Layer 1: 正则 + 信号字典分类器 → 处理 ~80% 请求（<1ms）
- Layer 2: 本地 Qwen3-1.7B (R13) → 处理 ~20% 模糊请求（+3000ms）

**问题：**
1. 路由延迟 3s > 最快后端延迟 376ms（Groq），路由比推理还慢
2. 决策空间仅 11 个 intent，CNC/嵌入式领域边界清晰，规则完全可覆盖
3. R14 实验证明 1864 条数据不足以让模型内化后端能力（极简 prompt 仅 4/10）
4. GPU 显存占用 + frp 隧道 + 模型维护 = 高运维成本，低 ROI

## 目标

- 移除本地路由模型依赖，释放 GPU 显存
- 增强规则层覆盖率：80% → 95%+
- 剩余 5% 用默认 fallback chain 兜底（不再需要模型推理）
- 路由延迟：3000ms → <5ms（纯规则）

## 参考方案（GitHub 高星项目）

| 项目 | Stars | 路由方式 | 启发 |
|------|-------|----------|------|
| LiteLLM | 47.6k | Config-driven fallback + load balance | 后端注册表结构 |
| Portkey Gateway | 11.8k | Rule-based conditional routing | 条件路由配置化 |
| RouteLLM (LMSYS) | 4.9k | Binary strong/weak classifier | 简单阈值分流 |
| Helicone | 5.7k | Observability-driven | 延迟数据反哺路由 |

**核心启发：** 业界主流方案都不用重 ML 模型做路由。RouteLLM 仅用二分类（强/弱），
Portkey 用纯配置规则。我们的 11-intent 分类完全在规则可覆盖范围内。

## 设计方案

### 架构变更

```
Before:  Query → Regex(80%) → [miss] → Local Model(20%) → Backend
After:   Query → Regex+Signal(95%) → [miss] → Default Chain(5%) → Backend
```

### 增强规则层（80% → 95%）

**新增维度：**
1. **消息长度分类** — 短消息(<20字)默认 trivial，长消息(>500字)提升 complexity
2. **代码检测** — 包含代码块/缩进代码的请求直接走 code_generation
3. **上下文继承** — 多轮对话保持上一轮的 intent（避免跟进问题被重新分类）
4. **IDE 信号** — Cursor/VS Code 来源默认偏向 code_generation
5. **语言检测增强** — 英文技术术语密度高→code/architecture

**置信度阈值调整：**
- 现有规则 ≥0.80 → 直接路由（不变）
- 信号分类器 ≥0.70 → 直接路由（从 0.80 降低，因为不再有模型兜底）
- 低于 0.70 → 走 default fallback chain（不调用模型）

### Default Fallback Chain（兜底策略）

当规则层无法确定 intent 时，不再调用本地模型，而是：
1. 使用 `unknown` intent 的 fallback chain
2. 按延迟排序（latency-aware sorting 已有）
3. 依赖熔断器 + 质量重试保证可用性

### 投机调用保留

`predict_fast_backend()` 保持不变 — 它是纯正则，<1ms，与本地模型无关。

## 代码变更清单

| 文件 | 变更 | 影响 |
|------|------|------|
| `smart_router.py` | 删除 `_call_local_model()`，增强 `signal_classify()` | 核心路由逻辑 |
| `smart_router.py` | `analyze()` 函数中移除模型调用分支 | 路由入口 |
| `smart_router.py` | 新增长度/代码/上下文分类规则 | 规则层增强 |
| `local_router.py` | 标记为 deprecated（暂不删除） | 可选保留做实验 |

## 回退策略

如果规则层覆盖率不够：
- 短期：用 Groq (376ms) 做轻量分类（比本地模型快 8x）
- 中期：积累路由日志，反哺规则层
- 长期：数据够 5000+ 时再考虑训练新模型

## 验收标准

- [ ] 路由延迟 <5ms（纯规则路径）
- [ ] 覆盖率 ≥95%（通过历史日志回放验证）
- [ ] GPU 显存释放（不再加载 Qwen3-1.7B）
- [ ] 所有现有功能不受影响（熔断器、投机调用、视觉路由）
- [ ] 本地模型代码标记 deprecated 但不删除（保留回退能力）
