# LiMa 产品定义

> 2026-06-01 · 基于代码实测和 13 个里程碑的执行教训

## 一、LiMa 是什么

**LiMa 是一个个人 AI 编程助手平台**，由两部分组成：

| 组件 | 角色 | 部署位置 |
|------|------|----------|
| **LiMa Server** | 多模型路由网关 + Agent 运行时 + 会话记忆 | VPS (47.112.162.80) |
| **LiMa Code CLI** | 终端交互式编码助手（TUI + headless） | 用户本机 |

用户通过 CLI（`lima-code`）或 IDE 插件（Claude Code / Cursor / VS Code）发起编程任务，LiMa Server 自动选择最优免费模型执行，记录上下文和历史，返回结果。

## 二、核心体验

```
用户说"帮我修这个 bug"
  → LiMa Code CLI 读取项目文件
  → LiMa Server 选择最优模型（184 个后端中自动选）
  → 模型返回代码修改
  → CLI 应用修改 + 运行测试
  → 结果反馈给用户
```

**一句话**：像有一个 AI 程序员在终端里帮你写代码，你不用管它用哪个模型。

## 三、目标用户

- **个人开发者**（owner 本人），不是团队/企业
- 主要场景：Python 后端开发（当前 repo 是 Python）
- 次要场景：通用编程任务

## 四、LiMa 不是什么

| 不是 | 说明 |
|------|------|
| 开放平台 | 没有商业化 API、没有多租户、没有计费 |
| 模型训练平台 | 不做 fine-tune、不做 RLHF |
| 托管服务 | 不是 Vercel/ Railway，不管部署用户代码 |
| MCP marketplace | 不是 MCP 工具商店 |
| IoT 平台 | ESP32/设备网关已退役 |

## 五、当前技术栈

### 保留（核心）

| 模块 | 文件 | 用途 |
|------|------|------|
| 路由引擎 | `router_v3.py` | 三层后端池选择（strong/medium/floor） |
| 后端注册 | `backends_registry.py` | 184 个后端定义 |
| 拓扑检测 | `runtime_topology.py` | 后端可用性（已简化为全通） |
| HTTP 调用 | `http_caller.py` | 统一 HTTP 客户端 |
| 代码编排 | `code_orchestrator.py` | 编程场景 fallback + 质量门控 |
| 上下文管线 | `context_pipeline/` | 代码索引+检索+注入 |
| Agent 运行时 | `agent_runtime/` | 任务队列+审批+执行+沙箱 |
| 会话记忆 | `session_memory/` | SQLite 持久化会话 |
| 工具转发 | `routes/tool_forward.py` | IDE tool_calls 代理 |
| 反向网关 | `reverse_gateway/` | 5 个 VPS sidecar 管理 |
| CLI | `deepcode-cli/` | LiMa Code CLI (fork) |

### 待退役（缝合怪残留）

| 模块 | 原因 | 优先级 |
|------|------|--------|
| `smart_router.py` | 与 `router_v3.py` 功能重叠（兼容层） | P0 |
| `routing_engine.py` | 与 `router_v3.py` 功能重叠（五层路由） | P0 |
| `routing_classifier.py` | 请求分类逻辑分散，可合并到 router_v3 | P1 |
| `route_scorer.py` | 评分逻辑可合并到 router_v3 | P1 |
| `backends.py` | facade 文件，功能已被 registry + constants 拆分 | P2 |
| `server.py` 中的 `BodySizeLimitMiddleware` | 功能单一，可独立 | P2 |

### 待决定

| 项目 | 选项 |
|------|------|
| LiMa Code CLI | A) 继续维护 deepcode-cli fork / B) 基于 MiMo-Reasonix 重写 / C) 自研 |
| ContextManager | A) 完成 SessionManager 集成 / B) 删除 orphan 代码 |

## 六、后端添加原则

**ModelScope 是反面教材**——key 到手就加，没有评估。以后加后端必须满足：

1. 至少有 3 次独立调用的成功记录
2. 模型在至少一个路由池中有明确角色（不是"加了再说"）
3. 有对应测试或 eval 数据
4. 更新 `docs/MODEL_CATALOG.md` 或同等文档

## 七、路由引擎统一计划

**目标**：只保留 `router_v3.py` 作为唯一路由引擎。

1. 审计 `smart_router.py` 和 `routing_engine.py` 的调用方
2. 将两者的独有逻辑（如果有）合并到 `router_v3.py`
3. 将 `routing_classifier.py` 的请求分类合并到 `router_v3.py`
4. 删除旧文件，更新所有 import
5. 全量测试

## 八、CLI 策略建议

当前 `deepcode-cli` fork 的问题是：
- 上游项目有自己的方向，LiMa 的修改可能和上游冲突
- fork 里已有 22 个 LiMa 特有 commit，维护成本在增长
- 没有 TUI 自定义能力（提示词、品牌、工作流都是上游的）

**建议**：短期继续维护 fork（成本低），中期评估 MiMo-Reasonix 作为基础重写的可行性（它有成熟的 loop/tools/TUI 架构，且已适配中文）。

## 九、不做的事（明确边界）

- 不加 IoT / 硬件相关功能
- 不加多语言 i18n（中文就够）
- 不加 MCP marketplace
- 不加付费/订阅/多租户
- 不加 Web 管理面板（Telegram bot 已覆盖移动场景）
- 不追求"更多后端"——184 个够了，重点转向质量和延迟
