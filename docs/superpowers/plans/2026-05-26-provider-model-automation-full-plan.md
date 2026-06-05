# 免费模型自动发现与准入 — 详细实施方案（存档）

> **For agentic workers:** 本计划 **已存档、非当前执行主线**。当前优先：
> [`2026-05-26-telegram-github-maximization.md`](2026-05-26-telegram-github-maximization.md)
>
> **Goal:** 定期发现各供应商免费/变更模型，经分层验证后仅以 overlay 方式准入 `late_fallback`，永不自动修改 `backends_registry.py`。
>
> **Status:** 设计完成；`provider_automation/` 已实现 ~70%；**未接线**（零 live 快照、无 scheduler、无 `backend_admission.json` 路由合并）。
>
> **Created:** 2026-05-26 | **Evidence baseline:** `tests/test_provider_automation.py` 56 passed

---

## 1. 现状审计

### 1.1 已存在代码（可直接复用）

| 模块 | 路径 | 能力 |
|------|------|------|
| 目录与 delta | `provider_automation/catalog.py` | `ProviderModelEntry`、`compute_delta`、`ModelAdmissionStatus` |
| OpenRouter | `provider_automation/openrouter.py` | `parse_fixture()`、`fetch_live()`（门控 `LIMA_OPENROUTER_LIVE_FETCH=1`） |
| 分层探测 | `provider_automation/probe.py` | metadata → smoke → stream → coding → quality |
| 批量编排 | `provider_automation/runner.py` | `ProbeRunner` + injectable callables |
| 快照 | `provider_automation/snapshot_store.py` | `data/provider_snapshots/` JSON |
| 准入计划 | `provider_automation/admission.py` | `PatchPlan`；**不写** `backends_registry.py` |
| 报告 | `provider_automation/report.py` | Markdown 变更报告 |
| 审查包 | `provider_automation/review.py` | operator 审查 bundle |
| 影响 | `provider_automation/impact.py` | 退役影响检查 |
| 设计 | `docs/PROVIDER_MODEL_AUTOMATION_PLAN.md` | 状态机、数据文件、策略 |

### 1.2 缺口

| 缺口 | 影响 |
|------|------|
| 无 `scripts/provider_discover.py` 一键跑通 | 发现层从未生产运行 |
| 无 Cloudflare / Pollinations / SCNet / GitHub Models adapter | 仅 OpenRouter fixture |
| 无 `data/backend_admission.json` | 动态准入无处写入 |
| `router_v3` / `routing_engine` 不读 overlay | 即使写入也不路由 |
| 无 scheduler | 无 cron/daemon |
| ProbeRunner 未接 `http_caller` 按供应商 callable | 冒烟停留在框架层 |
| Telegram 日报未接 | 与 operator 闭环断开 |

### 1.3 与注册后端差距（2026-05-26 估计）

| 供应商 | 已注册（约） | 潜在未注册 | 发现方式 |
|--------|-------------|-----------|----------|
| OpenRouter `:free` | ~10 | 数十 | `GET /api/v1/models` |
| Cloudflare Workers AI | ~14 | ~28 | Account AI models search API |
| Pollinations | ~5 | 未知 | `GET /openai/models` |
| SCNet | ~7 | 若干 | 网页/内部 API（脆） |
| GitHub Models | ~8 | 未知 | Marketplace models API |
| DuckAI localhost | ~6 | 跟随上游 | `localhost:4500/v1/models` |

---

## 2. 架构：三层管道

```text
┌─────────────────────────────────────────────────────────┐
│  Scheduler (systemd timer / asyncio daemon)             │
│  每 6h: discover | 每 1h: health_ping | 每 4h: retest   │
│  每天 9: Telegram 日报（与 LiMa digest 合并或独立）      │
└───────────────────────────┬─────────────────────────────┘
                            │
     ┌──────────────────────┼──────────────────────┐
     ▼                      ▼                      ▼
┌──────────┐        ┌──────────────┐       ┌──────────────────┐
│ 发现层    │        │  验证层       │       │  准入层           │
│ Adapters │───────▶│ Smoke/Stream │──────▶│ late_fallback    │
│          │        │ Coding eval  │       │ (自动 overlay)   │
│          │        │ Latency      │       │ code_floor+ (人工)│
└────┬─────┘        └──────────────┘       └────────┬─────────┘
     │                                               │
     ▼                                               ▼
 data/provider_snapshots/                    data/backend_admission.json
 data/provider_model_deltas.json             (router merge, flag 默认 off)
 docs/PROVIDER_MODEL_CATALOG_REPORT.md
```

### 2.1 安全红线（不可妥协）

1. **永不**自动修改 `backends_registry.py` / `backends.py` 静态条目。
2. 探测 prompt 固定合成（`"Say OK only."`），不传私有代码/仓库上下文。
3. `private_code_allowed=false` 为默认；logging 模型不得进 IDE 路径。
4. 自动写入仅限 `admitted_late_fallback` + 非私有 chat fallback 池。
5. `LIMA_DYNAMIC_ADMISSION=0` 默认关；overlay merge 可一键禁用。
6. 每 adapter 独立 `try/except`；失败降级到上一快照。

---

## 3. 数据文件契约

### 3.1 快照

```text
data/provider_snapshots/
  openrouter-20260526-120000.json
  cloudflare-20260526-120000.json
  ...
```

由 `snapshot_store.save_snapshot()` 写入；保留每 provider 最近 30 份。

### 3.2 Delta

`data/provider_model_deltas.json`（或按 run 带时间戳）：

```json
{
  "run_id": "2026-05-26T12:00:00Z",
  "added": [{"provider": "openrouter", "model_id": "qwen/..."}],
  "removed": [],
  "changed": [],
  "suspicious": []
}
```

由 `catalog.compute_delta(previous, current)` 生成。

### 3.3 动态准入 overlay

`data/backend_admission.json`（初始 `{"overlays": []}`）：

```json
{
  "overlays": [
    {
      "backend_key": "or_free_qwen_coder",
      "provider": "openrouter",
      "model_id": "qwen/qwen3-coder:free",
      "tier": "late_fallback",
      "admission_status": "admitted_late_fallback",
      "private_code_allowed": false,
      "enabled": true,
      "expires_at": null,
      "evidence_refs": ["probe:2026-05-26T12:05:00Z"]
    }
  ]
}
```

路由层读取：`static BACKENDS ∪ enabled overlays`（feature flag 控制）。

---

## 4. 供应商适配器接口

```python
# provider_automation/adapters/base.py（待建）
class ProviderAdapter(Protocol):
    provider: str

    async def fetch_catalog(self) -> ProviderModelSnapshot: ...

    def map_to_backend_key(self, entry: ProviderModelEntry) -> str | None:
        """可选：映射到 LiMa backend 命名；None = 仅 watchlist"""
```

### 4.1 首批 adapter 规格

| Adapter | 文件 | 发现 API | 难点 | 估行 |
|---------|------|----------|------|------|
| OpenRouter | 已有 `openrouter.py` | `/api/v1/models` + `:free` 筛选 | endpoint 元数据需二次请求 | 0（接线） |
| Cloudflare | `adapters/cloudflare.py` | `/client/v4/accounts/{id}/ai/models/search` | Account ID、映射 `cf_*` | ~80 |
| Pollinations | `adapters/pollinations.py` | `/openai/models` | 无 key；命名 `poll_*` | ~50 |
| GitHub Models | `adapters/github_models.py` | Marketplace models | 已有 `GITHUB_TOKEN` | ~60 |
| SCNet | `adapters/scnet.py` | 内部/页面解析 | **脆**；建议 Phase 3+ | ~80 |
| DuckAI | 可选 | localhost models | 仅本机 | ~40 |

---

## 5. 验证管道

```text
discovered
  → metadata gate (endpoint/pricing/privacy)
  → completion_smoke (200 + 非空)
  → stream_smoke (可选)
  → coding_fixture (3 题合成，eval_coding_backends 子集)
  → quality_gate (可选)
  → admitted_late_fallback | watchlist | rejected
```

| 终态 | 自动路由 | 条件 |
|------|----------|------|
| `watchlist` | 否 | 无 endpoint / 隐私标记 / smoke 失败 |
| `admitted_late_fallback` | 是（overlay） | smoke 通过 + 非 coding 主路径 |
| `admitted_code_floor` | 有限 coding | smoke + coding eval + **Telegram 人工 Approve** |
| `admitted_primary` | 主池 | 稳定性证据 + 人工 + 全量 eval |

`ProbeRunner` 注入示例（OpenRouter）：

```python
runner.set_smoke_callable(lambda m, msgs, max_t: http_caller.call_api(
    f"or_{slug(m.model_id)}", msgs, max_t
)["answer"])
```

---

## 6. 实施分片（存档版工时）

| ID | 内容 | 依赖 | 估时 | 生产风险 |
|----|------|------|------|----------|
| **PA-A** | `scripts/provider_discover.py`：OpenRouter live → snapshot → delta → report | 无 | 4h | 无（只读） |
| **PA-B** | Cloudflare adapter + 同上管道 | PA-A | 6h | 无 |
| **PA-C** | Pollinations + GitHub Models adapter | PA-A | 6h | 无 |
| **PA-D** | `backend_admission.json` + `routing_engine` overlay merge + flag | PA-A | 8h | **中** |
| **PA-E** | ProbeRunner 接 http_caller（OR + CF） | PA-A | 8h | 低 |
| **PA-F** | `scripts/provider_model_scheduler.py` + systemd timer | PA-A | 6h | 低 |
| **PA-G** | Telegram 日报（发现 summary → `telegram_notify`） | PA-A, TG 稳定 | 4h | 无 |
| **PA-H** | Telegram 审批 `code_floor+`（复用 Approve 模式） | PA-D, PA-E | 8h | 中 |
| **PA-I** | SCNet adapter（可选） | PA-F | 10h | 低 |

**MVP（PA-A + PA-B + PA-G）：** ~2 天，零路由改动。  
**可回滚准入（+ PA-D + PA-E）：** +2 天。  
**完整方案（含 PA-H + PA-I）：** ~1 周。

> 原估算「6h 全完成」偏乐观；路由 overlay 与多供应商 callable 是主要变量。

---

## 7. 测试策略

| 层 | 命令 / 文件 |
|----|-------------|
| 单元 | `pytest tests/test_provider_automation.py -q`（已有 56） |
| 新 adapter | `tests/test_provider_adapters_*.py` fixture + 可选 live gate |
| 发现脚本 | `LIMA_OPENROUTER_LIVE_FETCH=1 python scripts/provider_discover.py --dry-run` |
| 路由 overlay | `tests/test_backend_admission_overlay.py`（待建） |
| 全量 | `pytest -q --ignore=active_model` |

---

## 8. 部署与运维

```text
# VPS（可选，与 LiMa router 同机或 Windows 本机带代理）
systemd: lima-provider-discover.timer  →  scripts/provider_discover.py
env: LIMA_OPENROUTER_LIVE_FETCH=1, CF_ACCOUNT_ID=..., GITHUB_TOKEN=...
```

- 发现脚本 **不得**与 `lima-router` 同进程阻塞；独立 timer 或 sidecar。
- 失败写 `progress.md` / Telegram，不 crash router。

---

## 9. 与 Telegram / GitHub 主线关系

本计划 **暂停执行**，待 [`2026-05-26-telegram-github-maximization.md`](2026-05-26-telegram-github-maximization.md) 完成 **TG-GH-2（LiMa 生命周期推送）** 与 **TG-GH-3（统一 Operator 简报）** 后再启动 **PA-G**，避免重复造通知通道。

---

## 10. 验收清单（未来启用时用）

- [ ] `data/provider_snapshots/` 有 OpenRouter + Cloudflare 时间戳文件
- [ ] `docs/PROVIDER_MODEL_CATALOG_REPORT.md` 或 Telegram 收到「新增 N 个 :free 模型」
- [ ] `backend_admission.json` 仅在 `LIMA_DYNAMIC_ADMISSION=1` 时影响 fallback 池
- [ ] 私有 `/code` 路径不命中 overlay 中 `private_code_allowed=false` 条目
- [ ] 全量 pytest 通过；VPS smoke 12/12 不退化

---

## 11. 参考文档

- `docs/PROVIDER_MODEL_AUTOMATION_PLAN.md` — 策略与状态机权威
- `docs/FREE_MODEL_ROUTING_STATUS.md` — 当前免费模型证据
- `docs/PERSONAL_CODING_ASSISTANT_PLAN.md` — 产品优先级
- `provider_automation/` — 实现源码
