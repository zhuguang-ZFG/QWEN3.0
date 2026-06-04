> ⚠️ 2026-06-01 起已过时。ESP32/FRP/WeChat 已移除。当前状态见 STATUS.md

# LiMa AI 技术架构

> 深圳市动力巢科技有限公司
> 版本: 3.0 | 更新: 2026-05-20

> **⚠ 阅读说明（2026-05-26）**  
> 下文「系统架构图」「商业模式」等章节为 **2026-05-20 商业开放平台** 草案，与当前 **私人编码助手** 方向部分不一致。  
> **当前权威架构** 见：`docs/REQUEST_PIPELINE_AUTHORITY.md`、`routing_engine.py`、`server.py`（薄入口）、`docs/LIMA_MEMORY.md`（2026-05-26 consolidated state）。

---

## 当前架构（2026-05-26 · 私人编码助手）

### 定位

- **产品：** 个人编码助手后端（非开放注册 SaaS）。
- **主入口：** `https://chat.donglicao.com`（访客网页 + IDE `/v1`）。
- **微信：** 产品已退役；`/channel` HTTP 契约保留，`WECHAT_BRIDGE_ENABLED=0`。

### 请求管线（生产）

```text
Client → server.py (BodySizeLimitMiddleware, access_guard)
      → routes/chat_endpoints | anthropic_messages_handler
      → chat_preflight (guardrails, budget, identity)
      → routing_engine.route()  ← 权威选路与执行
      → http_caller → 后端池 (httpx)
      → route_post_process + identity_guard
      → chat_post_closeout (memory, metrics, distill queue)
```

模块归属矩阵：**`docs/REQUEST_PIPELINE_AUTHORITY.md`**

### 路由与后端

| 组件 | 文件 | 说明 |
|------|------|------|
| 五层路由 | `routing_engine.py` | 分类、池选、执行、fallback |
| P2C / sticky | `router_v3.py`, `sticky_session.py` | 负载与亲和 |
| 健康 | `health_tracker.py` | 退避 + 质量追踪 |
| 后端注册 | `backends_registry.py` | 170+ 后端；`backends.py` 为兼容 facade |
| 语义缓存 | `semantic_cache.py` | temperature=0 |
| Skills | `skills_injector.py` | 弱模型补缺 |

### 并行子系统（非 chat 热路径）

| 子系统 | 路径 | 说明 |
|--------|------|------|
| Device Gateway | `device_gateway/` | `/device/v1/*`；Redis 任务队列 + WSS；公开 `chat.donglicao.com/device/v1/*` |
| Channel Gateway | `channel_gateway/`, `routes/channel_gateway.py` | 斜杠命令、G3 会话、公开 API 工具 |
| Agent tasks | `routes/agent_tasks.py`, `agent_runtime/` | LiMa Code 任务契约 |
| Session memory | `session_memory/` | 持久记忆 + learning loop（PROD-008） |
| LiMa Code | `deepcode-cli/` submodule `8e680ea` | 本地 worker `/lima task` |
| ESP32 产品 | `esp32S_XYZ/` submodule `160e526` | 固件 + fake-U8；真机 flash pending |

### 部署拓扑（简图）

```text
                    Internet
                        │
          ┌─────────────┴─────────────┐
          │  VPS 47.112.162.80        │
          │  nginx → lima-router :8080 │
          │  Redis (device tasks)      │
          └─────────────┬─────────────┘
                        │ FRP :8088
          ┌─────────────┴─────────────┐
          │  Windows 本机              │
          │  :8080 本地代理 + 免费后端   │
          │  (SCNet/Kimi/LongCat 等)    │
          └───────────────────────────┘
```

### 安全基线（2026-05-26）

- `BodySizeLimitMiddleware`：超大 body / chunked 超限 → 413。
- `/api/live-key`：仅返回元数据，**不**下发 `GOOGLE_AI_KEY`。
- Admin 登录：`constant_time_equals`。
- `deploy/key_rotation.py`：退役；legacy 在 `scripts/archive/`。

---

## 核心技术栈（历史文档 · 2026-05-20）

### 智能路由引擎 (Smart Router)

LiMa 的核心竞争力不是单一模型，而是**智能路由系统**——根据用户意图自动选择最优 AI 后端。

| 层级 | 技术 | 延迟 | 作用 |
|------|------|------|------|
| Layer 1 | 请求分类器 (路径+UA+元数据) | <1ms | 区分 IDE/Chat/Vision/Image |
| Layer 2 | 后端池选择 (健康感知+同层随机) | <1ms | 从对应池选健康后端 |
| Layer 3 | 执行器 (Skills注入+模型专属prompt) | 0ms | 增强弱模型输出质量 |

**V3 架构特点：**
- 三层分离（分类/选择/执行）
- 后端池分层（strong/medium/floor）
- 被动追踪 + 主动探活双轨健康检查
- TTL cache 冷却期（5s，参考 LiteLLM）
- 永不"不可用"三级保底

### 性能均衡策略

```
用户请求 → 请求分类(<1ms) → 后端池选择(健康感知) → Skills注入 → 调用 → 响应
              ↓                    ↓                    ↓          ↓
         IDE/Chat/Vision     同层随机+延迟路由     语言专属规范   失败重试(max 5)
```

**三维均衡：速度 × 质量 × 成本**

1. **速度优先**：80% 简单请求走免费通道，响应 <1s
2. **质量保障**：复杂请求自动升级到 Claude/GPT-4 级别后端
3. **成本控制**：智能路由使 API 调用成本降低 10 倍

### 74 个 AI 后端 / 21 供应商

| 类别 | 后端数 | 代表 | 用途 |
|------|--------|------|------|
| 国内直连 | 11 | 智谱、阿里、百度、火山 | 日常对话、编程 |
| 国际直连 | 52 | Groq、GitHub、NVIDIA、OpenRouter | 高质量推理 |
| 需代理 | 11 | Google、Mistral、Cloudflare | 视觉、长文本 |

---

## 模型能力提升路径

### 持续训练体系 (Round-based SFT)

| 轮次 | 数据量 | 重点 | 成果 |
|------|--------|------|------|
| R1-R8 | 500条 | 基础能力 | 路由准确率 75% |
| R9-R12 | 2000条 | 身份+嵌入式 | 准确率 88% |
| R13 | 6867条 | 公司身份+ESP32 | Loss 0.42, Acc 90.1% |
| R14 | 8000条 | 上下文工程+工具架构 | Loss 0.48, Acc 91.4% |
| R15 | 2082条 | 防遗忘+防幻觉 | 计划中 |

### 防遗忘训练策略

- **30% 旧轮回放**：每轮训练混入历史数据，防止灾难性遗忘
- **负样本注入**：8 条防幻觉样本教模型说"我不确定"
- **渐进学习率**：从 2e-5 逐步降至 5e-6，保护已学知识

### 质量保障机制

| 机制 | 作用 |
|------|------|
| 置信度检测 | 低置信度自动升级到更强模型 |
| 不确定性标记 [ERR] | 检测到幻觉风险时拒绝回答 |
| Fallback 重试 | 质量不达标时切换后端重试 |
| 蒸馏日志 | 记录高质量回答用于下轮训练 |

---

## 平台架构

```
┌─────────────────────────────────────────────────┐
│  用户终端 (Cursor / VS Code / Chat / API)        │
└──────────────────────┬──────────────────────────┘
                       │ HTTPS
┌──────────────────────▼──────────────────────────┐
│  Nginx 反代 (SSL + 品牌注入 + 负载均衡)          │
└──────────────────────┬──────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│ new-api      │ │ NextChat │ │ 官网 (Next.js)│
│ API 网关     │ │ 免费聊天 │ │ 品牌展示     │
│ port 3003    │ │ port 3002│ │ 静态部署     │
└──────┬───────┘ └────┬─────┘ └──────────────┘
       │              │
       ▼              ▼
┌─────────────────────────────────────────────────┐
│  Smart Router (FastAPI, port 8080)               │
│  ┌──────────────┐ ┌──────────┐ ┌─────────────┐ │
│  │规则+信号分类 │→│后端选择  │→│质量检查+蒸馏│ │
│  │(0ms)         │ │(74后端)  │ │             │ │
│  └──────────────┘ └──────────┘ └─────────────┘ │
└──────────────────────┬──────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│ one-api      │ │ DeepSeek │ │ Claude/GPT-4 │
│ (负载均衡)   │ │ (免费)   │ │ (付费, 强)   │
└──────────────┘ └──────────┘ └──────────────┘
```

---

## 硬件设备集成

LiMa AI 可无缝接入动力巢智能硬件产品线：

| 设备 | 集成方式 | AI 能力 |
|------|----------|---------|
| 派曦写字机 | GRBL G-code 生成 | AI 自动排版+字体生成 |
| 绘图机 | SVG→G-code 转换 | AI 图像描述→矢量绘制 |
| 激光雕刻机 | 功率/速度优化 | AI 材料识别+参数推荐 |
| ESP32 控制器 | 固件 OTA + API | AI 远程诊断+自动调参 |

---

## 可组合 Prompt 工程

借鉴 Claude Code 架构，LiMa 采用**片段化 Prompt 组装**：

```python
fragments/
├── identity.md      # 身份声明（静态，可缓存）
├── capabilities.md  # 能力描述
├── constraints.md   # 约束规则
└── safety.md        # 安全边界

# 运行时按需组装，支持 A/B 测试和功能开关
SYS = assemble_prompt(features={'identity', 'capabilities', 'constraints'})
```

**缓存优化**：系统提示词完全静态，动态数据注入消息层，缓存命中率 80%+。
