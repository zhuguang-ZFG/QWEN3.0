# LiMa 工作日志 — 2025-05-21

## 概览

本次会话聚焦**后端扩展与稳定性修复**，新增 34 个后端（从 ~78 扩展到 ~112），修复多个关键服务的连接问题，并建立了 TheOldLLM 的自动 Token 刷新机制。

---

## 一、DuckDuckGo AI 后端修复（5 个模型全通）

### 问题
- `ddg_mistral`: 400 Bad Request（模型 ID 过期）
- `ddg_claude_haiku`: 400 Bad Request（缺少 reasoningEffort 字段）
- `ddg_o3_mini`: 400 Bad Request（同上）

### 根因与修复
| 后端 | 根因 | 修复 |
|------|------|------|
| ddg_mistral | DDG 把模型 ID 从 `mistralai/Mistral-Small-24B-Instruct-2501` 改为 `mistral-small-2603` | 更新模型 ID |
| ddg_claude_haiku | DDG 分类为 "reasoning" 模型，请求体必须含 `reasoningEffort` | duckai 代理加 `"reasoningEffort": "none"` |
| ddg_o3_mini | 同上，模型 ID 也从 `o3-mini` 改为 `gpt-5-mini` | duckai 代理加 `"reasoningEffort": "minimal"` |

### 技术细节
- 从 DDG 前端 JS (`entry.duckai.ea16da1b652e759bd056.js`) 逆向发现 `reasoningEffort` 字段要求
- 修改 duckai 代理的 `chat()` 和 `chatStream()` 两个方法
- x-fe-version 保持旧版 `serp_20250401_100419_ET-19d438eb199b2bf7c300`（新版被反机器人拦截）

---

## 二、StockAI 后端扩展（+2 模型）

从 `stock.zhuguang.ccwu.cc` 的 `/v1/models` 发现 2 个未配置模型，测试通过后加入：

| 后端名 | 模型 ID | 延迟 |
|--------|---------|------|
| stock_news | stockai/news | 1.5s |
| stock_mistral | mistral/mistral-small | 3.7s |

同时补全了所有 StockAI 后端的能力矩阵标注。

---

## 三、TheOldLLM 扩展至 12 个模型（+10 模型）

### 问题链
1. Worker MODEL_MAP 错误 — 映射了不存在的 Claude/Gemini/DeepSeek 模型
2. Worker 部署失败 — zone route 缺失，代码上传成功但不生效
3. Token 过期 — 上游返回 403，所有模型不可用
4. Token 刷新脚本不工作 — 无代理无法访问外网 + secret 名称不匹配

### 修复
| 步骤 | 操作 |
|------|------|
| 1 | 重写 MODEL_MAP：移除 Claude/Gemini/DeepSeek，加入正确的 GPT 系列映射 |
| 2 | 通过 CF API 补回 zone route (`llm.zhuguang.ccwu.cc/*` → `lima-oldllm`) |
| 3 | 修复刷新脚本：加 proxy + 修正 secret 名 `TENANT_TOKEN` → `REQUEST_TOKEN` |
| 4 | Worker 加入 403 自动刷新重试机制（调本地 Playwright 端点） |

### 最终可用模型（全部验证 200）
```
gpt-5.4, gpt-5.3, gpt-5.2, gpt-5.1, gpt-5, gpt-5-mini,
gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, gpt-4, o1, o4-mini
```

### Token 自动刷新架构
```
请求 → Worker → 上游(theoldllm.vercel.app)
                    ↓ 403?
              调用 refresh 端点(本地 Playwright via CF tunnel)
                    ↓ 新 token
              更新 global + 重试 → 成功返回
```

---

## 四、新增后端组（今日新增总计）

### Cloudflare Workers AI（ai.zhuguang.ccwu.cc）— 4 个 ✅
| 后端 | 模型 | 延迟 |
|------|------|------|
| cfai_llama70b | llama-3.3-70b | 2.3s |
| cfai_llama4 | llama-4-scout | 3.3s |
| cfai_qwen_coder | qwen2.5-coder-32b | 1.1s |
| cfai_deepseek_r1 | deepseek-r1-32b | 1.3s |

### 本地 Ollama 新增 — 2 个
| 后端 | 模型 |
|------|------|
| local_qwen3 | qwen3:8b |
| local_phi4 | phi4:14b |

### PollinationsAI（直连，去掉 g4f 中间层）— 4 个 ✅
| 后端 | 模型 |
|------|------|
| pollinations_openai | openai |
| pollinations_openai_large | openai-large |
| pollinations_deepseek | deepseek |
| pollinations_qwen_coder | qwen-coder |

---

## 五、g4f/PollinationsAI 稳定性分析

### 发现
- g4f 库自身限制：**5 次/分钟**（付费可解除）
- PollinationsAI 直连 API：限速更宽松（~10-15次/分钟）但仍有限制
- 限速是 g4f 库加的，不是 PollinationsAI 本身

### 决策
- 去掉 g4f 中间层，直接调 PollinationsAI API
- PollinationsAI 定位为补充源（非主力）
- 路由引擎现有 cooldown 机制已能处理 429 自动降级

---

## 六、健康探针模块（已创建，待集成）

创建 `health_probe.py`：
- 后台线程每 5 分钟 probe 不稳定后端
- 失败 → `record_failure()` 进入 cooldown
- 恢复 → `record_success()` 自动重新启用
- 与现有 `probe_loop.py` 互补（probe_loop 只探 dead/suspicious，health_probe 主动探不稳定源）

---

## 七、文件变更汇总

| 文件 | 变更 |
|------|------|
| `backends.py` | 新增 34 个后端定义，g4f→PollinationsAI 直连 |
| `capability_matrix.py` | 新增 StockAI(9) + TheOldLLM(12) 能力评分 |
| `health_probe.py` | 新建：主动健康探针模块 |
| `D:\duckai\src\duckai.ts` | 修复 reasoningEffort + 模型 ID |
| `D:\ollama_server\lima-oldllm-v2.js` | Worker 重写：MODEL_MAP + 403 自动刷新 |
| `D:\ollama_server\refresh_theoldllm_token.js` | 修复：proxy + secret 名称 |
| `D:\ollama_server\token_refresh_server.js` | 新建：本地刷新 HTTP 端点 |
| `D:\ollama_server\start_refresh_tunnel.js` | 新建：tunnel + 刷新服务启动器 |

---

## 八、当前后端总览

| 供应商 | 后端数 | 状态 |
|--------|--------|------|
| LongCat | 5 | ✅ 主力 |
| DeepSeek | 2 | ✅ |
| NVIDIA | 6 | ✅ |
| OpenRouter | 10 | ✅ |
| Groq | 6 | ✅ |
| Cerebras | 3 | ✅ |
| GitHub Models | 3 | ✅ |
| DuckDuckGo AI | 5 | ✅ 全修复 |
| StockAI | 9 | ✅ |
| TheOldLLM | 12 | ✅ 全修复 |
| CF Workers AI | 4 | ✅ |
| PollinationsAI | 4 | ✅ 直连 |
| 本地 Ollama | 7 | ✅ |
| lza6 Workers | 5 | ✅ |
| 其他 | ~30+ | ✅ |

**总计：~112 个后端**
