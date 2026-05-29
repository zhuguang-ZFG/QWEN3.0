# LiMa 项目开发规范

## Superpowers 原则

### 0. 禁止降级处理（全局硬规则）

**所有功能必须在正确配置下运行，不允许静默降级或跳过。**

- `.env` 必须设置 `LIMA_API_KEY` 和 `LIMA_API_KEYS`，否则服务启动时应报错而非降级
- 路由引擎收到 coding 请求时，必须执行代码上下文注入，不允许静默跳过
- 响应后处理必须执行语法+安全检查，不允许因为"可选模块未安装"而跳过
- agent 执行器必须在 `LIMA_DRY_RUN=0` 时真正执行，不允许返回"disabled in scaffold"
- Telegram 命令必须完整处理，不允许返回"Unknown command"后不给用户任何提示
- 任何 `except Exception: pass` 或 `except ImportError: pass` 在生产路径中都是**禁止的**——必须至少 `logger.warning` 并说明降级原因
- 如果关键依赖不可用（如 chromadb、tree-sitter），必须在启动时日志明确告警，而不是运行时静默降级

**违反此规则的代码不得合入主分支。**

### 0.1 演练以自家项目为重（全局硬规则）

**所有演练和测试必须以 LiMa 后端 + LiMa Code 前端为核心对象。**

- 演练场景必须覆盖：LiMa 路由端到端、LiMa Code agent 任务全生命周期、Telegram 开发者技能
- 不得用外部玩具项目代替自家项目的演练
- 发现的问题必须记录到 `findings.md` 并修复
- LiMa Code（`deepcode-cli` 子模块）的演练包括：CLI 启动、任务 claim、代码生成、结果提交

### 0.2 不准自动降级验证（全局硬规则）

**验证必须使用真实环境，不允许自动降级或跳过。**

- VPS 部署后必须在 VPS 上实际验证，不能只在本地测
- 公网 API 必须用真实 token 通过公网域名测试，不能只测 localhost
- LiMa Code 必须实际启动 TUI 并交互，不能只用 curl 模拟
- Telegram 命令必须通过真实 Telegram 消息测试，不能只调用函数
- 发现"不可达"时，必须诊断根因并修复，不允许标记为"跳过"或"待定"
- 如果某个验证步骤因环境限制无法执行，必须明确说明原因和替代方案

### 0.3 .env 部署保护（全局硬规则）

**部署 .env 文件时必须合并，不得覆盖。**

- `.env` 包含敏感凭据（API key、bot token、webhook secret），部署时必须先备份 VPS 原始 .env
- 使用 `cat >> .env` 追加新变量，不使用 `sftp.put` 覆盖
- 每次部署后立即验证关键服务（Telegram webhook、API key 认证）是否正常
- 如果发现服务异常，第一反应是检查 .env 是否被覆盖
- `.env` 文件必须在 `.gitignore` 中，不得提交到 git

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

## 生产力与产品化总约束

- 一切行为都必须服务于 LiMa、LiMa Code 和 ESP32/Device Gateway 的真实生产力、
  产品化落地和 LiMa 自身特色。
- 优先解决阻碍真实使用的基建、可靠性、可观测性、执行闭环、联调闭环和交付闭环
  问题；锦上添花让位于雪中送炭。
- 新功能必须回答“它如何让用户更快完成真实工作”；不能只为了炫技、堆概念、
  扩大架构或追逐参考项目而引入复杂度。
- ESP32/硬件能力的目标是真正可验证、可回滚、可观测的智能执行力；LiMa Code
  的目标是真正能规划、修改、测试、审查、交付的软件生产力。
- 每次规划和审查都要优先检查是否存在更基础的生产力短板：日志、任务状态、
  错误恢复、提示词/记忆/路由学习、验证工具、可视化和操作员反馈。

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
7. Agent commits with a concise conventional-style message and pushes the current branch to **GitHub (`origin`) and Gitee mirror (`gitee` or dual push URL)**.
8. Only after that push does the agent propose the next milestone plan.

## Agent 自动 Closeout 约定（全局）

> 完整流程见 [`docs/DEPLOY_AND_RELEASE_CONVENTION.md`](docs/DEPLOY_AND_RELEASE_CONVENTION.md)。

当 Owner 或 Agent 完成一个可部署里程碑切片，且用户未禁止自动发布时，Agent **默认执行**：

```text
1. 本地 pytest（生产代码改动 → 全量；纯文档 → focused）
2. VPS 部署 + restart + /health + 切片 smoke
3. 更新 progress.md / findings.md（含 VPS 证据）
4. git add（仅里程碑相关文件）
5. git commit（conventional commit）
6. git push origin HEAD → git push gitee HEAD
```

**硬规则：**

- 无 VPS smoke 证据不得声称「已部署」。
- 不提交 `.env`、token、VPS 密码、`.lima-data/`、生成缓存。
- 部署前备份；失败则记录 rollback 位置，不 force-push。
- 新能力默认关（env flag），VPS 上不得擅自打开未审查开关。
- 禁止 `git add .`，只 stage 里程碑相关文件。

## Operator 全局偏好（2026-05-26）

Owner 明确要求：**里程碑切片完成后 Agent 自动 VPS 部署 + 自动 git commit/push（GitHub + Gitee）**，无需再逐项请示。仍遵守：仅 stage 里程碑相关文件、不提交密钥、部署失败则记录 rollback。

## 自动部署、VPS 验证调试与 GitHub 上传（项目全局）

当任务属于可交付代码切片、运维修复、联调验证或质量审查修复时，Agent 默认把 closeout 做到“本地可证据化 + VPS 可验证 + GitHub 可追溯”。除非用户明确说“不要部署”“不要提交”“只本地检查”，否则按以下顺序执行：

1. 本地门禁：运行与改动匹配的 focused pytest；生产路径变化时补跑 `ruff check`、`pyright` 和必要的全量/分批 pytest。失败时先调试修复，不能带失败结果进入部署。
2. 变更审查：检查 `git status --short`，只处理本轮相关文件；发现用户未说明的改动时保留并绕开，不做 reset/checkout。
3. VPS 部署前置：确认部署脚本使用固定 host key/known_hosts 校验，不使用 `AutoAddPolicy()`；部署前记录当前版本、备份位置和可回滚命令。
4. VPS 自动部署：优先使用 `scripts/deploy_*.py` 或该切片文档指定脚本，一次性上传替换，不在生产 VPS 上边改边调。
5. VPS 验证调试：部署后执行 restart、`/health`、公开 HTTPS smoke 和切片专属 smoke；失败时先收集日志、端口、进程、服务状态和最近异常，再最小化修复并重跑 smoke。
6. 证据落盘：把本地门禁、VPS health/smoke、失败原因、修复动作、rollback 位置和残余风险写入 `progress.md` / `findings.md` / `STATUS.md` 中最合适的位置。
7. GitHub 上传：仅 `git add` 本轮相关文件，提交前做 secret/凭据风险检查；用简洁 conventional commit；优先 `git push origin HEAD` 上传 GitHub，再按需要推送 Gitee 镜像或使用双推脚本。
8. 完成汇报：只有在本地门禁、VPS smoke 和 GitHub push 都有本轮证据时，才能声称“已部署并上传 GitHub”；否则明确说明卡在哪一环。

硬性边界：

- 不提交 `.env`、token、VPS 密码、本地数据库、生成缓存、压缩包、参考仓库、临时抓包/调试输出。
- 不为通过 smoke 放宽认证、扩大公网端口、关闭 host key 校验、绕过硬件 allowlist，或默认打开未审查的云/消息/数据库/硬件能力。
- 部署失败时优先 rollback 或停在可诊断状态，不 force-push，不用宽泛 `git add .` 掩盖问题。
- 自动上传 GitHub 是 closeout 的一部分，但仍必须建立在“只包含相关改动、无凭据、验证证据完整”的前提上。

**常用脚本：**

| 切片 | 部署 | VPS smoke |
|------|------|-----------|
| CF admission | `deploy_cf_admission_overlay.py` | overlay + cf_smoke |
| TG-GH-1 / INF-B | `deploy_reliability_ops.py` | `smoke_telegram_outbound.py` |
| GitHub webhook | `deploy_telegram.sh` / 手动 | `smoke_github_webhook_public.py` |
| Gitee MCP | `deploy_gitee_mcp_slice.py` | `smoke_gitee_mcp_tools.py`（先 `provision_gitee_token_vps.py`） |
| LC-W-1e | `deploy_lcw1_e2e_slice.py` | `smoke_lcw1_lima_next_e2e.py`（worker 需本机 tsx） |
| LC-W-2 | `deploy_lcw2_slice.py` | `smoke_lcw2_hooks_e2e.py`（worker 需本机 `.lima-code/skill-rules.json`） |
| PROD-008 | `deploy_prod008_slice.py` | `smoke_prod008_learning_loop_e2e.py`（task→result→四通道 learning loop） |
| CF-EVAL-1 | `run_cf_eval1_slice.py --completion-only` | 可加 `--apply` 写入 SANDBOX overlay |
| TG-GH-2 | — | `smoke_tg_gh2_limacode_telegram_e2e.py`（`--send` 需 Telegram token） |
| SCNET-DSPRO | — | `diag_scnet_ds_pro.py`（只读 probe 30s/90s） |

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
