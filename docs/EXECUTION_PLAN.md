# LiMa 执行计划

> 创建: 2026-05-21
> 状态: 历史计划，已被 `docs/PERSONAL_CODING_ASSISTANT_PLAN.md` 取代；其中开放平台和商业化 Sprint 不再作为当前方向。
> 原则: Superpowers — 自主推进，并行执行，先交付再完善
> 前置: 全量审计完成，所有未闭环项已识别

---

## 执行总览

```
Sprint 0 (30min)  安全修复 + Git清理 + 基础设施
Sprint 1 (1h)     死代码清理 + Phase 4 收尾
Sprint 2 (30min)  生产部署 V3 + 私用 API 验证
Sprint 3 (2-3h)   双轨路由实现
Sprint 4 (2h)     限流 + 稳定性接入
Sprint 5 (半天)   个人编码助手评测闭环
```

---

## Sprint 0: 安全 + 卫生（立即执行）

### 0.1 移除硬编码密码

**文件**: `deploy_v3.py:16`

```python
# 之前
PASS = "***"  # 硬编码密码

# 之后
PASS = os.environ.get("LIMA_DEPLOY_PASS")
if not PASS:
    sys.exit("ERROR: set LIMA_DEPLOY_PASS env var")
```

### 0.2 文档脱敏

旧开放平台商业化文档已删除。当前敏感信息处理按个人编码助手方向继续，详见 `docs/PERSONAL_CODING_ASSISTANT_PLAN.md`。

### 0.3 创建 requirements_server.txt

```
fastapi>=0.111.0
uvicorn>=0.30.0
httpx>=0.27.0
python-dotenv>=1.0.0
pybreaker>=1.2.0
paramiko>=3.4.0
edge-tts>=6.1.0
```

### 0.4 补全 .env.example

追加:
```
LONGCAT_URL=
LONGCAT_MODEL=
GPT_API_KEY=
LIMA_DEPLOY_PASS=
```

### 0.5 Git 清理

```bash
# 提交训练数据删除（有意清理）
git add -u data/training_data/
git add -u auto_distill_main.py auto_retrain.py auto_trainer.py context_feature_extractor.py
git commit -m "chore: 移除训练数据和废弃训练脚本"

# 删除断裂引用
git rm train_router_model.py  # imports 已删除的 context_feature_extractor
git commit -m "chore: 删除不可运行的训练脚本"

# .gitignore 补充
echo "_stream_test.py" >> .gitignore
echo "_tcf2.py" >> .gitignore
```

### 0.6 修复 test_streaming.py

将模块级 HTTP 调用包装为 pytest 函数，加 `@pytest.mark.integration` 标记。

---

## Sprint 1: 死代码清理 + Phase 4 收尾

### 1.1 删除确认死亡的模块

| 操作 | 文件 | 理由 |
|------|------|------|
| 删除 | `v3_integration.py` | 被 routing_engine.py 完全覆盖 |
| 删除 | `health_probe.py` | 与 probe_loop.py 重叠，从未接入 |
| 删除 | `quota_tracker.py` | 与 budget_manager.py 重叠 |

### 1.2 决策：stats_collector.py

**选项 A（推荐）**: 接入 server.py，在请求完成后调用 `stats_collector.record_request()`
**选项 B**: 删除，统计功能由外部日志系统承担

→ 选 A，接入点: `server.py` 的 `_handle_chat()` 返回前。

### 1.3 决策：fallback_chain.py

**选项 A**: 将 `quality_check()` 接入 `routing_engine.execute()` 返回值校验
**选项 B（推荐）**: 删除整个文件，routing_engine 已有完整 fallback 逻辑

→ 选 B，routing_engine + health_tracker 已覆盖所有降级场景。

### 1.4 smart_router.py 瘦身

目标: 1944 行 → <500 行

**删除清单（已迁移到其他模块的代码）:**
- `BACKENDS` 字典 → backends.py
- `call_api()` / `call_api_stream()` → http_caller.py
- `cb_allow()` / `cb_record()` / `cb_status()` → health_tracker.py
- `route()` / `analyze()` / `select_backend()` → routing_engine.py
- `clean_response()` → response_builder.py (已有)
- 所有 `_INSTANT_REPLIES` 残留 → 已删除但可能有引用

**保留（server.py 仍依赖，后续迁移）:**
- `predict_fast_backend()` → 后续移入 speculative.py
- `get_thinking_backend()` → 后续移入 router_v3.py
- `detect_image_intent()` → 已在 vision_handler.py，删 smart_router 版本
- 常量: `PUBLIC_MODEL_NAME`, `DEBUG`, `VISION_SYSTEM_PROMPT` → 移入 config.py

### 1.5 router_v3.py 清理未调用函数

将以下函数标记为内部使用或删除:
- `p2c_select` → routing_engine.select() 应调用它（接入）
- `detect_mass_failure` → health_tracker 已有实现（删除重复）
- `compute_health_score` → health_tracker 已有（删除重复）
- `semantic_cache_key` → semantic_cache.py 已有（删除重复）
- `get_skills_to_inject` → skills_injector 已有（删除重复）

---

## Sprint 2: 生产部署

### 2.1 部署 V3 到服务器

```bash
# 前置: 确保 LIMA_DEPLOY_PASS 已设置
export LIMA_DEPLOY_PASS="..."
python deploy_v3.py
```

部署内容: 17 个 V3 模块 + patch_server_v3 修改 server.py 接入点

### 2.2 验证

```bash
# SSH 到服务器后
curl -s http://localhost:8080/health
curl -s -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"lima-1.3","messages":[{"role":"user","content":"hello"}],"max_tokens":50}'
```

### 2.3 开放平台 P0 修复

```sql
-- 修复 Channel 端口
sqlite3 /opt/new-api/one-api.db \
  "UPDATE channels SET base_url='http://localhost:8080' WHERE base_url LIKE '%8090%' OR base_url LIKE '%9090%';"

-- 重启
podman restart new-api
```

### 2.4 端到端 IDE 测试

用 Claude Code 连接 `https://api.donglicao.com`，发送编程请求，验证:
- 响应正常
- x_lima_meta 包含 backend 信息
- 流式输出逐 token 到达

### 2.5 systemd 配置

```ini
# /etc/systemd/system/lima-router.service
[Unit]
Description=LiMa AI Router
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/lima-router
ExecStart=/usr/bin/python3 -m uvicorn server:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5
EnvironmentFile=/opt/lima-router/.env

[Install]
WantedBy=multi-user.target
```

---

## Sprint 3: 双轨路由实现

### 3.1 新增 classify_scenario()

**文件**: `routing_engine.py`（在 classify 层扩展）

```python
def classify_scenario(query: str, messages: list, ide: str = "") -> str:
    if ide and ide.lower() in ("claude code", "cursor", "aider", "cline", "codex"):
        return "coding"
    last_msg = messages[-1]["content"] if messages else query
    if "```" in last_msg or "Traceback" in last_msg or "Error:" in last_msg:
        return "coding"
    code_keywords = {"def ", "class ", "import ", "function ", "const ", "async "}
    if any(kw in last_msg for kw in code_keywords):
        return "coding"
    return "chat"
```

### 3.2 定义双池

**文件**: `router_v3.py` POOLS 扩展

```python
POOLS["code"] = [
    "scnet_ds_pro", "nvidia_qwen_coder", "cf_qwen_coder",
    "mistral_codestral", "longcat_thinking", "scnet_qwen235b",
    "or_qwen3_coder", "groq_llama70b",
]
POOLS["chat"] = [
    "groq_llama70b", "groq_qwen32b", "cerebras_gptoss",
    "scnet_ds_flash", "longcat_lite", "longcat_chat",
    "kimi", "scnet_qwen30b",
]
```

### 3.3 路由入口适配

`routing_engine.select()` 根据 scenario 选择 POOLS["code"] 或 POOLS["chat"]。

### 3.4 测试

```python
# test_dual_track.py
def test_ide_forces_coding():
    assert classify_scenario("hi", [], ide="Claude Code") == "coding"

def test_code_block_is_coding():
    assert classify_scenario("```python\nprint()```", []) == "coding"

def test_plain_chinese_is_chat():
    assert classify_scenario("今天天气怎么样", []) == "chat"
```

---

## Sprint 4: 限流 + 稳定性接入

### 4.1 创建 rate_limiter.py

滑动窗口 IP 限流，接入 server.py `/v1/chat/completions` 入口。

### 4.2 接入 health_tracker 质量追踪

当前 `detect_degradation()`, `score_response_quality()` 已实现但未被调用。
接入点: `routing_engine.select()` 过滤 dead 后端，degraded 排末尾。

### 4.3 接入 stats_collector

`server.py` 请求完成后调用 `stats_collector.record_request()`。

---

## Sprint 5: 开放平台 P1 + NextChat

### 5.1 重置 root 密码 + 品牌修复

通过 SSH 执行 SQL 修改 New API 数据库。

### 5.2 部署 NextChat

```bash
docker run -d --name nextchat -p 3002:3000 \
  -e OPENAI_API_KEY=sk-free-trial \
  -e BASE_URL=https://api.donglicao.com \
  -e CUSTOM_MODELS=-all,+lima-1.3 \
  -e SITE_TITLE="LiMa AI" \
  yidadaa/chatgpt-next-web
```

### 5.3 Nginx + DNS

- chat.donglicao.com → localhost:3002
- DNS A 记录添加

---

## 不做的事（明确排除）

| 排除项 | 原因 |
|--------|------|
| 支付系统 | 阻塞于企业资质，非技术问题 |
| vLLM 替换 | 需 Linux/WSL，当前 Windows 不支持 |
| OAuth 登录 | P2 优先级，不阻塞核心功能 |
| server.py 完全拆分至 <800 行 | 风险高，等 V3 生产稳定后再做 |
| 重写 orchestrate.py | 不在本轮范围 |
| Anthropic SSE 完全提取 | thinking mode 耦合深，保留 server.py |

---

## 验收标准

| Sprint | 完成定义 |
|--------|----------|
| 0 | deploy_v3.py 无明文密码 + requirements_server.txt 存在 + git clean |
| 1 | 5 个死文件已删 + smart_router <500行 + 零断裂引用 |
| 2 | 生产 /health 200 + IDE 端到端通过 + 平台 API 可调用 |
| 3 | classify_scenario 测试通过 + 编程请求走 code 池 + 聊天走 chat 池 |
| 4 | rate_limiter 拦截超限请求 + degraded 后端自动降权 |
| 5 | chat.donglicao.com 可聊天 + 管理后台可登录 |

---

## 风险与回退

| 风险 | 缓解 |
|------|------|
| V3 部署后生产崩溃 | `LIMA_V3=0` 一行回退到 smart_router |
| smart_router 瘦身删多了 | git revert 即可恢复 |
| 双轨分类错误 | 宁可 false positive (归为 coding)，代价低 |
| 限流误杀正常用户 | 先设宽松阈值 (20/min)，观察后收紧 |
