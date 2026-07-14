# Root Package Spec — DLC 绘图服务（Python 服务主包）

> 本目录是根目录 Python 服务的编码规范，供所有 AI agent 在写代码前阅读。
> 权威细则仍以 `AGENTS.md` / `docs/AGENTS_REFERENCE_CN.md` 为准；本 spec 是跨平台、可版本化的蒸馏层，冲突时以 docs 为准并回写本 spec。

项目：DLC 绘图服务（Python 3.10 + FastAPI，:8081），为 ESP32 绘图机/写字机提供云端路径生成、任务下发与设备管理，经 MCP 接入小智云，经 `/device/v1/app/*` 服务微信小程序。

公网入口：`https://chat.donglicao.com/dlc/*`（nginx → `server_dlc` :8081）。

## 规范文件

| 文件 | 内容 |
|------|------|
| [architecture.md](architecture.md) | 请求链路、模块归属、退役模块、仓库结构 |
| [coding-conventions.md](coding-conventions.md) | Ponytail 第一、大小约束、类型注解、特性开关、文档语言 |
| [error-handling.md](error-handling.md) | 无静默降级、本地异常惯用法、日志模式 |
| [quality-gates.md](quality-gates.md) | pytest / ruff / pyright / 代码大小 / pre-commit / CodeGraph |
| [data-and-env.md](data-and-env.md) | SQLite / Redis、配置模块、.env 合并规则、关键环境变量 |
| [git-and-deploy.md](git-and-deploy.md) | Git 纪律、里程碑协议、部署 closeout |

## 相关文档（仓库内）

- `AGENTS.md` — 精简入口（硬规则摘要）
- `docs/AGENTS_REFERENCE_CN.md` — 完整 Agent 操作指南
- `docs/ARCHITECTURE.md` — 系统架构详述
- `docs/DEPLOY_AND_RELEASE_CONVENTION.md` — 部署与发布约定
- `STATUS.md` — 当前状态与里程碑
- `docs/AGENTS_PONYTAIL.md` — Ponytail 细则
