# provider_probe 离线包归档说明（CP-5）

> 版本：2026-06-16
> 关联：[`CODEBASE_COLD_PRUNE_PRIORITY_CN.md`](CODEBASE_COLD_PRUNE_PRIORITY_CN.md) P4

## 目的

将 **Cold** 的 `provider_probe` 从主仓根目录迁入 `packages/provider-probe-offline/`，明确其与 LiMa Router 热路径的边界，并统一 JDCloud 部署复制路径。

## 不变量

1. **禁止**在 `server.py`、`server_lifespan.py`、`routes/route_registry.py` 中 import `provider_probe`。
2. **`probe_loop.py`**（运行时后端探活）保留在仓库根，**不属于**本离线包。
3. JDCloud 节点 `117.72.118.95` 通过 `deploy/jdcloud/*.sh` 部署；主 VPS `chat.donglicao.com` 不挂载本包。
4. 自动化产出仅为 candidate/watchlist；合入 `backends_registry.py` 须人工 review。

## CP-5 变更（2026-06-16）

| 动作 | 路径 |
|------|------|
| 迁入 | `provider_probe/` → `packages/provider-probe-offline/provider_probe/` |
| 指针 | 根 `provider_probe/README.md`（无 Python 实现） |
| 部署 | `deploy/jdcloud/deploy_probe_platform.sh`、`install_playwright.sh` 更新源路径 |
| 测试 | `tests/test_browser_service.py` 保留；`pytest.ini` 增加 `pythonpath` |

## 回归门禁

```powershell
python -m pytest tests/test_browser_service.py tests/test_retrieval_injection.py tests/test_routing_engine.py -q
python -m py_compile packages/provider-probe-offline/provider_probe/browser_service.py packages/provider-probe-offline/provider_probe/discovery/scheduler.py
ruff check packages/provider-probe-offline/provider_probe tests/test_browser_service.py
```

## 后续（未执行）

- 抽成独立 git repo 或 PyPI 包（当前仍 monorepo 内归档）
- `test_browser_service.py` 迁至 `packages/provider-probe-offline/tests/`（可选）
