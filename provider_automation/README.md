# provider_automation — 提供商模型准入（Warm / Cold 分层）

> 更新：2026-06-16（CP-3）
> 分层权威：[`docs/CODEBASE_SUBSYSTEM_TIER_CN.md`](../docs/CODEBASE_SUBSYSTEM_TIER_CN.md) §7

## 定位

发现新提供商模型、探测连通性、生成 **candidate / watchlist** 证据。**不得**自动写入 `backends_registry.py` 或开启 `ROUTING_ENABLED`。

## Warm（生产只读叠加）

| 模块 | 触及点 |
|------|--------|
| `adapters/cloudflare.py` | `backend_admission_store.apply_startup()` |
| `adapters/gitee_ai.py` | 同上 |
| `catalog.py`（类型/状态枚举） | adapters + `backend_admission_store` 读 overlay |

启动路径：`server_lifespan.py` → `backend_admission_store.apply_startup()`（需 `LIMA_DYNAMIC_ADMISSION=1` 才合并路由）。

## Cold（离线流水线）

| 模块 | 用途 |
|------|------|
| `runner.py` / `probe.py` | 批量探测 |
| `openrouter.py` | fixture 解析；live fetch 需 `LIMA_OPENROUTER_LIVE_FETCH=1` |
| `admission.py` / `report.py` / `review.py` / `impact.py` | 准入计划与报告 |
| `snapshot_store.py` | 快照持久化 |

**禁止**在 `server.py` / 设备热路径默认 import `runner` / `probe`。

## CLI 入口（运维）

```powershell
# 显式门控，仅 metadata 探测（默认 fixture）
$env:LIMA_PROVIDER_AUTOMATION_RUN = "1"
python scripts/provider_automation/run_probe_batch.py --fixture data/openrouter_fixture.json

# OpenRouter 实时拉取（额外门控）
$env:LIMA_OPENROUTER_LIVE_FETCH = "1"
python scripts/provider_automation/run_probe_batch.py --live-openrouter
```

## 不变量测试

```powershell
python -m pytest tests/test_provider_automation_admission.py tests/test_provider_automation_runner.py -q
```

## 相关

- 叠加存储：`backend_admission_store.py` → `data/backend_admission.json`
- 设备模型准入（独立轨道）：`docs/model_admission/` + `scripts/eval_device_model_role.py`
