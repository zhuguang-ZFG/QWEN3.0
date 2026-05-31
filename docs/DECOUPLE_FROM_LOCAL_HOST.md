# 让 LiMa 脱离本机运行 — 设计文档

> 目标：所有 LiMa 后端服务在 VPS 上自给自足，不再依赖本地 Windows 主机。

## 现状全景

`runtime_topology.py:8-47` 定义 `LOCAL_ONLY_BACKENDS`（37 个 backend name），
`backends_registry.py:240-259` 在 import 时把这些后端从 `BACKENDS` pop 到
`DISABLED_HOST_DEPENDENT_BACKENDS`。它们通过 `LIMA_ENABLE_HOST_DEPENDENT_BACKENDS`
环境变量 + FRP 隧道端口检测来判定可用性。

逐后端现状：

| # | Backend | 实际 URL | 现状 | 决定 |
|---|---------|----------|------|------|
| 1 | `deepseek_free` | `127.0.0.1:8000` | 本机代理，用途不明 | 待确认后决定 |
| 2-7 | `ddg_*` (6) | `localhost:4500` | 本机 DuckAI (bun)，需 GFW 代理 | M6 决定 |
| 8-10 | `kimi*` (3) | `localhost:4504` | 本机 Node.js 代理，cookie 认证 | M3 迁 VPS |
| 11-12 | `scnet_large_ds_*` (2) | `localhost:4505` | 本机 Node.js 代理；VPS Python sidecar **已有完整代码** | M2 启用 |
| 13-15 | `longcat_web_*` (3) | `localhost:4506` | VPS 占位 sidecar，keepalive 已有 Playwright 刷新 | M4 实现 |
| 16-20 | `mimo_web_*` (5) | `VPS_HOST:4507` | VPS 占位 sidecar，需浏览器/cookie | M5 实现 |
| 21-32 | `oldllm_*` (12) | `llm.zhuguang.ccwu.cc` | **已是 CF Worker！** 标记错误 | M1 清理标记 |
| 33-40 | `local_*` (8) | `localhost:11434` | 本机 Ollama GPU 推理 | M1 删除 |
| 41-42 | `scnet_qwen235b_code`, `scnet_ds_pro_code` | `VPS_HOST:4505` | 走 SCNet Large sidecar 端口，状态同 #11-12 | 随 M2 |

## 迁移优先级

| 优先级 | 里程碑 | 后端数 | 风险 | 理由 |
|--------|--------|--------|------|------|
| P0 | M1 安全清理 | 20 | 零 | oldllm_* 已迁 CF Worker 只是标记错；local_* 用户明确不要 |
| P1 | M2 SCNet Large | 4 | 低 | Python sidecar 代码已完整，仅需配置启用 |
| P2 | M3 Kimi | 3 | 中 | 需重写 Node.js → Python，cookie 需手动刷新 |
| P3 | M4 LongCat | 3 | 中 | 需实现 sidecar |
| P4 | M5 MiMo | 5 | 中 | 需实现 sidecar |
| P5 | M6 DDG + deepseek_free | 7 | 低 | 先确认使用率再决定去留 |
| P6 | M7 收尾 | — | 低 | 停 Windows 进程 + FRP |

## 架构原则

- **每个 sidecar 独立文件 ≤300 行**（Superpowers #2）
- **`*_REVERSE_ENABLED` 环境变量门控**：关掉即回退旧路径（Superpowers #4/#6）
- **新旧并行**：Windows 代理保持运行直到 VPS sidecar 验证通过（Superpowers #6）
- **先验证后部署**：pytest 通过 → VPS health → smoke → 全量（Superpowers #3）

## 不做的事情

- 不重写路由逻辑（`smart_router.py` / `routing_engine.py`）
- 不改变 `backends.py` facade 接口
- 不迁移 `deepcode-cli`（独立 Node.js 项目）
- 不迁移 `esp32S_XYZ`、`wechat_bridge`（独立子项目）
