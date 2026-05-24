# LiMa 项目开发规范

## Superpowers 原则

### 1. 文档先行

- 任何非 trivial 改动，先写设计文档再编码。
- 文档是设计决策的永久记录，代码会变，但决策原因不该丢失。
- 参考开源项目时记录具体借鉴了什么，以及为什么。

### 2. 文件小而专注

- 单文件目标不超过 300 行。
- 每个文件只做一件事：路由、健康检查、会话管理分别独立。
- 函数目标不超过 50 行，超过就拆。
- 不利于维护的大文件必须逐步拆分。

### 3. 本地验证再部署

- 本地实现并测试通过后，一次性替换服务器文件。
- 不在生产服务器上边改边调。
- 部署前备份，部署后验证。

### 4. 永不破坏生产

- 服务器改动必须可回滚。
- 新模块优先独立文件，确认无误后再接入核心路径。
- 端口冲突、进程残留和长连接卡住重启等问题要在部署流程中处理。

### 5. 参考业界最佳实践

- 设计决策应尽量有开源参考或实测数据佐证。
- clone 参考项目时要分析源码并提取核心实现，不盲目照搬。
- 不重复造轮子；成熟库优先于自研基础设施。

### 6. 渐进式替换

- 新旧系统可以并行运行，逐步切流。
- 保留旧代码直到新代码完全验证。
- 重要路径先小流量或手工 smoke，再全量使用。

## 当前方向

LiMa 当前不是商业化开放平台，而是个人编码助手后端。

优先级：

1. 编码体验和 IDE/Agent 接入。
2. 后端质量评测和证据驱动路由。
3. VPS 简化运维和可回滚部署。
4. 请求内上下文预检和工具路径速度。

暂停：

- 支付。
- 公共注册。
- 商业 quota/usage/billing。
- 客户侧商业 dashboard。

## VPS 主动验证授权

- 用户允许 Agent 在有助于代码验证、条线联调、多端联调或生产路径
  smoke 时，主动部署到 LiMa VPS。
- 核心目标是尽快让 LiMa、LiMa Code 和 ESP32/Device Gateway 形成实际生产力；
  优先交付可运行、可验证、可回滚的切片，而不是长期停留在方案讨论。
- VPS 验证可以覆盖 LiMa Server、LiMa Code worker、公开 HTTPS 路由、FRP/本地
  代理路径、Redis/Postgres/WebSocket 会话路由、Device Gateway HA、ESP32 fake
  或真机 smoke。
- 涉及生产行为时仍必须保留安全边界：部署前备份，改动范围收敛，重启后跑
  health/smoke，记录回滚位置、验证结果和残余风险。
- 不为通过 smoke 而泄露密钥、放宽认证、扩大公网端口、绕过硬件 allowlist，
  或把未审查的云/数据库/消息/硬件能力默认打开。

## 当前关键文档

| 文档 | 内容 |
|---|---|
| `STATUS.md` | 当前项目状态总览。 |
| `docs/LIMA_MEMORY.md` | 详细长期记忆。 |
| `docs/PERSONAL_CODING_ASSISTANT_PLAN.md` | 当前主线计划。 |
| `docs/FREE_MODEL_ROUTING_STATUS.md` | SCNet/Kimi 免费模型使用状态。 |
| `task_plan.md` | 当前任务计划和证据。 |
| `findings.md` | 事实发现和运维结论。 |
| `progress.md` | 执行进展日志。 |

## 开发流程

```text
1. 更新或创建设计/计划文档
2. 本地编码
3. 本地测试
4. 必要时主动部署到 VPS 做代码验证或多端联调
5. VPS 编译 + restart + health
6. 公开接口 smoke
7. 更新 STATUS / memory / progress
8. Git commit / push
```

## Git 注意事项

- 不要 stage `.claude/`、本地参考仓库、临时调试脚本、压缩包或凭据文件。
- 不要提交真实密钥、VPS 密码、API token。
- 提交前运行测试和 secret 扫描。
- 工作区可能有用户改动；不要随意 reset 或 checkout。

## Milestone Collaboration Protocol

This project uses a two-role milestone loop:

1. Owner writes the implementation for the next milestone slice.
2. Agent reviews the submitted summary and code before any next milestone starts.
3. Agent fixes review findings when they are small and clearly scoped.
4. Agent runs focused tests, compile checks, ASCII/secret-safety scans where relevant, `git diff --check`, and the full test suite when production code changed.
5. Agent updates `progress.md` and `findings.md` with the closeout, including test evidence and any residual risks.
6. Agent stages only milestone-related files, never unrelated local data or reference repositories.
7. Agent commits with a concise conventional-style message and pushes the current branch to GitHub.
8. Only after that push does the agent propose the next milestone plan.

Hard rules for this loop:

- Do not skip the review-closeout step, even if the owner reports tests passed.
- Do not auto-stage broad directories when the worktree contains unrelated untracked files.
- Do not upload local databases, fixtures, credentials, reference repos, generated caches, or scratch scripts unless explicitly requested.
- New network, cloud, provider, shell, deployment, or hardware behavior must be default-off unless explicitly approved.
- Generated plans and patch plans are review artifacts; they must not auto-edit production routing or deployment files.
- No completion claim without fresh verification evidence from this session.
- If a focused test is expanded during review, report the new count and the full-suite count in the closeout.

Default handoff shape:

```text
User: implements milestone and posts summary.
Agent: review -> fix -> focused tests -> full tests -> docs/findings -> commit -> push -> next plan.
```
