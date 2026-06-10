# 免费模型路由状态

> 更新时间: 2026-05-26
> 范围: LiMa 中的 SCNet 和 Kimi 系列免费或接近免费的后端。

## 2026-05-26 重新评估 C（11 个后端全量）

命令: `eval_coding_backends.py` × 11 × 3 案例（约 3.3 分钟）。

| 后端 | 通过数 | 平均分 | 平均延迟 | 决策 |
|---|---:|---:|---:|---|
| `scnet_large_ds_pro` | 3/3 | 100 | 1232ms | 本地 4505 最快 pro |
| `scnet_qwen30b` / `scnet_large_ds_flash` / `scnet_qwen235b` / `scnet_ds_flash` | 3/3 | 100 | 1.3–2.0s | 第一梯队 |
| `scnet_ds_pro` | **3/3** | 100 | 6451ms | 深度梯队（超时 90 + 空响应保护） |
| `cf_kimi_k26` / `kimi_search` / `kimi_thinking` | 3/3 | 100 | 4.8–27s | 编码候选 |
| `kimi` | **3/3** | 100 | ~17s | timeout 45s；见 `kimi_eval_timeout45.json` |
| `stock_kimi_k2` | 0/3 | 0 | — | 不活跃 |

原始数据: `data/scnet_kimi_eval_20260526_full.json`、`docs/CODING_BACKEND_RANKING.md`。

---

## 2026-05-26 重新评估 B（JSON 围栏 + scnet_ds_pro 超时）

命令: `scripts/eval_coding_backends.py` — Kimi 三模式 + `scnet_ds_pro`（修复后）。

| 后端 | 通过数 | 平均分 | 平均延迟 | 决策 |
|---|---:|---:|---:|---|
| `kimi` / `kimi_thinking` / `kimi_search` | **3/3** | 100 | 3–11s | **编码候选**（JSON 围栏解析已修复） |
| `scnet_ds_pro` | **3/3** | 100 | 9–16s（复测；直连偶发空响应→`http_sync` 空体快速失败） | 恢复第一梯队深度推理候选（仍慢于 flash） |

原始数据: `data/scnet_kimi_eval_20260526b.json`、`data/scnet_ds_pro_eval_retry.json`。

---

## 2026-05-26 重新评估（本地 Windows 代理）

命令: `scripts/eval_coding_backends.py` 对 11 个 SCNet/Kimi 后端 × 3 个编码案例。

| 后端 | 通过数 | 平均分 | 平均延迟 | 决策 |
|---|---:|---:|---:|---|
| `scnet_large_ds_flash` | 3/3 | 100 | **1199ms** | **最快** 第一梯队 通过 `localhost:4505` |
| `scnet_qwen30b` | 3/3 | 100 | 1814ms | 第一梯队（VPS 直连） |
| `scnet_ds_flash` | 3/3 | 100 | 2205ms | 第一梯队 |
| `scnet_qwen235b` | 3/3 | 100 | 2388ms | 第一梯队 |
| `scnet_large_ds_pro` | 3/3 | 100 | 75046ms | 仅本地深度（对热路径太慢） |
| `kimi` / `kimi_thinking` / `kimi_search` | 2/3 | 80 | 4–7s | **已取代** — 见重新评估 B **3/3** |
| `cf_kimi_k26` | 1/3 | 48 | 6776ms | 仅回退 |
| `scnet_ds_pro` | 0/3 | 0 | 超时/冷却 | **已取代** — 超时 90 + 空响应保护；复测 **3/3** |
| `stock_kimi_k2` | 0/3 | 0 | 无效/冷却 | 不活跃 |

原始数据: `data/scnet_kimi_eval_20260526.json`、`docs/CODING_BACKEND_RANKING.md`。

**Kimi 状态变化：** 2026-05-22 记录 `chat.anonymous_usage_exceeded`；**2026-05-26 重新评估已恢复聊天**，仍不宜进入严格 JSON / 第一编码池。

---

## 当前答案

SCNet 直连模型足够强大以进入第一梯队编码路由。

LiMa 现在将 VPS 工作的直连 SCNet 模型提升到编码的第一梯队。Windows 本地代理路径也得到确认：SCNet-large 运行在 `D:\ollama_server` 端口 `4505` 上，并通过本地 LiMa 路由器工作。Kimi 端口 `4504` 正在运行，但其聊天调用当前失败，因为 Kimi 登录状态已回退到匿名配额。

## 第一梯队夹具证据

VPS 评估日期: 2026-05-22。

| 后端 | 通过数 | 平均分 | 平均延迟 | 决策 |
|---|---:|---:|---:|---|
| `scnet_ds_flash` | 3/3 | 100 | 3330ms | 第一梯队 |
| `scnet_qwen235b` | 3/3 | 100 | 4004ms | 第一梯队 |
| `scnet_qwen30b` | 3/3 | 91 | 2713ms | 第一梯队 |
| `scnet_ds_pro` | 3/3 | 91 | 4571ms | 第一梯队，排在更快的 SCNet 模型之后 |
| `cf_kimi_k26` | 1/3 | 48 | 7844ms | 仅回退 |
| `scnet_minimax` | 0/3 | 0 | 10145ms | 不活跃，超时 |
| `scnet_large_ds_flash` | 3/3 本地路由评估 | 100 | 987ms | 强本地/FRP 候选；仅在本地代理拓扑保护下提升 |
| `scnet_large_ds_pro` | 3/3 本地路由评估 | 100 | 3899ms | 强本地/FRP 候选，比 flash 慢 |
| `stock_kimi_k2` | 0/3 | 0 | 525ms | 不活跃，无效响应 |
| `kimi` | 认证/配额失败 | 0 | 0ms | 端口 `4504` 运行，但聊天返回 `chat.anonymous_usage_exceeded` |
| `kimi_thinking` | 认证/配额失败 | 0 | 0ms | 端口 `4504` 运行，被 Kimi 登录状态阻止 |
| `kimi_search` | 认证/配额失败 | 0 | 0ms | 端口 `4504` 运行，被 Kimi 登录状态阻止 |

原始摘要: `data/free_model_first_tier_eval.json`。

## VPS 冒烟证据

冒烟提示: `Say OK only.`

| 后端 | 状态 | 延迟 | 路由决策 |
|---|---:|---:|---|
| `scnet_ds_flash` | OK | 2904ms | 活跃免费回退用于编码/聊天。 |
| `scnet_ds_pro` | OK | 26496ms | 强/深度回退，因为慢。 |
| `scnet_qwen235b` | OK | 2110ms | 活跃免费回退用于编码/聊天。 |
| `scnet_qwen30b` | OK | 1727ms | 活跃快速/聊天回退。 |
| `scnet_minimax` | 超时 | 30742ms | 已注册，默认池中不活跃。 |
| `scnet_large_ds_flash` | 本地路由评估 OK | 987ms 平均 | 已注册；Windows 本地代理 `4505` 兼容编码夹具。 |
| `scnet_large_ds_pro` | 本地路由评估 OK | 3899ms 平均 | 已注册；强但比 `flash` 慢。 |
| `cf_kimi_k26` | OK | 9987ms | 活跃聊天回退；编码回退仅在更强模型之后。 |
| `stock_kimi_k2` | 无效响应 | 2070ms | 已注册，默认池中不活跃。 |
| `kimi` | 认证/配额失败 | 0ms | 已注册；Windows 本地代理 `4504` 运行，但 Kimi 会话需要重新登录。 |
| `kimi_thinking` | 认证/配额失败 | 0ms | 已注册；Windows 本地代理 `4504` 运行，但 Kimi 会话需要重新登录。 |
| `kimi_search` | 认证/配额失败 | 0ms | 已注册；Windows 本地代理 `4504` 运行，但 Kimi 会话需要重新登录。 |

## 代码更改

| 文件 | 更新 |
|---|---|
| `code_orchestrator.py` | 将 `scnet_ds_flash`、`scnet_qwen235b`、`scnet_qwen30b` 和 `scnet_ds_pro` 提升到第一梯队编码池。 |
| `router_v3.py` | 将 VPS 工作的 SCNet 直连模型提升到 IDE/chat/code/chat_fast 池的前端。 |
| `test_routing_engine.py` | 为 SCNet 第一梯队排序和 Kimi 回退位置添加回归覆盖。 |

## DuckAI 本地准入证据

本地评估日期: 2026-05-22。命令输出记录在 `data/ddg_route_admission_eval.json` 和 `docs/DDG_ROUTE_ADMISSION.md` 中。

| 后端 | 通过数 | 平均分 | 平均延迟 | 决策 |
|---|---:|---:|---:|---|
| `ddg_gpt4o_mini` | 3/3 | 100 | 3022ms | 后期本地回退；非第一梯队。 |
| `ddg_gpt5_mini` | 3/3 | 100 | 3626ms | 后期本地回退；非第一梯队。 |
| `ddg_claude_haiku_45` | 2/3 | 58 | 2358ms | 仅类聊天回退；严格 JSON 输出失败。 |
| `ddg_tinfoil_gptoss_120b` | 0/3 | 0 | 89ms | 不活跃；上游 500 和冷却。 |

## 部署证据

- 路由更改后的本地测试: `71 passed in 0.52s`。
- VPS 备份: `/opt/lima-router/backups/free-model-routing-20260522_184556`。
- 远程编译对更改的路由文件通过。
- VPS 本地 `/health` 在重启恢复后返回 200。
- 公共编码冒烟返回 200 在 4585ms。
- 公共 Anthropic 工具冒烟返回 200 在 672ms 带有 `stop_reason=tool_use`。

## 第一梯队部署证据

- 第一梯队提升后的本地测试: `71 passed in 0.59s`。
- VPS 备份: `/opt/lima-router/backups/scnet-first-tier-20260522_190032`。
- 远程编译对 `server.py`、`routing_engine.py`、`code_orchestrator.py` 和 `router_v3.py` 通过。
- VPS 本地 `/health` 在重启后返回 200。
- VPS 路由顺序冒烟确认编码选择从 `scnet_ds_flash`、`scnet_qwen235b`、`scnet_qwen30b`、`scnet_ds_pro` 开始，然后是 `github_gpt4o`。
- 公共编码冒烟返回 200 在 3347ms。

## 策略

- 编码主路由保持证据驱动：SCNet 直连模型现在领先，因为它们通过了生产 VPS 夹具。
- `scnet_ds_flash`、`scnet_qwen235b` 和 `scnet_qwen30b` 是第一梯队编码候选。
- `scnet_ds_pro` 也具有第一梯队资格，但由于延迟/格式差异排在更快的 SCNet 模型之后。
- `cf_kimi_k26` 可用但速度慢且冗长，因此保留用于回退而非第一梯队 IDE 编码。
- 本地代理模型必须通过 Windows LiMa 路由器路径验证，而不是通过检查 VPS `localhost:4504/4505`。
- Kimi 本地故障应视为 `manual_refresh_required` 或 `quota_exhausted`，而不是在热路径中重复重试。
- DuckAI `ddg_gpt4o_mini` 和 `ddg_gpt5_mini` 仅在公共通道修复且更长的稳定性运行通过后才作为后期本地回退准入。
- SCNet-large 在 Windows 本地路由上很强，但不得在无法到达 Windows `localhost:4505` 的 VPS 进程上提升。
- 未来的免登录 Web AI 适配器必须在通过 `docs/FREE_WEB_AI_EXPANSION_PLAN.md` 中的准入规则之前远离第一梯队编码。
- `health_tracker.record_failure` 现在接受 `error_text`，分类 Kimi 匿名配额/会话故障，并存储后端状态以便后续路由跳过/评分。

## 下一步验证

当代理服务有意启动时：

```bash
curl -sS http://127.0.0.1:4504/v1/models
curl -sS http://127.0.0.1:4505/v1/chat/completions
curl -sS http://127.0.0.1:8080/v1/chat/completions
```

然后对以下后端重新运行编码评估：

- `kimi`
- `kimi_thinking`
- `kimi_search`
- `scnet_large_ds_flash`
- `scnet_large_ds_pro`