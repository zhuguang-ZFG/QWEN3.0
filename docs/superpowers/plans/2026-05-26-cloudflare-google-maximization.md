# Cloudflare × Google 免费账号利用最大化 — 详细实施方案

> **For agentic workers:** 文档先行；与
> [`2026-05-26-telegram-github-maximization.md`](2026-05-26-telegram-github-maximization.md)
> 并行规划，**次于 TG-GH-2** 启动编码实现。
>
> **Goal:** 把你已有的 **Cloudflare 账号** 与 **Google AI 免费额度** 变成 LiMa 可观测、可路由、可回退的生产力层——而不是注册后闲置。
>
> **Status:** Active plan | **Created:** 2026-05-26
>
> **Related:** `docs/CLOUDFLARE_MODEL_INVENTORY.md`、`docs/FREE_MODEL_ROUTING_STATUS.md`、
> `docs/superpowers/plans/2026-05-26-provider-model-automation-full-plan.md`（PA-B Cloudflare adapter）

---

## 1. 战略定位

```text
LiMa 路由池
  ├── L0  SCNet / 本地代理（第一优先，已验证）
  ├── L1  Cloudflare Workers AI（零/低边际成本，账号 API + Worker 双路径）
  ├── L2  Google Gemini/Gemma 免费 API（chat/vision floor）
  ├── L3  GitHub Models / OpenRouter :free / …
  └── Lx  late_fallback（动态发现 overlay，未来）

Cloudflare 账号额外价值（非 chat）:
  Pages（官网静态）| AI Gateway（可选）| R2（暂不需要）

Google 账号额外价值:
  Gemini Flash 系列 chat | Flash Lite 极速 | Gemma | 未来 embeddings（ gated）
```

**原则：**
- 免费额度要 **跑满但不爆**——`budget_manager` + 路由 tier + 告警。
- 新模型 **先发现 → 冒烟 → eval → 再进池**；不跳过证据。
- CF 直连与 `cfai_*` Worker **双轨冗余**；一条挂掉另一条顶上。
- Google 适合 **chat_fast / vision floor**；编码主路径仍以 SCNet + `cf_qwen_coder` 为先。

---

## 2. 现状审计（2026-05-26）

### 2.1 Cloudflare Workers AI

| 路径 | 已注册 | 在路由池 | 缺口 |
|------|--------|----------|------|
| 直连 `cf_*`（Account API） | **14** | 多数在 `router_v3` code/chat medium+ | Dashboard 约 **~28** 模型未注册 |
| Worker `cfai_*`（零 key） | **4** 有效 | `cfai_qwen_coder` 等 | `cfai_mistral` HTTP 500 未准入 |
| `cf_vision` | 1 | vision 路由待确认 | 消息格式/adapter 需 smoke |
| Embeddings / 图像 / TTS | 0 | 未接 chat 热路径 | 见 Phase CF-G-4 |

**环境：** VPS 可直连 `cf_qwen_coder`；本地 shell 常缺 `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_TOKEN`（测试限制，非生产故障）。

**预算：** `budget_manager.py` **未配置任何 `cf_*`** → 无法自动降优先级或日限额告警。

### 2.2 Google AI（Gemini API 免费层）

| Backend | 模型 | 路由角色 | 缺口 |
|---------|------|----------|------|
| `google_flash_lite` | gemini-3.1-flash-lite | chat/ide **floor** | 无自动模型列表轮询 |
| `google_flash` | gemini-2.5-flash | chat floor + vision 候选 | 同上 |
| `google_gemini3` | gemini-3-flash | chat medium/floor | 同上 |
| `google_gemma4` | gemma-3-27b-it | chat floor | 同上 |

**预算：** 已配 `daily_limit=1000`（三模型）；`google_flash` 未单独列 budget（走默认无限需补）。

**编码池：** `code_orchestrator` **未** 纳入 Google → 正确（免费 Gemini 非编码第一选择）。

### 2.3 与 Provider Automation 关系

| 能力 | CF | Google |
|------|----|--------|
| 模型列表 API | `accounts/{id}/ai/models/search` | `generativelanguage.googleapis.com/v1beta/models` |
| PA 存档计划 | **PA-B** Cloudflare adapter | **PA-C 扩展** Google adapter |
| 自动 late_fallback | overlay | overlay |

---

## 3. 利用最大化矩阵

| 资源 | 当前利用率 | 目标 | 手段 |
|------|-----------|------|------|
| CF 10k neurons/天（免费档） | 低（14/42 模型注册） | **≥80% 有效模型进 fallback** | 发现 + 冒烟 + 注册 |
| CF Worker 零 key | 中（3/4 可用） | Worker 作 VPS 密钥丢失时的 **备份路径** | 修复 cfai_mistral 或退役 |
| CF Vision | 几乎未用 | 视觉请求走 `cf_vision` / `cf_gemma4` | vision smoke + 路由 |
| Google 免费 RPM/RPD | 中（4 模型在 floor） | flash_lite 扛 **chat_fast** 流量 | tier 调整 + budget |
| Google Gemini 新模型 | 未知 | 季度轮询 + Telegram 通知 | Google adapter |
| CF Pages | 未用 | **官网静态**（国内优于 GitHub Pages） | 见 CF-G-5 |
| Gitee Pages | 未用 | 国内静态站备选 | 见 [`GI-G-4`](2026-05-26-gitee-maximization.md) |
| 配额可见性 | Telegram `/budget` 部分 | CF/Google 用量进 **早报** | TG-GH-3 扩展 |

---

## 4. 实施分片

### Phase CF-G-0 — 基线盘点（P0，~3h，无路由改动）

**目标：** 一份可信的「账号里到底有什么」清单。

| Task | 产出 |
|------|------|
| 0.1 | `scripts/inventory_cloudflare_models.py` — 调 CF models search API → JSON |
| 0.2 | `scripts/inventory_google_models.py` — 调 Google ListModels → JSON |
| 0.3 | `data/cf_model_inventory.json`、`data/google_model_inventory.json` |
| 0.4 | 与 `backends_registry.py` diff 报告 → `docs/CF_GOOGLE_INVENTORY_REPORT.md` |

**环境（VPS `.env`，勿提交）：**
```bash
CLOUDFLARE_ACCOUNT_ID=...
CLOUDFLARE_TOKEN=...
GOOGLE_AI_KEY=...
```

**验收：** 报告列出「已注册 / 未注册 / 已注册但不在路由池」。

---

### Phase CF-G-1 — 预算与告警（P0，~4h）

**目标：** 免费额度 **跑满可控**。

| Task | 文件 |
|------|------|
| 1.1 | `budget_manager.py` 增加 `cf_*` 家族预算（建议 daily 800–1500/模型，共享 CF 日池 warn 70%） |
| 1.2 | 增加 `google_flash` budget；CF 账户级聚合 warn |
| 1.3 | `health_tracker` / `telegram_notify` — 预算 80%/100% 推送 |
| 1.4 | Telegram `/budget` 显示 CF + Google 分组 |

**验收：** 模拟高用量 → Telegram 收到 warn；`/budget` 显示 cf_qwen_coder 计数。

---

### Phase CF-G-2 — Cloudflare 模型扩容（P1，~1 天）

**依赖：** CF-G-0；可与 Provider **PA-B** 合并实现。

| Task | 内容 |
|------|------|
| 2.1 | `provider_automation/adapters/cloudflare.py` |
| 2.2 | 对 **新增** chat/code 模型跑 `ProbeRunner` smoke（合成 prompt） |
| 2.3 | 通过者写入 `backends_registry.py`（**人工 review PR**）或 `backend_admission.json` overlay |
| 2.4 | `router_v3` / `code_orchestrator` — 新 `cf_*` 进 **medium/floor**，不进 first-tier |
| 2.5 | 修复或移除 `cfai_mistral`；验证 Worker 路径冗余 |

**准入规则：**
- smoke 200 + 延迟 <15s → `late_fallback` / chat medium
- coding fixture ≥2/3 → code **floor**（非 primary）
- 失败 → watchlist，不进池

**验收：** 未注册 CF 模型数下降 ≥50%；VPS smoke `cf_qwen_coder` + 1 个新模型 OK。

---

### Phase CF-G-3 — Google 免费层优化（P1，~6h）

| Task | 内容 |
|------|------|
| 3.1 | `inventory_google_models.py` 定期 diff |
| 3.2 | 路由：`google_flash_lite` 提前到 `chat_fast.strong`（低成本短回复） | ✅ |
| 3.3 | `google_flash` 绑定 vision 路径（与 `cf_vision` 并列 fallback） | ✅ |
| 3.4 | 编码请求 **不** 默认 Google（保持现状）；仅 explicit model 或 public chat |
| 3.5 | eval：`scripts/eval_coding_backends.py` 子集跑 Google（记录证据，不 promote） |

**验收：** IDE chat_fast 请求可观察到 `google_flash_lite` 命中；vision 请求有 Google/CF 双 fallback 证据。

---

### Phase CF-G-4 — 非 Chat 能力（P2，可选）

| 能力 | CF API | LiMa 接入点 |
|------|--------|-------------|
| Embeddings | `@cf/baai/bge-*` | `routes/embeddings.py` 扩展 provider |
| 图像生成 | CF flux/SD | 已有 `routes/images.py` / Pollinations 并列 |
| TTS/ASR | CF audio 模型 | `stt.py` / `mimo_tts` 备选 |

**默认 off**；每项独立 smoke + 文档。

---

### Phase CF-G-5 — CF Pages 官网（P2，与 TG-GH / 官网讨论衔接）

| 对比 | GitHub Pages | **CF Pages** |
|------|-------------|--------------|
| 国内访问 | 一般 | **通常更好** |
| `/api/demo` | 需改 JS 跨域 | 同左，或 Workers 反代 |
| 与 CF 账号 | 分离 | **同一账号** |

**步骤：** `donglicao-site/` → CF Pages project → `www.donglicao.com` CNAME → demo 改调 `chat.donglicao.com/v1`。

**验收：** 官网可访问；demo 对话 OK；VPS `/www/wwwroot/donglicao-site` 可下线释空间。

---

### Phase CF-G-6 — 可观测与 Telegram 闭环（P1，~4h）

与 **TG-GH-3 早报** 合并：

```text
LiMa Daily · CF/Google
CF: 1423/10000 neurons (est.) | 3 models added this week
Google: flash_lite 812/1000 RPD | gemini3 104/1000
Top used: cf_qwen_coder, google_flash_lite, scnet_ds_flash
Dead: cfai_mistral (500)
```

| Task | 说明 |
|------|------|
| 6.1 | `budget_manager.get_usage_summary()` 按 provider 分组 |
| 6.2 | 早报段落 + CI fail / GitHub 并列 |
| 6.3 | 每周 inventory diff → Telegram（新 Gemini / 新 @cf 模型） |

---

## 5. 路由策略（目标态）

### 5.1 编码（IDE / private code）

```text
1. scnet_ds_flash, scnet_qwen235b, scnet_qwen30b, scnet_ds_pro
2. cf_qwen_coder, cfai_qwen_coder, cf_gptoss_120b, cf_deepseek_r1
3. github_gpt4o, or_* …
4. [动态 overlay late_fallback]
×  google_* （不进默认 coding 池）
```

### 5.2 快速 chat / 访客

```text
1. scnet_qwen30b, longcat_lite
2. google_flash_lite, google_flash
3. cf_llama4, cf_gemma4
4. cf_kimi_k26（最后，慢）
```

### 5.3 Vision

```text
cf_vision → google_flash → github_gpt4o → mistral_pixtral
```

---

## 6. 安全与合规

| 风险 | 护栏 |
|------|------|
| 免费额度突然耗尽 | budget + 自动降 tier + Telegram |
| CF/Google 日志隐私 | 私有代码路径不默认 Google；data policy 标记 |
| 自动注册污染 | overlay + late_fallback only；registry 改动走 review |
| API key 泄露 | 仅 VPS `.env`；inventory 脚本 redact |
| Worker 500 | health_tracker 熔断；不进入 active pool |

---

## 7. 文件清单（预计）

```text
scripts/
  inventory_cloudflare_models.py   # CF-G-0
  inventory_google_models.py       # CF-G-0
  smoke_cf_google_backends.py      # CF-G-2/3 集中 smoke

provider_automation/adapters/
  cloudflare.py                    # CF-G-2 (= PA-B)
  google_models.py                 # CF-G-3

data/
  cf_model_inventory.json
  google_model_inventory.json

budget_manager.py                  # CF-G-1
docs/CF_GOOGLE_INVENTORY_REPORT.md # 生成物
```

---

## 8. 优先级与依赖

```text
并行轨道:
  TG-GH-1/2（Telegram 可靠性 + LiMa Code 推送）     ← 仍是最先
  CF-G-0 + CF-G-1（盘点 + 预算）                   ← 可立即做，零路由风险
  CF-G-2 + PA-B（CF 发现与扩容）                   ← CF-G-0 之后
  CF-G-3（Google 路由优化）                        ← CF-G-0 之后
  CF-G-6（早报）                                   ← 依赖 TG-GH-3
  CF-G-5（CF Pages 官网）                          ← 可选，独立
  CF-G-4（embeddings/图像）                        ← 锦上添花
```

**建议第一刀：** CF-G-0  inventory 脚本（今天就能看见「漏了哪些免费模型」）。

---

## 9. 验收总清单

- [ ] CF / Google 模型 inventory JSON 与 diff 报告
- [ ] 所有 active `cf_*` / `google_*` 有 budget 配置
- [ ] 预算告警进 Telegram
- [ ] 至少 **5 个** 新 CF 模型经 smoke 进入 fallback 池
- [ ] `google_flash_lite` 在 chat_fast 有实测命中
- [ ] Worker `cfai_*` 与直连 `cf_*` 故障切换 evidence
- [ ] 文档 + `progress.md` 证据；全量 pytest 不退化

---

## 10. 参考文档

| 文档 | 用途 |
|------|------|
| `docs/CLOUDFLARE_MODEL_INVENTORY.md` | CF 已注册模型 |
| `docs/CLOUDFLARE_WORKER_QUICK_EVAL.md` | Worker eval 证据 |
| `docs/FREE_MODEL_ROUTING_STATUS.md` | 免费模型 tier 决策 |
| `docs/superpowers/plans/2026-05-26-provider-model-automation-full-plan.md` | 发现管道存档 |
| `docs/superpowers/plans/2026-05-26-telegram-github-maximization.md` | 告警/早报通道 |
