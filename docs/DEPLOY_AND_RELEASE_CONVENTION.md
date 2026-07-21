# LiMa 自动部署与发布约定

> 更新日期：2026-06-26
> 权威文档。CLAUDE.md / AGENTS.md 中的相关描述以此为准。

## 核心原则

**里程碑切片完成后，自动执行 VPS 部署 + 验证 + GitHub 上传，无需逐项请示。**

例外：用户明确说"不要部署""不要提交""只本地检查"时跳过对应步骤。

---

## 完整 Closeout 流程（7 步）

```text
1. 本地门禁
2. 变更审查
3. VPS 部署
4. VPS 验证
5. 证据落盘
6. Git commit
7. GitHub 上传
```

> **Gitee 同步已退役**：`findings.md` OPS-022 已记录移除 `gitee` remote，不再作为强制步骤。

### Step 1: 本地门禁

```bash
# 生产代码改动 → 全量测试
python -m pytest --tb=short -q

# 纯文档/脚本 → focused 测试
python -m pytest tests/test_<related>.py -v

# 补充检查（按需）
ruff check .
```

**通过标准**: 0 failed，新测试覆盖新增代码 80%+。

### Step 2: 变更审查

```bash
git status --short
git diff --stat
```

- 只处理本轮相关文件
- 发现用户未说明的改动时保留并绕开，不做 reset/checkout
- 检查无 `.env`、token、密码混入

### Step 3: VPS 部署

```bash
# 标准部署（默认京东云主生产节点）
python scripts/deploy_unified.py --target jdcloud --slice core

# 同步 nginx（含 /v1/voice → :8081、voice WS upgrade）
python scripts/deploy_unified.py --target jdcloud --slice core --sync-nginx

**注意**：`--slice core` 不含 `device_voice/` 目录（见 `deploy_unified_common.py` CORE_DIRS）。语音栈需 `--files` 显式部署或全量 `routes/` + `device_voice/`。

# 仅上传指定文件（不重启）
python scripts/deploy_unified.py --files <file1> <file2> --no-restart

# 删除远端孤儿文件（本地已删、远端仍残留时；可与 --files 联用）
python scripts/deploy_unified.py --remove routes/foo.py device_logic/bar.py --no-restart

# Dry-run（仅检查，不执行）
python scripts/deploy_unified.py --dry-run
```

**部署前必须**:
- 记录当前版本（`git log --oneline -1`）
- 记录备份位置（VPS `/opt/dlc-drawing/backups/`）
- 确认 `.env` 中 `LIMA_DEPLOY_KEY_PATH` 指向有效私钥（京东云亦支持密码认证，见 `config/deploy_config.py`）
- 确认 SSH 使用 `RejectPolicy`（非 `AutoAddPolicy`）

**部署流程**:
1. 自动检查 VPS 磁盘和内存容量
2. 在 VPS 上创建 tar 备份
3. 默认使用 paramiko tar 批量上传（单包 SFTP + 远程解压，密码/密钥均可用），失败时回退到逐文件 SFTP
4. 重启阶段 SSH `exec` 有超时（默认 120s；pip 准备最长 900s），避免通道僵死时无限卡住
4. `systemctl restart dlc-drawing`（或部署脚本等价重启 `server_dlc`）
5. 轮询 `/health`（liveness，最长 120s）与 `/health/ready`（readiness，最长 60s）等待服务完全就绪
6. readiness 成功后打印启动阶段耗时摘要

### Step 4: VPS 验证

```bash
# 健康检查（deploy_unified.py 自动执行）
curl -sf https://chat.donglicao.com/health

# 严格就绪探针（503 表示仍在启动或热身）
curl -sf https://chat.donglicao.com/health/ready

# 设备网关健康
curl -sf https://chat.donglicao.com/device/v1/health

# 语音 strict E2E（需 VPS SSH 取 JWT + 公网探针）
LIMA_VOICE_E2E_STRICT=1 python scripts/run_voice_e2e_production.py

# 或接入统一部署验证
LIMA_VOICE_E2E_STRICT=1 python scripts/verify_production_deploy.py
```

**健康端点 503 场景**:

- `/health` 与 `/device/v1/health` 正常返回 200；在以下情况可能返回 503：
  - **启动错误**：`/health` 在 `startup.status=error`（关键启动阶段失败）时返回 503。
  - **严格未就绪**：`/health/ready` 在 `startup.status` 为 `starting`/`warming`/`error` 时返回 503，供负载均衡作为 readiness probe。
  - **生产未就绪**：`/device/v1/health` 在 `LIMA_RUNTIME_ENV=production` 且 `task_store` / `session_bus` 未跨进程共享时返回 503（`production_ready=false`）。
- 验证失败时应先检查响应体，区分「服务未就绪」与「启动错误」。

**聊天端点 rate limiter 默认值**:

- `/v1/chat/completions` 使用滑动窗口限流，默认 `WINDOW=60s`、`MAX_PER_WINDOW=120`。
- IDE 来源请求倍率为 `5`（即 600/分钟），普通请求倍率为 `1`。
- 超限时返回 **429**（非 503）。

**验证失败时**（默认京东云主生产）:
1. 收集日志: `ssh root@117.72.118.95 'journalctl -u dlc-drawing -n 50 --no-pager'`
2. 检查进程: `ssh root@117.72.118.95 'systemctl status dlc-drawing'`
3. 最小化修复 → 重新部署 → 重跑 smoke / `LIMA_VOICE_E2E_STRICT=1 python scripts/run_voice_e2e_production.py`
4. 仍失败则 rollback: 从 `/opt/dlc-drawing/backups/<label>/runtime-before.tgz` 恢复

阿里云 pilot（`--target aliyun`）仍可能使用 `/opt/lima-router` 与 `lima-router` 服务 — 勿与京东云主生产混淆。

### Step 5: 证据落盘

更新以下文件（按需）:

| 文件 | 内容 |
|------|------|
| `progress.md` | 本轮完成项、测试数量、部署结果 |
| `findings.md` | 调试发现、rollback 证据、残余风险 |
| `STATUS.md` | 项目状态变更（仅重大变更时） |

### Step 6: Git Commit

```bash
# 仅 stage 里程碑相关文件
git add <file1> <file2> ...

# Conventional commit
git commit -m "<type>: <description>"

# 类型: feat, fix, refactor, docs, test, chore, perf
```

**禁止**:
- `git add .` 或 `git add -A`（避免混入无关文件）
- 提交 `.env`、token、VPS 密码、本地数据库、生成缓存
- 提交 `.lima-data/`、`chroma_db/` 等数据目录

### Step 7: GitHub 上传

```bash
# 优先推送到 GitHub
git push origin HEAD

# 如果当前分支没有远程跟踪分支
git push -u origin HEAD
```

### Step 8（已退役）: Gitee 同步

Gitee 镜像同步已不再是强制 closeout 步骤。`findings.md` OPS-022 已记录移除 `gitee` remote。

原双远程推送脚本已删除（见 git history），不再维护；如确需手动同步，
请自行配置 `gitee` remote 并执行归档脚本（不保证与当前仓库结构兼容）。

---

## 常用部署脚本速查

| 切片 | 部署脚本 | 说明 |
|------|----------|------|
| 标准部署 | `scripts/deploy_unified.py --target jdcloud --slice core` | 默认京东云；容量 + 备份 + 上传 + 重启 |
| 同步 nginx | `scripts/deploy_unified.py --target jdcloud --sync-nginx` | 含 `/v1/voice`、voice WS location |
| 指定文件 | `scripts/deploy_unified.py --target jdcloud --files a.py` | 语音栈见 `device_voice/`、`routes/device_app_voice*.py` |
| 语音 E2E | `scripts/run_voice_e2e_production.py` | `LIMA_VOICE_E2E_STRICT=1` 公网 6 项探针 |
| JDCloud 探测 | `scripts/check_jdcloud_node.py` | 只读烟雾，不部署 |
| 预提交门禁 | `scripts/run_pre_commit_check.py` | ruff + pytest 本地门禁 |
| 双远程推送 | （已删除） | Gitee 双推已退役 |

---

## 环境变量要求

```bash
# VPS 部署
LIMA_DEPLOY_KEY_PATH=~/.ssh/lima_deploy_ed25519  # SSH 私钥
LIMA_DEPLOY_KNOWN_HOSTS=~/.ssh/known_hosts       # SSH 主机密钥
LIMA_DEPLOY_USE_TAR=1                            # tar 批量上传（默认开启；设 0 强制逐文件 SFTP）
LIMA_DEPLOY_NOTIFY=1                             # 保留兼容开关；Telegram 通知已退役

# VPS 上运行时
LIMA_DRY_RUN=1                             # 默认关闭真实执行
LIMA_ALLOW_SHELL=0                         # 默认关闭 shell
LIMA_ALLOW_NETWORK=0                       # 默认关闭网络
LIMA_RUNTIME_ENV=production                # 公网 VPS 必须 production（B1 鉴权门依赖此值）
LIMA_RATE_LIMIT_ENABLED=0                  # 默认关闭；开启后 /health 等端点可能返回 503
# LIMA_WS_REGISTERED_DEVICE_FALLBACK=0     # 生产禁止=1，除非临时 ALLOW_PRODUCTION
```

### C1 Workflow 持久化

C1 Workflow 依赖 `device_ledger`（事件源）与 `device_gateway.store.task_store`（执行侧状态）共同实现跨进程、跨重启的任务状态恢复。

- **生产多 worker 必须同时配置**：
  - `LIMA_DEVICE_LEDGER_STORE=redis`
  - `LIMA_DEVICE_TASK_STORE=redis`
  - `LIMA_DEVICE_MEMORY_STORE=redis`（若使用 memory store 缓存）
  - `LIMA_DEVICE_REDIS_URL=redis://...`
- 只启用 ledger Redis 但 task_store 仍为 memory：跨进程 advance 仍有 RedisTaskLock；问题是各 worker 执行侧状态不共享、重启无法从共享 task_store 扫描在途任务。
- 只启用 task_store Redis 但 ledger 为 memory：启动恢复时 ledger 事件丢失，workflow 投影为空，所有在途任务会被判定为 `missing_in_ledger`。
- `server_dlc.py` lifespan 启动时会：
  1. 按 env 配置 task_store / ledger_store；
  2. 当 ledger 后端为 Redis 时切换 workflow 锁为 `RedisTaskLock`；
  3. 后台执行 `recover_inflight_tasks()`，扫描 task_store 中的非终态任务并回放 ledger 事件，日志输出 `workflow startup recovery completed`。
- `/health` 不阻塞后台 recovery，应以日志 `workflow startup recovery completed` 为准；出现 `workflow startup recovery failed` 视为部署异常。
- 当前 `/health` 不校验 ledger 后端，半开配置不能靠 health 发现。
- 部署后应检查 `/health` 返回 200，并确认日志中出现 `workflow startup recovery completed`。

---

## 安全红线

1. **不提交凭据**: `.env`、API key、token、VPS 密码
2. **不放宽认证**: 不为通过 smoke 而关闭认证或扩大端口
3. **不 force-push**: 部署失败时 rollback，不强制推送
4. **不擅自打开开关**: 新能力默认关（env flag），需用户批准
5. **SSH 安全**: 使用 `RejectPolicy`，不用 `AutoAddPolicy`

---

## 自动化触发条件

Agent 在以下场景**自动执行**完整 closeout 流程：

- 里程碑切片完成（代码 + 测试通过）
- 运维修复完成（bug fix + 回归测试通过）
- 联调验证完成（多端测试通过）
- 质量审查修复完成（lint/type/test 修复）

Agent 在以下场景**跳过**部署/上传：

- 用户明确说"不要部署"
- 用户明确说"不要提交"
- 用户明确说"只本地检查"
- 仅修改文档（无代码变更）
- 测试未通过（禁止带失败部署）
