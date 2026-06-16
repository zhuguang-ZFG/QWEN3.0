# provider_probe（已归档）

> 更新：2026-06-16（CP-5）

本目录仅保留**指针**。实现代码已迁至离线部署包：

[`packages/provider-probe-offline/`](../packages/provider-probe-offline/README.md)

## 说明

| 项 | 内容 |
|----|------|
| 层级 | **Cold** — 不得被 `server.py` / 路由默认挂载 |
| 运行时探活 | 仓库根 `probe_loop.py`（Warm），**与本包无关** |
| 运行节点 | JDCloud `117.72.118.95` 手动/定时；见 `deploy/jdcloud/` |
| 权威分层 | [`docs/CODEBASE_SUBSYSTEM_TIER_CN.md`](../docs/CODEBASE_SUBSYSTEM_TIER_CN.md) §6 |

本地开发与测试：将 `packages/provider-probe-offline` 加入 `PYTHONPATH`（`pytest.ini` 已配置）。
