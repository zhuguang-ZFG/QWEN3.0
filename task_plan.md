# LiMa — 当前任务计划

> Updated: 2026-06-05 · 权威状态见 `STATUS.md` + `AGENTS.md`
> 优先级详见 `docs/NEXT_MILESTONES.md`（2026-06-01 起部分已过时）

## 待提交

| 文件 | 变更 | 说明 |
|------|------|------|
| AGENTS.md | 全面重写 (309→346行) | 架构文档 + 代码审查 10 项修复 |
| STATUS.md | 日期修正 + 里程碑补全 | 新增 M-OC0~M-OC6 |
| progress.md | 补全 M-OC4~M-OC6 条目 | routing fix + admin UI + AGENTS rewrite |
| findings.md | 补全 M-OC4~M-OC6 发现 | root cause + lessons learned |

## 活跃优先级（按 Superpowers 原则排序）

### P0: 代码质量 — 大文件渐进拆分

- 权威 backlog: `docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md`
- 目标: 超 300 行文件拆分（目标 ≤300 行/文件, ≤50 行/函数）
- 入口: `ruff check .` 识别大文件 → 按模块职责拆分

### P1: 编码后端 — eval refresh + 路由硬化

- Kimi/SCNet-large 经 Windows:8080 或 FRP:8088 重跑 eval
- `periodic_coding_eval.py`（`LIMA_PERIODIC_CODING_EVAL=0` 默认关）
- `health_tracker` + `probe_loop` terminal-state 冷却

### P2: LiMa Worker — Prompt Contract v0.1

- `/agent/tasks`、worker prompt、role prompt 统一 Context/Task/Constraints/Verify/Output
- Hooks + Skill Auto-Activation v0.1（依赖 Contract）

### P3: ESP32/Device Gateway — 真机

- PROD-003 真机烧录 + 结构化失败事件 + write/home 真机 smoke
- 需硬件，不阻塞其他线路

### 已永久暂停

支付、公共注册、商业 billing、微信真机/机器人

## 验证命令

```powershell
# 全量测试
.venv310\Scripts\python.exe -m pytest tests/ -q --tb=short

# Lint
ruff check .

# Smoke
curl -sf http://127.0.0.1:8080/health
curl -sf http://127.0.0.1:8080/v1/models | python -m json.tool
```

## 相关文档

| 文档 | 用途 |
|------|------|
| `AGENTS.md` | 项目架构总览（权威） |
| `STATUS.md` | 里程碑状态 + 部署状态 |
| `progress.md` | 执行日志 |
| `findings.md` | 发现与教训（证据数据） |
| `docs/NEXT_MILESTONES.md` | 优先级与路线图 |
| `docs/PERSONAL_CODING_ASSISTANT_PLAN.md` | 当前路线图 |
