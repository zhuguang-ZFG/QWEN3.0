# LiMa Findings — 关键发现与教训

> 证据数据，非执行指令。详细执行日志见 `progress.md`。
> 生产拓扑与方向性发现见 `STATUS.md` + `docs/PRODUCT_DEFINITION.md`。

## 关键根因分析

### provider_kind 检测缺口 (2026-06-05)
- **根因**: `provider_kind.py` 缺少 `or_*` (OpenRouter) 和 `github_*` (GitHub Models) 前缀检测，导致 21 个后端被误分类为 `openai_compatible`
- **修复**: 在 model-name 检测前添加 backend 名前缀匹配
- **教训**: 新 provider family 接入时需同步更新 provider_kind 检测链

### Nginx /api/ 代理缺失 (2026-06-06)
- **根因**: nginx conf 只有 `/admin/api/` 没有通用 `/api/` 代理，admin API 请求返回 HTML
- **修复**: 添加 `location ^~ /api/` proxy_pass 规则
- **教训**: 路径规则应从宽到窄，通用路径优先于特化路径

### OpenCode 空 body 500 (2026-06-05)
- **根因**: OpenCode 启动探测 POST 空 body → `await request.json()` 异常 → 500
- **修复**: JSON 解析异常 → 400；缺 messages → 400
- **教训**: 客户端探测请求必须 graceful 处理，不应返回 500

### deploy_opencode.py 端口冲突 (2026-06-05)
- **根因**: `fuser -k` + `nohup server.py` 与 `lima-router.service` 争用 8080
- **修复**: 改用 `systemctl restart lima-router.service`
- **教训**: 永远不要混用手动进程管理和 systemd 服务管理

### SSE 错误接线 (2026-06-05)
- **根因**: SSE 流中的 `type: "error"` 事件未结构化解析，无法区分 context_overflow (413) vs api_error (502)
- **修复**: `http_errors.py` 新增 `is_retryable` 参数，`http_stream.py` 接入 `parse_stream_error()`
- **教训**: SSE 错误通道应与 HTTP 错误码同等对待，支持重试决策

### CSRF/Origin 全路径修复 (2026-06-02)
- **根因**: 管理面板按钮请求缺少 CSRF token 和 Origin header 验证
- **修复**: 全路径添加 CSRF token + Origin 检查
- **教训**: 所有写操作端点必须经过统一的 CSRF 中间件

### 大文件渐进拆分 (持续)
- 文件 >300 行需拆分：`backends_registry.py` (70610 bytes)、`admin_ui.py` (72212 bytes)、`http_stream.py` 等
- 权威 backlog: `docs/CODE_QUALITY_IMPROVEMENT_PLAN_2026-05-25.md`

## 认证体系

- API 认证: `Authorization: Bearer {LIMA_API_KEY}`（`access_guard.py`）
- Admin 认证: `LIMA_ADMIN_TOKEN`（`routes/admin_auth.py`）
- `x-api-key` header 不被支持，Anthropic 端点也必须用 Bearer

## 生产拓扑

- VPS: `47.112.162.80`，nginx 80/443 → `lima-router` 127.0.0.1:8080
- 域名: `chat.donglicao.com` (chat), `api.donglicao.com` (open platform)
- VPS 内部端口: 8080 (lima), 3003 (NewAPI), 8091 (voice)
- systemd 管理: `lima-router.service`（唯一权威进程管理方式）

## 编码后端评估发现

| 发现 | 证据 |
|------|------|
| 85 候选端经 code_review 筛选 → 16 通过 | 首个宽筛过滤器 |
| scnet_large_ds_flash, github_gpt4o, github_gpt4o_mini 通过全部 3 个 fixture | 放入 strong/default coding tiers |
| cerebras_gptoss, groq_gptoss, mistral_small 均分 80+ 且延迟 <800ms | 低延迟场景使用 |
| 多数 provider 因 401/429/500/timeout 失败 | 重新测试前修复 keys/rate limits |

## 方向性发现

| ID | 发现 | 行动 |
|----|------|------|
| 路由双轨收敛 | smart_router 生产引用 14→0，全部迁移到 routing_engine | ✅ 完成 |
| 编码体验加厚 | IDE 默认池需 eval 证据驱动（非再堆聊天模型） | 持续 |
| 工具修复管线 | text_tool_extractor + tool_repair_pipeline 覆盖弱模型 | ✅ MVP |
| 上下文注入 trace | Admin 可查看注入历史（无密钥/全文） | ✅ |
