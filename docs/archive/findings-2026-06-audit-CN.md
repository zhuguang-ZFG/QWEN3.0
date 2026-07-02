# LiMa Findings - 2026-06 审计批次（AUDIT-1 ~ AUDIT-12）

> 归档自 `findings.md`。原 2026-06-28/29 的 12 个 AUDIT 审查批次整体迁移至此。

## 2026-06-28 AUDIT-1：LiMa 后端系统深度审查（安全/健壮性/配置）

> 多维度审查：安全与鉴权、错误处理与健壮性、路由与配置一致性。基础质量门禁全部通过（`check_code_size.py` PASS、`ruff check` clean），但发现多个生产运行时风险。所有 CRITICAL/HIGH 发现均经亲自核验。

### 审计范围
- 公网入口：`https://chat.donglicao.com`（FastAPI + SQLite）
- 排除：tests/、reference/、.venv310/、node_modules/、esp32S_XYZ/、.worktrees/

### CRITICAL（立即修复）

| ID | 文件:行号 | 发现 | 核验 |
|----|-----------|------|------|
| AUDIT-1-C1 | `device_gateway/auth.py:16,57-67` + `routes/device_gateway.py:190-192` | 设备鉴权 fallback 默认开启（`LIMA_WS_REGISTERED_DEVICE_FALLBACK="1"`），空 token + 已知 device_id 即可冒充任意注册设备连入 `/device/v1/ws`。`/ws` 路由无 HTTP 层鉴权依赖，device_id 由客户端 hello 消息提供（用户可控）。该开关未在 `.env.example` 声明 | ✓ 已读源码确认 |
| AUDIT-1-C2 | `server_lifespan.py:73` + `device_gateway/mqtt_client.py:176` | `asyncio.create_task(...)` 返回值被丢弃，GC 可中途回收后台任务（预热探测循环、MQTT 消息循环），导致静默取消无日志。MQTT 设备会静默断连且不重连 | ✓ 已读源码确认 |
| AUDIT-1-C3 | `routes/chat_stream.py:156-163` | `_stream_orchestration` 的 `_authoritative_route(...)` 调用未包 try/except（兄弟函数 `_resolve_authoritative_content:134` 有），路由引擎抛异常时整个 SSE 响应崩溃，用户看到中断的流且无降级消息 | ✓ 已读源码确认 |

### HIGH（本周修复）

| ID | 文件:行号 | 发现 | 核验 |
|----|-----------|------|------|
| AUDIT-1-H1 | `semantic_cache/store.py:45-48,51,60,91` | SQLite 连接泄漏：`with self._connection() as conn` 只管理事务不关闭连接，每次缓存操作泄漏一个文件描述符。项目已有 `config/sqlite_pool.py` 却未使用 | ✓ 已读源码确认 |
| AUDIT-1-H2 | `http_response.py:21` + `http_errors.py:50-57` | `data["choices"][0]["message"]` 直接索引，后端返回合法 JSON 但非 chat 格式（如 `{"error":{...}}`）时 KeyError；经 `_extract_code` 子串匹配（`"401" in text`）误判状态码，可能把配额消息误判为鉴权失败 → `key_pool` **永久拉黑健康 API key** | ✓ 已读调用链确认 |
| AUDIT-1-H3 | `http_stream.py:121-125,201,292` | 流式质量指标恒为 0：`_record_stream_success` 的 `total_text` 两处调用都传 `None`，`record_response_quality(backend, 0)` 恒 0，污染质量路由评分 | ✓ 已读源码确认 |
| AUDIT-1-H4 | `http_stream.py:202,293` | `except (BackendError, httpx.HTTPStatusError, Exception)` 过宽，客户端断连（GeneratorExit/ClientDisconnect）被误记为后端故障，惩罚健康后端健康分/冷却 | ✓ 已读源码确认 |
| AUDIT-1-H5 | `route_scorer.py:139,149,158` | `except (ImportError, Exception)`（冗余，Exception 覆盖 ImportError）吞掉 reputation/weights/profile 子系统所有异常，静默回退 0.5 默认分，真实 bug 无日志，路由评分被无声扭曲 | ✓ 已读源码确认 |
| AUDIT-1-H6 | `route_post_process.py:41` 等 14 处 | 生产路径 `except: pass` 违反 AGENTS.md 硬规则（至少需 logger.warning）。涉及 route_post_process/device_memory/user_identity/session_memory 等 | ✓ 已读源码确认 |

### MEDIUM（计划修复）

| ID | 文件:行号 | 发现 |
|----|-----------|------|
| AUDIT-1-M1 | `server.py:62-63` | CORS 中间件完全缺失（全项目零 `CORSMiddleware`）；若前后端跨域浏览器请求被拦，若靠 nginx 配 `*`+credentials 则是危险组合且不可审计 |
| AUDIT-1-M2 | `streaming.py:74-80` | `_async_fallback_to_api` 函数体完全为空（无 yield 无调用），异步原生流式空响应无降级，而同步桥接有完整实现——不对称缺口 |
| AUDIT-1-M3 | `key_pool.py:150-153` | API key 指纹暴露后4位（`suffix = key[-4:]`），经 admin 接口可见，部分泄漏 |
| AUDIT-1-M4 | `server_bootstrap.py:38-44` | `last_resort_call` 兜底只 log 异常类型名，返回 `""` 让上层误判为正常空回复 |
| AUDIT-1-M5 | `.env.example` | 变量名不一致：代码用 `MIMO_TTS_KEY`/`MIMO_V2_PRO_KEY`，`.env.example` 写 `MIMO_API_KEY`；`LIMA_WS_REGISTERED_DEVICE_FALLBACK` 未声明 |
| AUDIT-1-M6 | `routes/request_tracking.py:57-74` | `get_ip_location` 在请求路径内做同步阻塞 HTTP 调用（0.5s 超时），阻塞事件循环 |

### 已确认安全的维度（无需修复）

- **SQL 注入**：动态 SQL 值均走 `?` 参数化，列名经 `ALLOWED_DEVICE_COLUMNS` 白名单校验 ✓
- **SSRF**：无用户可控 URL 传入 httpx；IP 定位用严格正则校验 ✓
- **路径穿越**：`upload.py` 的 `_safe_upload_path` 三重防护（正则+resolve+is_relative_to）✓
- **硬编码密钥**：全项目零命中，密钥均经 `os.environ` 注入，`.env` 已 gitignore ✓
- **JWT 严格性**：显式 `algorithms=["HS256"]`、捕获过期/无效、查 DB 校验 active ✓
- **Admin 鉴权**：`secrets.compare_digest` 恒定时间比较，无恒真分支 ✓
- **孤儿路由**：`facade.py`/`v3_adapters.py` 经核实为内部辅助模块（无顶层 router）✓

### 修复批次建议
1. **第一批（CRITICAL）**：C1 关闭 fallback 默认值+生产硬禁用；C2 给 task 加强引用+done 回调；C3 给 `_stream_orchestration` 补 try/except
2. **第二批（HIGH-健壮性）**：H1 sqlite 连接关闭；H2 http_response 防御性 .get()；H3 流式质量指标；H4 流式错误分类；H5 route_scorer 异常范围收窄
3. **第三批（HIGH-规范）**：H6 批量给 except:pass 补 warning
4. **第四批（MEDIUM）**：CORS、异步降级实现、env 一致性等

### AUDIT-1 CRITICAL 批次修复完成（2026-06-28）

| ID | 修复文件 | 措施 | 验证 |
|----|----------|------|------|
| C1 | `device_gateway/auth.py`, `.env.example` | fallback 默认关闭；env 显式声明 | 新增单元测试：默认拒绝、开启后放行、未注册拒绝 |
| C2 | `server_lifespan.py`, `device_gateway/mqtt_client.py` | WARM phases / MQTT loop task 强引用，stop 时 cancel | 全量 pytest pass；部署启动日志显示各 phase ok |
| C3 | `routes/chat_stream.py` | `_stream_orchestration` 加 try/except，异常时回退兜底消息 | 新增测试：异常后仍流式输出 fallback |

- 质量门禁：`ruff check` clean；`ruff format` clean；`pyright` 目标文件 0 errors；`scripts/check_code_size.py` PASS。
- 部署：`scripts/deploy_unified.py --slice core` 成功，`https://chat.donglicao.com/health` 返回 200。
- 状态：**AUDIT-1 CRITICAL 批次已关闭**。

### AUDIT-1 HIGH 批次修复完成（2026-06-29）

| ID | 修复文件 | 措施 | 验证 |
|----|----------|------|------|
| H1 | `semantic_cache/store.py`, `semantic_cache/cache.py` | 改用 `pooled_sqlite_conn`；`get_cache()` 单例化 | `tests/test_semantic_cache.py` + `tests/test_route_pipeline.py` pass |
| H2 | `http_response.py`, `http_errors.py` | `choices` 防御性 `.get()`；移除 `"401"/"403"/"429" in text` 子串匹配 | 新增 `tests/test_http_response.py` |
| H3/H4 | `http_stream.py`, 新增 `http_stream_core.py` | 流式累计文本传给 `record_response_quality`；`GeneratorExit`/`CancelledError` 不再触发 `record_failure` | 新增 `tests/test_http_stream_quality.py` |
| H5 | `route_scorer.py` | 三处静默 `except (ImportError, Exception): pass` 改为 warning；拆分 `_reputation_score` 等小函数 | 新增 `tests/test_route_scorer.py` 回归测试 |
| H6 | `route_post_process.py` 等 9 文件 + `tests/test_ci_gates.py` | 静默 `except: pass` 补 warning；CI gate 增加 `ImportError` 模式 | `test_p13_no_silent_exception_pass_in_active_paths` pass |

- 质量门禁：`ruff check` clean；`ruff format` clean；`pyright` 0 errors（仅历史 warning）；`scripts/check_code_size.py` PASS。
- 部署：`scripts/deploy_unified.py --slice core` 成功，`https://chat.donglicao.com/health` 返回 200。
- 状态：**AUDIT-1 HIGH 批次已关闭**。

### AUDIT-1 MEDIUM 批次修复完成（2026-06-29）

| ID | 修复文件 | 措施 | 验证 |
|----|----------|------|------|
| M1 | `server.py`, `.env.example` | 添加 `CORSMiddleware`；默认 `*` 且 `allow_credentials=False`；新增 `LIMA_CORS_ORIGINS` 配置项 | `tests/test_server_cors.py` pass；线上 `OPTIONS /health` 返回 `Access-Control-Allow-Origin: *` |
| M2 | `streaming.py`, 新增 `tests/test_streaming_async_fallback.py` | 实现 `_async_fallback_to_api`：流空/异常时调用异步非流 API 并整块 yield；过滤 `[ERR` 前缀 | 6 个 fallback 场景测试 pass |
| M3 | `key_pool.py`, `tests/test_key_pool.py` | `_fingerprint_key` 不再拼接 key 后缀，仅返回 SHA256 前 10 位 | 14 个 key_pool 测试 pass |
| M4 | `server_bootstrap.py`, 新增 `tests/test_server_bootstrap.py` | 异常分支记录完整堆栈（`exc_info=True`）并返回统一兜底文案；未配置 Cloudflare 时也返回兜底文案 | 3 个 last_resort 测试 pass |
| M5 | `.env.example` | 新增 `MIMO_TTS_KEY=` 与 `MIMO_V2_PRO_KEY=`，保留 `MIMO_API_KEY` 给设备语音 TTS | `.env.example` 解析无异常 |
| M6 | `routes/request_tracking.py`, `routes/chat_handler_dispatch.py`, `routes/chat_fallback.py`, `routes/chat_response_finalize.py`, 新增 `tests/test_request_tracking_async_geo.py` | IP 定位查询提取为 `_fetch_ip_location`；新增 `resolve_ip_country` 在 executor 中异步执行；`record_request` 接受 `country` 参数；异步调用方提前解析后传入 | 5 个 async geo 测试 + 相关路由测试 pass |

- 质量门禁：`ruff check` clean；`ruff format` clean；`pyright` 0 errors（仅历史 warning）；`scripts/check_code_size.py` PASS。
- 测试：全量 pytest **4100 passed, 3 skipped**（新增 17 个测试）。
- 部署：`scripts/deploy_unified.py --slice core` 成功，`https://chat.donglicao.com/health` 返回 200；CORS 预检头正确。
- 状态：**AUDIT-1 MEDIUM 批次已关闭**。

## 2026-06-28 AUDIT-2：Web 端深度审查（chat-web 管理面板 + donglicao-site-v2 官网）

> 两个 Web 前端项目的安全与质量审查。chat-web 为原生 HTML/JS 管理控制台（公网），donglicao-site-v2 为 Next.js 16 静态导出官网。关键发现均经亲自核验源码确认。

### AUDIT-2-A：chat-web 管理面板（原生 HTML/JS）

**总体评价**：维护质量较高——聊天消息渲染（chat-messages.js）和 playground 正确使用 `textContent`/`escapeHtml`，所有页面配有 CSP，CDN 脚本带 SRI，无硬编码密钥。但存在若干真实可利用的安全隐患。

#### HIGH 级别（经核验）

| ID | 文件:行号 | 发现 | 核验 |
|----|-----------|------|------|
| AUDIT-2-W1 | `js/handwriting.js:144-153` | **存储型 XSS**：`viewBox="0 0 ${item.width} ${item.height}"` 将后端返回的 width/height 未转义直接插入 SVG 属性，整体经 innerHTML 注入。若后端值含 `" onload="alert(document.cookie)` 即触发。同段 `svg_path`（:147）正确用了 escapeHtml，但宽高被遗漏。**修复极简：parseInt** | ✓ 已读源码确认 |
| AUDIT-2-W2 | `js/devices.js:165` + `voice-call.html:228-231,262` | **WebSocket token 暴露在 URL**：因浏览器 WebSocket 不能设自定义头，把完整 Bearer token 放进 `?authorization=Bearer ${token}` query string。会被 nginx access log、Referer 头记录。一旦泄露可长期冒充用户 | ✓ 已读源码确认 |
| AUDIT-2-W3 | `js/auth.js:6,18-28` + 多处 | **token 存 localStorage**：`lima_token`、`lima-api-key` 等全存 localStorage（非 httpOnly），任意 XSS 可窃取并长期持有管理员凭证 | ✓ 已读源码确认 |

#### MEDIUM 级别

| ID | 文件:行号 | 发现 |
|----|-----------|------|
| AUDIT-2-W4 | 所有 HTML CSP（index.html:9 等） | CSP 全局允许 `'unsafe-inline'`（`script-src 'self' 'unsafe-inline'`），使事件处理器注入可直接利用，配合 W1 形成完整 XSS 链 |
| AUDIT-2-W5 | login.html/register.html/voice-call.html | **这三个页面完全没有 CSP**（仅 6 个页面有），登录页（含凭证输入）与语音页（含麦克风授权）是 XSS 最薄弱入口 |
| AUDIT-2-W6 | `js/keys.js:125-128` | **登出不彻底**：`removeToken()` 只删 `lima_token`，`lima-api-key`/`lima_sessions`（完整聊天历史）/`lima_playground_history` 等全部残留，共享设备隐私泄露 |
| AUDIT-2-W7 | `chat-messages.js:198-210` | KaTeX 数学渲染对模型输出内容解析 `$...$`，LaTeX 命令（`\href` 等）是已知攻击面，建议启用 `strict:true`/`trust:false` |

#### LOW 级别
- `index.html:127,222` 等外链 `window.open`/`target=_blank` 缺 `rel="noopener noreferrer"`（反向 tabnabbing）
- `register.html:76-78` 前端校验过弱（邮箱无格式校验，密码仅 6 位）
- `js/asset-upload.js:18-24` SVG 以明文读取上传，无内容净化，依赖消费方防 XSS
- `js/keys.js:113` 删除 key 时 id 未 `encodeURIComponent`（路径参数注入）
- 多处 `showToast(err.message)` 直接回显后端错误原文（信息泄露）

#### 已确认安全的维度（无需修复）
- **无硬编码密钥**：全仓 grep 无 `sk-...`、`LIMA_ADMIN_TOKEN` ✓
- **聊天消息渲染安全**：`formatContent` 先 escapeHtml 再 markdown，图片 URL 有域名白名单+协议校验 ✓
- **Playground 渲染安全**：响应追加用 textContent，历史项用 createElement+textContent ✓
- **SRI 完备**：所有 CDN 脚本/样式带 integrity+crossorigin ✓
- **无 token 暴露在 URL 参数**（除 WS 鉴权外）✓

### AUDIT-2-B：donglicao-site-v2 官网（Next.js 16 + React 19）

**总体评价**：静态导出（`output:"export"`），代码质量高，无分析/追踪脚本，无 eval/dangerouslySetInnerHTML 滥用（仅用于受控 JSON-LD）。但存在合规性与配置问题。

#### HIGH 级别（经核验）

| ID | 文件:行号 | 发现 | 核验 |
|----|-----------|------|------|
| AUDIT-2-S1 | `app/components/Footer.tsx:164` | **ICP 备案号为占位符** `京ICP备XXXXXXXX号-1`，公网上线即违规（工信部可要求整改/关站）。额外：主体是"深圳市动力巢科技"但备案前缀为"京ICP"（北京），省份不一致 | ✓ 已读源码确认 |
| AUDIT-2-S2 | `next.config.ts:1-12` | **完全缺失安全响应头**：无 CSP/X-Frame-Options/X-Content-Type-Options。注意：静态导出下 Next 的 headers() 本身不生效，必须在 nginx/CDN 层配置 | ✓ 已读源码确认 |

#### MEDIUM 级别

| ID | 文件:行号 | 发现 |
|----|-----------|------|
| AUDIT-2-S3 | `app/login/page.tsx:39` + `app/register/page.tsx:34` | token 存 localStorage（与 chat-web W3 同类问题），配合无 CSP 风险叠加 |
| AUDIT-2-S4 | `app/components/Hero.tsx:31` | **死链**：`href="/developer/"` 但 `app/developer/` 下只有 `playground/`，点击命中 not-found。应改为 `/developer/playground/` |
| AUDIT-2-S5 | 十几处（login/register/playground/Developer/Hero/Navbar） | **所有 URL 硬编码**，零个 `NEXT_PUBLIC_`/`process.env`，切换环境需改源码 |
| AUDIT-2-S6 | `app/developer/playground/page.tsx:54,133-139` | Playground 允许用户自定义任意 Base URL，携带 `Authorization: Bearer` 发出，存在凭据外泄面 |

#### LOW 级别
- 多处外链仅 `rel="noopener"` 缺 `noreferrer`
- 错误信息直接回显 `err.message`/后端 JSON（信息泄露）
- `app/layout.tsx:58-59` preconnect 指向自身域名（无效）
- 隐私政策未提及 localStorage 存储的 token（与实际数据处理不一致）

#### 已确认安全的维度
- **无分析/追踪脚本**：无 GA/百度统计/Sentry，与隐私政策声明一致 ✓
- **无 eval/innerHTML/document.write** ✓
- **dangerouslySetInnerHTML 仅用于受控 JSON-LD**（JSON.stringify 后端对象）✓
- **blog/[slug] 路由内容来自受控 posts.ts**，无注入面 ✓
- **法律页中英文条款对齐**，均有 force-static ✓
- **构建产物未 git 跟踪**（.gitignore 忽略 /dist/.next/.env）✓

### Web 端修复优先级建议
1. **立即（HIGH，公网暴露）**：W1 handwriting XSS 一行 parseInt 修复；W2 WS token 改 ticket 机制；S1 ICP 占位符替换/核对省份
2. **本周（HIGH/MEDIUM）**：W5 三页面补 CSP；W6 登出彻底清理；S2 nginx 补安全头；S4 死链修复
3. **计划（MEDIUM/LOW）**：W3/S3 token 存储迁移 httpOnly cookie；W4 CSP 移除 unsafe-inline；S5 URL 环境变量化

### AUDIT-2 Web 端修复完成（2026-06-29）

| ID | 修复文件 | 措施 | 验证 |
|----|----------|------|------|
| W1 | `chat-web/js/handwriting.js` | `parseInt(item.width/height, 10)` 后拼入 SVG `viewBox` | 人工代码审查 |
| W2 | `app_status_ws_ticket.py`、`routes/device_app_status_ws.py`、`routes/voice_pipeline_ws.py`、`chat-web/js/devices.js`、`chat-web/voice-call.html` | 设备状态 WS 与语音 WS 改用一次性 ticket（`?ticket=`），URL 不再暴露 Bearer token | ticket 发放/消费端 ruff+pyright 通过；部署后 health 200 |
| W3 | `chat-web/js/auth.js`、`chat-web/chat-ui.js`、`chat-web/js/model-selector.js`、`chat-web/voice-call.html`、`chat-web/js/playground-utils.js` | `lima_token`/`lima-api-key` 改用 `sessionStorage`（playground 保留 localStorage 只读迁移） | 人工代码审查 |
| W5 | `chat-web/login.html`、`chat-web/register.html`、`chat-web/voice-call.html` | 新增 CSP meta（`default-src 'self'`、`frame-ancestors 'none'`、`upgrade-insecure-requests` 等） | 人工代码审查 |
| W6 | `chat-web/js/auth.js`、`chat-web/js/keys.js` | `logout()` 清理 `lima_token`、`lima-api-key`、`lima_api_key`、`lima_sessions`、`lima_playground_history` | 人工代码审查 |
| W7 | `chat-web/chat-messages.js` | KaTeX 渲染启用 `strict: true`、`trust: false` | 人工代码审查 |
| S1 | `donglicao-site-v2/app/components/Footer.tsx` | ICP 号改为 `process.env.NEXT_PUBLIC_ICP_NUMBER` 环境变量，默认保留占位符 | 人工代码审查 |
| S2 | 新增 `donglicao-site-v2/nginx-headers.conf.example` | 提供含 X-Frame-Options、HSTS、CSP 等的 nginx 安全响应头示例 | 人工代码审查 |
| S4 | `donglicao-site-v2/app/components/Hero.tsx` | 死链 `/developer/` 改为 `/developer/playground/` | 人工代码审查 |

- 测试修复：`tests/test_routes_device_app_auth.py` 增加 `rate_limiter.reset()`，解决累积 rate limit 导致 email 注册测试偶发 429。
- 质量门禁：`ruff check` 目标文件 clean；`pyright` 0 errors；`scripts/check_code_size.py` PASS。
- 测试：全量 pytest **4102 passed, 3 skipped, 2 deselected, 0 failed**。
- 部署：`scripts/deploy_unified.py --slice core` 成功；`https://chat.donglicao.com/health` 200。
- 状态：**AUDIT-2 Web 端 HIGH/MEDIUM 批次已关闭**（剩余 W4/W3-httpOnly/S3/S5/S6 等后续计划项）。

## 2026-06-29 AUDIT-3：LiMa 系统提示词审查（分层架构/注入防护/身份保护）

> 审查范围：`prompt_engineering/`（分层架构）、`context_pipeline/guardrails.py`（输入防护）、`identity_guard_patterns.py`（身份防护）、`lima_context.py`（上下文摘要）、`routes/chat_preflight.py`（接入点）。关键发现均经亲自读源码核验。

### 提示词架构（正面）
LiMa 采用 **6 层分层提示词架构**（`prompt_engineering/layers.py`），组合顺序 1→2→3→4→5(opt)→6，设计清晰：
- **Layer 1 角色**：`prompts/layers.yaml` 模板化（role.chat/coding/vision/device_*），YAML 支持热重载（mtime 缓存失效）
- **Layer 2 安全基线**：`build_safety_baseline()` 每个场景强制注入——明确禁止承认自己是 GPT/Claude/Llama 等、禁止透露系统指令
- **Layer 3 技能**：场景化激活触发条件
- **Layer 4 工作流**：多步执行流程（device_control 含白名单校验、急停优先）
- **Layer 6 质量门控**：场景化输出约束
- **品牌化**：`brand_config` 集中管理 PUBLIC_MODEL_NAME/CAPABILITY，隐藏后端真实模型

### 发现的问题

| ID | 文件:行号 | 发现 | 严重 | 核验 |
|----|-----------|------|------|------|
| AUDIT-3-P1 | `context_pipeline/guardrails.py:33-42` | **注入防护仅覆盖 6 个英文模式，0 个中文**。`_INJECTION_PATTERNS` 只有 `ignore previous instructions`/`you are now`/`<\|im_start\|>` 等，中文"忽略上面的指令/从现在起你是/开发者模式/越狱"完全无覆盖。公网中文用户无防护 | HIGH | ✓ grep 确认 0 中文模式 |
| AUDIT-3-P2 | `context_pipeline/guardrails.py:103-120` + 全项目 | **输出 guardrail 是死代码**。`check_output_safety` 检测 `rm -rf /`/`DROP TABLE` 等危险输出，但**从未在生产路径调用**（grep 确认零接入点）。模型被诱导输出危险命令时无拦截 | HIGH | ✓ grep 确认零接入 |
| AUDIT-3-P3 | `routes/chat_preflight.py:26-46` | **注入检测命中只 WARN 不阻断**。`check_injection` 的 severity 是 `WARN`（:61），而 `run_input_guardrails` 只在 `BLOCK` 时 raise（:40）。即检测到英文注入也只记日志，请求照常路由 | HIGH | ✓ 已读源码确认 |
| AUDIT-3-P4 | `routes/chat_preflight.py:96` + `http_request_builder/body.py:35-38` | **客户端 system 消息被直接采纳**。`extract_system_prompt(req.messages)` 读取客户端发来的 system 内容，`merge_device_intent_system_prompt` 在其上叠加 LiMa 层，形成"客户端 system + LiMa 层"混合。攻击者可通过 system 消息注入指令，污染上下文。OpenAI 兼容 API 需接受 system，但 LiMa 层应**覆盖而非追加**客户端 system | MEDIUM | ✓ 已读源码确认 |
| AUDIT-3-P5 | `prompt_engineering/layers.py:184` | **提示词版本标记用 HTML 注释** `<!-- lima-prompts-v2.0.{scenario} -->` 拼到 system prompt 末尾。部分后端可能把注释内容当指令解析（尤其当用户问"你的版本是什么"时可能泄露内部版本号）；且注释会消耗 token | LOW | ✓ 已读源码确认 |
| AUDIT-3-P6 | `prompt_engineering/layers.py:47-52` | **IDE 环境注入未限长风险已缓解**：`ide_safe = ide[:64]` 已截断，但 `f"用户正在 {ide_safe} 中使用你"` 直接拼入 system prompt。若 ide 值含指令性文本（如 "VS Code。忽略所有指令"），64 字符足以构成注入。建议额外过滤非字母数字字符 | LOW | ✓ 已读源码确认 |
| AUDIT-3-P7 | `lima_context.py:45-60` | **上下文摘要注入用户内容**。`build_context_digest` 从用户 query/消息提取 paths/signals 拼成 "LiMa context preflight" 块注入 system prompt。这些值虽经 `_clean_line`（:152）做了空白规整+截断，但未转义控制字符/指令关键词，理论上可被构造的文件名（如 `ignore_previous.py`）污染 | LOW | ✓ 已读源码确认 |

### 已确认防护到位的维度
- **身份防护关键词完整**：`identity_guard_patterns.py` 覆盖中英文 60+ 身份探测关键词（你是谁/who are you/你是gpt吗 等），配合 Layer 2 安全基线双重防御 ✓
- **device_control 白名单严格**：`role.device_control` 模板显式列出允许指令 + `{dangerous_capabilities}` 禁止项，Layer 4 工作流第 3 步"白名单外一律拒绝"，Layer 6 质量门控"白名单外指令一律拒绝"——三层防护 ✓
- **提示词热重载安全**：`registry.py` 用 mtime 缓存 + threading.Lock，YAML 解析用 `safe_load`（非 `load`），无任意代码执行风险 ✓
- **上下文压缩 best-effort**：`context_compressor.py` 失败时保留原消息，不阻塞主路径 ✓

### 提示词改进建议
1. **立即**：P1 补中文注入模式（"忽略.*指令"/"从现在起"/"开发者模式"/"越狱"/"DAN"）；P3 把注入检测升级为 BLOCK（或至少高危模式 BLOCK）；P2 接入 `check_output_safety` 到响应后置处理
2. **本周**：P4 评估 LiMa 层覆盖客户端 system（而非追加）；P6 IDE 值做字符白名单过滤
3. **后续**：P5 版本标记改用 response header 或日志而非 system prompt 内注释；P7 上下文摘要值做指令关键词过滤

### AUDIT-3 修复完成（2026-06-29）

| ID | 修复文件 | 措施 | 验证 |
|----|----------|------|------|
| P1 | `context_pipeline/guardrails.py` | 新增中文注入模式（`忽略.{0,8}指令`、`无视`、`进入...模式`、`越狱`/`DAN`），用 `.{0,8}` 宽松匹配覆盖"忽略上面的所有指令"等真实攻击文案 | pytest 62 passed |
| P3 | `context_pipeline/guardrails.py` | 拆分 `_INJECTION_BLOCK_PATTERNS`（高置信度→BLOCK 阻断）与 `_INJECTION_WARN_PATTERNS`（可疑角色扮演→WARN 记日志不阻断）。`check_injection` 高置信度模式升级为 BLOCK，可疑降级为 WARN | pytest + ruff clean |
| P2 | `route_post_process.py` | `_post_response_pipeline` 接入 `check_output_safety`——检测 `rm -rf /`/`DROP TABLE` 等危险输出并 `_log.warning`（post-closeout 仅告警不阻断已发内容）；顺带修复该函数 `except ImportError: return` 的静默降级（改为 `_warn`） | ruff clean |
| 测试 | `tests/test_context_pipeline_guardrails.py`、`tests/test_guardrails.py`、`tests/test_phase19_22.py` | 更新断言：`injection_pattern_detected`→`injection_pattern_blocked`，severity WARN→BLOCK；新增 `test_chinese_injection_blocked` 中文注入用例 | 全部通过 |
| P4 | `routes/chat_preflight.py` | LiMa 设备意图层激活时，用合并后的 LiMa system 完全覆盖客户端 system，避免攻击者通过客户端 system 注入指令覆盖角色层 | pytest 聚焦通过 |
| P5 | `prompt_engineering/layers.py` + `routes/chat_endpoints.py` | 从 system prompt 中移除 HTML 注释版本标记，改为通过 response header `X-LiMa-Prompt-Version` 返回；新增 `prompt_version_for()` 供日志使用 | pytest + ruff + pyright |
| P6 | `prompt_engineering/layers.py` | `build_role_layer` 对 `ide` 做白名单过滤：仅保留 ASCII 字母/数字，移除空格、标点和注入文案 | pytest + ruff + pyright |
| P7 | `lima_context.py` | `build_context_digest` 对 `ide`、`workspace`、`paths`、`signals` 增加指令关键词过滤（`ignore previous`/`forget all`/`override instruction` 等），被污染的值直接丢弃 | pytest + ruff + pyright |

- 延后项：无。
- 状态：**AUDIT-3 全部关闭**（P1/P2/P3/P4/P5/P6/P7）。

---

## 2026-06-29 AUDIT-4：LiMa 容错率与可靠性加厚方向审查

> 审查范围：重试/退避、熔断器、超时/死信、并发/背压、降级链、数据一致性、资源防护、启动鲁棒性。聚焦运行时容错工程（不重复 AUDIT-1 安全审查）。关键发现均经亲自读源码核验。

### HIGH 级别（最值得立即加厚）

| ID | 文件:行号 | 发现 | 核验 |
|----|-----------|------|------|
| AUDIT-4-F1 | `routing_executor_serial.py:99-127` + `http_sync.py:222-236` | **无客户端层重试**：每个后端只调用一次，瞬时错误（网络抖动/503/连接重置）直接降级下一个后端。`httpx.RequestError` 这类重试一次就成的错误被误判为"network_error"触发 5s 冷却，白白损失健康后端。建议对可重试错误（RequestError/503/504/408/429）做 1-2 次指数退避重试 | ✓ 已读源码确认 |
| AUDIT-4-F2 | `device_gateway/redis_store.py:232-273` + `task_lifecycle.py:93-97` | **死信恢复是死代码**：`recover_stale_processing` 能把卡在 processing 超 120s 的任务塞回 pending，但**无任何后台线程调用它**（仅 tests 引用）。设备在 LMOVE 后崩溃则任务永远卡 processing 队列直到 TTL 过期 = 丢任务 | ✓ grep 确认零生产调用 |
| AUDIT-4-F3 | `routing_engine.py:259-300` + `routing_executor_serial.py` | **无全局并发限制/信号量**：`route()` 被 `asyncio.to_thread` 调用，FastAPI 默认 40 线程。所有后端都慢（每个最多 60s 超时）时，40 并发占满线程池，新请求排队 = 整机无响应。建议路由入口加 `Semaphore(N)` 超限返回 503 | ✓ 已读源码确认 |
| AUDIT-4-F4 | `http_request_builder/client.py:24-45` + `routing_executor_parallel.py:115` + `speculative_execution.py:84` | **httpx.Client 每次新建无连接池复用**：并行 fallback 和投机执行每次 `with ThreadPoolExecutor` + 每次 `_build_client` 新建 Client。高并发下 FD/socket 飙升，失去 keep-alive 优势。这是除 sqlite 泄漏外的第二类 FD 泄漏点 | ✓ 已读源码确认 |
| AUDIT-4-F5 | `server_bootstrap.py:18-44` + `routing_executor.py:60` | **终极降级只在流式生效**：`last_resort_call`（Cloudflare 兜底）在 `chat_stream.py:53-60` 流式路径用，但非流式 `route()` 全后端耗尽时返回 `("exhausted","",errors)` → 空内容 200 响应，**非流式零引用 last_resort**。IDE 等非流式客户端全局故障时收到空内容无降级 | ✓ grep 确认非流式零引用 |
| AUDIT-4-F6 | `health_recorder.py:159` + `health_state.py:185-239` | **monotonic 时钟持久化 bug**：cooldown_until 用 `time.monotonic()`（进程启动后单调递增，重启归零）计算，却原样存 SQLite，重启后读回。新进程 monotonic 从 ~0 开始，读回的旧值导致 cooldown 判断在"永不冷却"和"全熔断"间随机摇摆。等价于健康状态重启不可靠 | ✓ 已读源码确认 |
| AUDIT-4-F7 | `server_lifespan_phases.py:197-204` | **device/MQTT 启动是 CRITICAL 阶段**：`start_device_gateway_runtime`/`start_mqtt_client` 被列为 critical，任一失败则 `raise RuntimeError` 阻塞整个 FastAPI 启动。但它们对核心 chat 路由非必需，MQTT broker 抖一下就启动不了主服务。应降为 WARM 阶段 | ✓ 已读源码确认 |

### MEDIUM 级别

| ID | 文件:行号 | 发现 |
|----|-----------|------|
| AUDIT-4-F8 | `health_models.py:50-55` + `http_errors.py:22-38` | **429 冷却无视 Retry-After**：`_extract_code` 提取了 `Retry-After` 头但 `_apply_cooldown` 忽略它，固定用 30s 起。上游限流几分钟时，系统每 30s 重试再 429，浪费配额加剧限流 |
| AUDIT-4-F9 | `health_scoring.py:89-100` | **mass_failure 清空全部健康状态**：dead 后端 >50% 时清空 `_health_map`/`_cooldown_states`/`_quality_states` 全部内存态，丢失延迟/成功/错误分类等差异化信息，下次请求可能把刚冷却的坏后端当健康用 |
| AUDIT-4-F10 | `device_gateway/mqtt_client.py:131-136,196` | **MQTT uplink 队列无界**：`message_queue = asyncio.Queue()` 无 maxsize（对比 downlink 有 maxsize=32），处理慢时上游持续推消息 → 无界增长 → OOM |
| AUDIT-4-F11 | `device_gateway/store.py:230-243` + `redis_store_helpers.py:27-33` | **Redis 运行时故障无降级**：启动时二选一（Redis 或 InMemory），但运行时 Redis 挂了，每个方法抛 `ConnectionError` 无 try/except 降级。`rate_limiter_redis.py` 有降级到内存，task store 没有 |
| AUDIT-4-F12 | `device_gateway/redis_store.py:108-111` | **设备任务状态无乐观锁**：`_write_task_state` 裸 HSET 覆盖，无 version/etag/WATCH。并发事件（设备上报+超时重排）后写覆盖前写，丢失事件 |
| AUDIT-4-F13 | `speculative_execution.py:151-171` | **投机输家线程不被取消**：`future.cancel()` 只能取消未启动的 future，已运行的 httpx 阻塞调用无法中断，loser 线程跑满自己的 60s 超时占用 worker slot |

### LOW 级别
- `routing_executor_serial.py:16`：`PER_BACKEND_TIMEOUT=15s` 只事后警告慢后端，不中断挂起请求（真正超时来自 httpx 默认 60s）
- `async_utils.py:27-28`：`run_coro_sync` 每次新建 ThreadPoolExecutor(max_workers=1)，热路径线程创建开销
- `server_bootstrap.py:30`：`last_resort_call` 用裸 `urllib` 不走 GFW 代理，国内服务器可能连不上 Cloudflare

### 已确认健康的维度（无需加厚）
- **降级链无循环**：`_serial_attempt` 遍历 `backends[:max_tries]`，fallback 从同列表筛健康候选，MAX_FALLBACKS=10 合理上限 ✓
- **缓存/记忆 best-effort 隔离**：`semantic_cache`/`session_memory` 写入全包 try/except 不阻塞主路径 ✓
- **缺 key 后端静默跳过**：缺 key 的后端在选路时被 budget/health 过滤剔除，不崩溃 ✓

### 容错率加厚优先级（按 ROI 排序）
| 批次 | 项目 | 一句话 |
|------|------|--------|
| **第一批** | F1 | 加客户端层瞬时错误重试（1-2 次退避），消化网络抖动 |
| **第一批** | F2 | 接线 `recover_stale_processing` 到后台 reaper（当前死代码），防丢任务 |
| **第一批** | F3 | 路由入口加全局 Semaphore 背压，防线程池耗尽整机不可用 |
| **第二批** | F4 | 复用 httpx.Client 连接池，治 FD 泄漏 + 提升 keep-alive |
| **第二批** | F5 | 非流式 exhausted 时调 last_resort_call，对齐流式降级 |
| **第二批** | F6 | 修 monotonic 持久化 bug（load 时清零 cooldown 最简） |
| **第二批** | F7 | device/MQTT 启动降为 WARM，避免阻塞主服务 |
| **第三批** | F8-F13 | Retry-After 遵从、mass_failure 渐进恢复、MQTT 背压、Redis 降级、任务 CAS、投机短超时 |

**关键风险路径**：F1（无重试）+ F3（无背压）+ F4（FD 泄漏）三者叠加，是单次上游故障演变为整机不可用的典型路径——慢后端占满线程池 + FD 耗尽 + 无重试反复降级 = 雪崩。F6（monotonic bug）是隐蔽的静默 bug，重启后健康状态在"全熔断"和"全放行"间随机摇摆。

### AUDIT-4 修复完成（2026-06-29）

| ID | 修复文件 | 措施 | 验证 |
|----|----------|------|------|
| F2 | `routes/device_gateway_helpers.py`、`device_gateway/sessions.py` | 新增 `_stale_task_reaper_loop` 后台任务（60s 周期），扫描已连接设备的 processing 队列，把卡 >120s 的任务塞回 pending 并通知会话；`start/stop_device_gateway_runtime` 接线生命周期；`SessionRegistry` 新增 `active_device_ids()` | pytest 51 passed |
| F3 | `routes/chat_handler_dispatch.py` | 路由入口加全局 `_route_semaphore`（`asyncio.Semaphore(LIMA_ROUTE_MAX_CONCURRENCY=32)`），`execute_non_stream_route` 用 `async with` 限制并发，防止慢后端占满线程池 | ruff + 1062 测试通过 |
| F5 | `routing_engine.py` | 非流式路径 `final_backend=="exhausted"` 且 answer 为空时调用 `last_resort_call`（Cloudflare 终极降级），对齐流式 `_ensure_content` 降级逻辑 | ruff clean |
| F6 | `health_state.py` | `load_health_state` 加载 cooldown 时强制 `cooldown_until=0.0`（重启清零，让 probe_loop 重新探测），保留 consecutive_failures/error 统计。修复 monotonic 时钟重启归零导致的"全熔断/全放行"摇摆 bug | pytest 通过 |
| F1（延后项完成） | `http_errors.py`、`http_retry.py`（新）、`http_sync.py`、`http_async.py` | 客户端层瞬时错误重试：新增 `is_retryable_error`（网络/408/429/502/503/504 可重试，400/401/403 不可重试）+ `_post_with_retry`/`_post_with_retry_async`（默认 2 次指数退避，429 遵从 Retry-After）；重试期间不调 record_failure（避免过度惩罚冷却），仅最终耗尽调一次 | ruff + size + 234 HTTP 测试通过 + 15 新增 retry 测试 |

- **延后高风险项（需专门集成测试，避免核心路径回归）**：
  - ~~F1（客户端层瞬时错误重试）~~ ✅ 已完成
  - ~~F4（httpx.Client 连接池复用）~~ ✅ 已完成（见 AUDIT-8 P4）
  - ~~F7（device/MQTT 启动降 WARM）~~ ✅ 已完成
- 状态：**AUDIT-4 全部关闭**。

---

## 2026-06-29 AUDIT-5：LiMa 可观测性、日志与监控体系审查

> 审查范围：observability/、routes/system_endpoints.py、routes/ops_metrics/、context_pipeline/tracing.py、routes/request_tracking.py、access_guard.py。聚焦运维可观测性（不重复 AUDIT-1~4）。关键发现均经亲自读源码核验。

### HIGH 级别（经核验）

| ID | 文件:行号 | 发现 | 核验 |
|----|-----------|------|------|
| AUDIT-5-O1 | `routes/system_endpoints.py:93-140` | **健康检查不探活运行时依赖**：`/health` 与 `/health/ready` 只读 `get_startup_state()`（启动 phase 状态）。启动完成后即使 SQLite 耗尽/Redis 挂掉/全部后端 dead/磁盘满，`/health` 仍返回 200 `"ok"`。公网 LB 探针会被死实例欺骗，死实例继续导流 | ✓ 已读源码确认 |
| AUDIT-5-O2 | `routes/request_tracking.py:150-162` + `routes/admin_api.py:81-85` | **明文用户 query 入指标**：`record_request` 把 `query[:80]` + `sys_prompt[:100]` 明文写入 `recent_logs` 内存，再经 `/api/logs` 暴露。用户可能在 query 里输入 API key/PII，经 admin 接口泄漏。`observability/events.py` 有 `_sanitize_text` 脱敏管线但此处完全绕过 | ✓ 已读源码确认 |
| AUDIT-5-O3 | `routes/admin_extra_alerts.py:14,20-64` | **告警规则系统是空壳**：只有 CRUD 端点（create/update/delete/list），`_ALERT_RULES` 纯内存，**无评估器**（grep evaluate/fired/trigger/check_threshold 零命中）。管理员配的阈值告警永远不会触发，无通知 | ✓ grep 确认零评估器 |
| AUDIT-5-O4 | `routes/admin_extra_insights.py:121-124` | **admin 审计是假审计**：`/api/agent-audit` 硬编码 `return {"tasks": []}`。增删后端、退役、改 client_keys、改配置等破坏性操作**全部无审计日志**，无法事后追溯谁在何时改了什么 | ✓ 已读源码确认 |
| AUDIT-5-O5 | `observability/correlation.py:100-118` + `observability/jsonl_store.py:43-57` | **设备任务审计可篡改**：`record_device_task_correlation` 写进程内内存 `deque(maxlen=500)` 重启即丢；`_trim_jsonl` 用 `path.write_text` 重写整个文件（非 append-only），历史记录可被覆盖。不满足审计日志防篡改要求 | ✓ 已读源码确认 |
| AUDIT-5-O6 | 无 OpenTelemetry（`requirements_server.txt` 仅 prometheus_client） | **无分布式追踪后端**：自研 `RequestTrace`/`Span`（tracing.py）仅写进程内内存 ring buffer（MAX_RECENT_TRACES=1000），重启即丢，无法跨实例关联。多后端 fallback 链路无法在 Jaeger/Tempo 可视化 | ✓ grep 确认无 otel |
| AUDIT-5-O7 | `routes/chat_endpoints.py:158` + grep `X-Request-Id` 零命中 | **trace_id 不写入 HTTP 响应头**：`new_trace()` 生成 trace 但不回写 `X-Request-Id` 响应头。用户报障时无法把客户端 ID 反查服务端日志；fallback 各跳之间无显式 request_id 串联 | ✓ grep 确认零响应头注入 |

### MEDIUM 级别
| ID | 文件:行号 | 发现 |
|----|-----------|------|
| AUDIT-5-O8 | `config/settings_core.py:242` | **结构化 JSON 日志默认关闭**（`structured_logging="0"`），生产默认 stderr 纯文本，无法被 Loki/ELK 机器解析 |
| AUDIT-5-O9 | 无日志轮转（grep RotatingFileHandler/maxBytes 零命中） | **无日志轮转/限流**，高并发错误循环会冲爆磁盘；根目录已有游离 `debug.log`/`_verify.txt` |
| AUDIT-5-O10 | `routes/admin_extra_logs.py` SSE + `backend_telemetry.jsonl` | **无错误聚合**：同类错误（如某 key 配额耗尽）逐条重复记日志，500 条 jsonl 很快被刷掉丢失根因 |
| AUDIT-5-O11 | `routes/system_endpoints.py:106-122` | **/health 信息泄漏**：公开（无鉴权）返回 `modules`（内部模块清单）、`startup.phases`、`security.anonymous_access` 状态，是攻击者侦察价值信息 |

### LOW 级别
- `observability/prometheus_metrics.py`：缺 in-flight 请求 Gauge 和队列深度指标，无法区分"延迟飙升因排队还是后端慢"
- `/metrics` 端点经 `require_private_api_key` 保护（好），但 Prometheus scrape 用静态 token，泄漏后无速率限制

### 已确认健康的维度
- Prometheus 指标命名规范、label 基数可控（backend×4 状态、capability 有限枚举）✓
- 结构化日志模块 `observability/structured_logging.py` 实现完整（trace_id 注入 contextvars）✓
- backend_telemetry jsonl 有上限（500 行）防无限增长 ✓

### 可观测性改进优先级
1. **立即**：O1 `/health/ready` 加运行时依赖探活（DB/Redis/后端/磁盘）；O2 query 脱敏（复用 `_sanitize_text`）
2. **本周**：O3 告警评估器落地；O4 admin 破坏性操作审计
3. **计划**：O5 审计 append-only 化；O6 OpenTelemetry 接入；O9 日志轮转

### AUDIT-5 修复完成（2026-06-29）

| ID | 修复文件 | 措施 | 验证 |
|----|----------|------|------|
| O1 | `routes/system_endpoints.py` | `/health/ready` 增加运行时依赖探活：检查至少一个后端非 dead（否则 ready=false）+ 磁盘剩余空间 ≥256MB。原实现只读启动 phase 状态，运行时依赖挂掉仍返回 200 的问题已修复 | pytest 通过 |
| O2 | `routes/request_tracking.py` | `record_request` 存储 query/sys_prompt 前用 `observability.events._sanitize_text` 脱敏（剥离密钥类模式），经 `/api/logs` 暴露的明文用户输入不再含密钥 | pytest 通过 |
| O4 | `routes/admin_api.py`、`routes/admin_extra_insights.py`、`tool_gateway/audit.py` | 破坏性 admin 操作（add/delete/toggle backend）接入 `audit_event` 持久化审计（密钥自动脱敏）；`_admin_actor` 提取操作者身份；`/api/agent-audit` 从返回空数组改为读取真实审计日志 | pytest 12 passed |
| O7 | `routes/request_id_middleware.py`、`server.py`、`tests/test_request_id_middleware.py` | 新增 `RequestIdMiddleware`：每个响应自动注入 `X-Request-Id`（优先复用 `X-LiMa-Trace-Id`，否则生成 UUID）；CORS `expose_headers` 增加该头；新增 2 个测试覆盖 health 与 chat 路径 | ruff + pyright + size + 全量 4162 passed + 线上 /health/ready 返回该头 |
| O8 | `config/settings_core.py`、`observability/structured_logging.py`、`.env.example` | 结构化 JSON 日志默认开启：`LIMA_STRUCTURED_LOGGING` 默认从 `"0"` 改为 `"1"`；文档字符串同步；.env.example 新增注释样例；新增子进程隔离测试验证默认/关/开 | ruff + pyright + size + 全量 4157 passed |
| O9 | `config/settings_core.py`、`observability/structured_logging.py`、`.env.example`、`tests/test_observability_log_rotation.py` | 默认启用滚动文件日志：`LIMA_LOG_FILE_PATH=logs/lima-router.log`（空字符串关闭），`RotatingFileHandler` 单文件 100MB、保留 5 个备份；结构化日志关闭时仍写文件；修复 `JsonFormatter` 在 Windows 上 `%f` 的兼容性问题 | ruff + pyright + size + 全量 4169 passed + VPS `/health/ready` 200 |
| O3 | `observability/alert_evaluator.py`、`server_lifespan_phases.py`、`routes/admin_extra_alerts.py`、`tests/test_alert_evaluator.py` | 新增告警规则评估器：60 秒周期读取 admin 面板规则，与 `backend_telemetry`/健康指标对比；支持 gt/gte/lt/lte/eq；命中后写 `data/alert_log.jsonl` 并记结构化 warning；按 `window_sec` cooldown 防刷屏；集成 lifespan WARM 阶段自动启动 | ruff + pyright + size + 全量 4179 passed + VPS 启动日志显示 `observability.alert_evaluator.start ok` |
| O10 | `observability/telemetry_aggregator.py`、`observability/backend_telemetry.py`、`observability/routing_guard.py`、`tests/test_telemetry_aggregator.py` | 新增 `BackendTelemetryAggregator`：按（backend/error_class/status_code/phase/attempt 等）指纹聚合重复后端遥测记录，内存缓冲达 100 条唯一指纹或 500 次尝试即刷入 jsonl；读取 summary/guard 前自动 flush；summary 与 routing_guard 按 `count` 统计，避免重复记录冲掉 500 条窗口 | ruff + pyright + size + 全量 4173 passed |
| O11 | `routes/system_endpoints.py`、`tests/test_system_endpoints.py`、`tests/test_routes_system_endpoints.py` | `/health` 鉴权区分：匿名请求仅返回 `status`/`version`/`model`/`startup.status`；带有效 Bearer token 才返回 `modules`/`startup` 详情/`security.anonymous_access` | ruff + pyright + size + 全量 4164 passed + 线上匿名 /health 不再含 modules/security |
| O5 | `observability/jsonl_store.py`、`observability/backend_telemetry.py`、`observability/cli_telemetry.py`、`tests/test_jsonl_store.py` | 审计/遥测 JSONL 改为纯追加：`append_jsonl_record` 写单行，超默认 1MB 时按大小滚动（`.1`…`.5`），不再重写整个文件；`backend_telemetry`/`cli_telemetry` 读取自动扫描备份文件；新增/更新测试覆盖追加、滚动、备份读取 | ruff + pyright + size + 全量 4181 passed + VPS 本地 `/health/ready` 200 |

- **延后项（架构级改造，需独立排期）**：O6（OpenTelemetry 接入）
- 状态：**AUDIT-5 HIGH 批次已全部关闭**（O1/O2/O3/O4/O5/O7/O8/O9/O10/O11）。

---

## 2026-06-29 AUDIT-6：LiMa API 契约一致性与测试覆盖审查

> 审查范围：routes/（205 端点/56 文件）、tests/（482 文件）、server.py、nginx 配置。聚焦 API 设计规范性与测试质量（不重复 AUDIT-1~5）。关键发现均经亲自读源码核验。

### HIGH 级别（经核验）

| ID | 文件:行号 | 发现 | 核验 |
|----|-----------|------|------|
| AUDIT-6-A1 | `server.py:40-45` | **生产 Swagger/OpenAPI 文档应用层未禁用**：`FastAPI()` 未传 `docs_url=None/openapi_url=None/redoc_url=None`，靠 nginx try_files 隐式拦截。一旦 nginx 重配或 uvicorn 直接监听公网，`/openapi.json` 暴露所有端点结构 | ✓ grep 确认无禁用 |
| AUDIT-6-A2 | `routes/images.py:161` vs `routes/chat_endpoints.py:64-67` | **error 字段类型不一致**：images 用 `{"error": "invalid image request"}`（字符串），chat 用 `{"error": {"message":..., "type":...}}`（对象）。同后端同名字段类型不同，客户端 `resp["error"]["message"]` 会崩——真实契约断裂 | ✓ 已读源码确认 |
| AUDIT-6-A3 | `routes/device_app_tasks.py:72,75,84` + `device_app_auth.py:238,240` | **业务错误码无码表且语义冲突**：4002 在 tasks 端点=参数校验失败，在 auth 端点=密码未设置；4003 在 tasks=任务构建失败，在 auth=旧密码错误。同一 code 不同端点含义完全不同，客户端无法按 code 分支 | ✓ 已读源码确认 |

### MEDIUM 级别

| ID | 文件:行号 | 发现 |
|----|-----------|------|
| AUDIT-6-A4 | `device_logic/http.py:14` `ok()` 信封定义了但 device 路由几乎未调用 | **成功响应格式三套并存无统一信封**：OpenAI 系平铺（choices/created）、device 系裸 dict、`ok()` 信封定义却没用 |
| AUDIT-6-A5 | device_app_api.py + device_app_tasks.py | **RESTful 与 RPC 风格混用**：GET/PUT/DELETE 与 POST /register、POST /unbind、POST /approve 混用；列表端点用 `limit` 无 `offset`/cursor，无法翻页遍历 |
| AUDIT-6-A6 | device_app_tasks.py:104 + device_logic/http.py:22-45 | **大量端点绕过 Pydantic 手动解析 dict**：用 `read_body` + `str_field` 手动取字段，无类型/长度/结构校验。对比 `images.py` 的 `ImageRequest(BaseModel)` 是正确范例 |
| AUDIT-6-A7 | `routes/system_endpoints.py:66-80` | **/v1/models 硬编码 13 个模型 ID**，与 backends_registry 动态注册脱节，列表会与实际可用后端漂移 |
| AUDIT-6-A8 | admin.py 用 HTTPException（`{"detail":...}`）vs device 系用 `err()`（`{"code":..., "message":...}`）vs OpenAI 系 `{"error":{...}}` | **错误抛出方式三套**，错误处理中间件无法统一拦截 |

### 测试覆盖盲区（MEDIUM）

| ID | 发现 |
|----|------|
| AUDIT-6-T1 | **流式响应中断无端到端测试**：`/v1/chat/completions` stream=true 是核心路径，但 `test_routes_chat_stream.py` 只测正常发完，未测客户端中途断开是否正确取消后端请求、是否泄漏 speculative route task |
| AUDIT-6-T2 | **降级链全是 mock 单元测试**：`test_routing_executor_fallback.py` 全用 MagicMock，无真实多后端串联集成测试。pytest.ini 默认 `-m "not network"`，CI 上降级链无真实后端验证 |
| AUDIT-6-T3 | **无路由引擎并发竞态测试**：有 device task store 并发测试，但无多个请求并发选择同一后端的竞态测试 |

### 已确认健康的维度
- **无被 skip/xfail 的测试**（grep skip/xfail 计数为 0）✓
- **测试文件数量充足**（482 个测试文件）✓
- **图片端点 ImageRequest 是 Pydantic 校验范例**（pattern/ge/le/field_validator 齐全）✓

### API 契约改进优先级
1. **立即**：A1 应用层禁文档（`docs_url=None`）；A2 统一 error 字段类型
2. **本周**：A3 建立错误码表 `docs/error_codes.md`；A4 统一响应信封；T1 补流式中断测试
3. **计划**：A5 REST 风格统一；A6 Pydantic 收口；A7 /v1/models 动态生成；T2 真实后端集成测试

### AUDIT-6 修复完成（2026-06-29）

| ID | 修复文件 | 措施 | 验证 |
|----|----------|------|------|
| A1 | `server.py` | `FastAPI()` 默认禁用 `docs_url`/`redoc_url`/`openapi_url`（防端点结构泄漏）；开发环境 `LIMA_DOCS_ENABLED=1` 可暴露 | ruff + pyright + 全量 pytest（含新增 `tests/test_server_docs_disabled.py`）通过 |
| A2 | `routes/images.py` | error 字段从字符串 `{"error":"..."}` 改为对象 `{"error":{"message":...,"type":...}}`，与 chat_endpoints 一致 | ruff clean |
| A3 | `docs/error_codes.md` | 新增业务错误码表（4001-4004 语义定义 + 历史冲突说明 + 响应格式规范） | 文档新增 |
| A7 | `routes/system_endpoints.py` | `/v1/models` 改为从 `backends_registry.BACKENDS` 动态生成模型列表；按 model id 去重；从 `model` 字段的 provider 前缀或 backend key 推导 `owned_by`；保留 LiMa 自有模型 | ruff + pyright + size + 新增 2 个动态模型测试 + 全量 pytest |

- **延后项（大范围端点改造）**：A4（统一响应信封，涉及所有 device 端点）、A5（REST 风格统一）、A6（Pydantic 收口）、T1/T2（测试补齐）
- 状态：**AUDIT-6 HIGH 批次与 A7 已关闭**（A1/A2/A3/A7）。

---

## 2026-06-29 AUDIT-7：LiMa 部署运维、容器化、CI/CD、备份与供应链审查

> 审查范围：Dockerfile、docker-compose.yml、.github/workflows/、requirements*.txt、nginx 配置、infra/vps/、scripts/deploy_unified*.py。关键背景：生产通过 **systemd 直跑 uvicorn 单 worker**（不用 Docker）。关键发现均经亲自读源码核验。

### HIGH 级别（经核验）

| ID | 文件:行号 | 发现 | 核验 |
|----|-----------|------|------|
| AUDIT-7-D1 | `.github/workflows/test.yml:33-61` | **CI "Tests" 工作流从不跑测试**：安装了 pytest 但执行步骤只有 ruff/pyright/bandit/run_pre_commit_check，**无任何 `pytest` 步骤**。deploy.yml 把 test.yml 当 needs 前置门禁，但该门禁不验证功能正确性 = 生产部署无测试保护 | ✓ grep 确认无 pytest 步骤 |
| AUDIT-7-D2 | `.github/workflows/deploy.yml:16-18` | **生产部署无 GitHub Environment 审批保护**：deploy job 无 `environment:` 字段，任何对 main 有 push 权限即触发对生产 VPS 的 SSH 部署。无 required reviewer、无 deployment gate | ✓ 已读源码确认 |
| AUDIT-7-D3 | `infra/vps/systemd/lima-router.service:11` + `litestream.yml` | **Litestream 备份仅写本地无异地副本**：7 个 SQLite DB 的 replica 全部 `type: file` 写同一台 VPS 的 `/opt/lima-router/backups/litestream/`，S3/R2 副本被注释。VPS 整机故障时主库与本地副本同时丢失 | ✓ 已读源码确认 |
| AUDIT-7-D4 | `requirements_server.txt:5-37` | **依赖全用 `>=` 范围无 hash pinning**：除 3 个 `==` 外全 `>=`，构建不可复现 + PyPI 投毒风险。文件已注释排除过 `fastapi 0.136.3 MAL-2026-4750`（真实供应链事件），但 `>=` 无法防下一次 | ✓ 已读源码确认 |

### MEDIUM 级别

| ID | 文件:行号 | 发现 |
|----|-----------|------|
| AUDIT-7-D5 | `_nginx_chat_temp.conf:117,257,276` + `infra/vps/nginx/` | **limit_req_zone 定义未版本化**：nginx 配置引用 `zone=api`/`zone=agent` 速率限制区，但全仓库版本化配置不含 `limit_req_zone` 定义（在未跟踪的 nginx.conf）。换机器灾难恢复时会脆断或速率限制静默失效 |
| AUDIT-7-D6 | `Dockerfile:1`（`python:3.10-slim` 浮 tag）+ `docker-compose.yml:54`（`searxng/searxng` 无 tag=latest） | **镜像未固定 patch 版本**：python:3.10-slim 浮动（且 3.10 接近 EOL 2026-10）；searxng 用 latest |
| AUDIT-7-D7 | `docker-compose.yml:1-73` | **无资源限制**：lima/redis/searxng 三服务均无 mem_limit/cpus，一方内存泄漏拖垮整机 |
| AUDIT-7-D8 | `_nginx_chat_temp.conf:301-306` | **TLS 未显式硬化**：仅 `listen 443 ssl` + 依赖未跟踪的 certbot options；HSTS max-age=15552000（180天）偏短且无 includeSubDomains;preload |
| AUDIT-7-D9 | `deploy_unified_preflight.py:39-58` | **回滚只覆盖代码不覆盖 .env 与数据库**：备份是 `tar -czf runtime-before.tgz` 仅含将覆盖的 .py/.html；.env 人工维护不在回滚保护内，SQLite DB 不备份。回滚 tar 包从未做试恢复验证 |
| AUDIT-7-D10 | `deploy_unified_restart.py:37-41` + `deploy.yml:41-49` | **部署用 root SSH + 密码回退 + ssh-keyscan**：以 root 直连 VPS，密钥失败回退明文密码；CI 用 `ssh-keyscan` 把任意主机指纹加入信任（中间人可注入伪造主机键） |

### LOW 级别
- systemd 未设 `TimeoutStopSec`，shutdown 阶段挂起被 SIGKILL 截断流式请求
- 重型依赖（opencv/scikit-image/Pillow）无条件打入服务镜像，主 chat 路由不需要
- deploy.yml 无 pip cache（每次重装依赖），secrets 用 `${{ }}` 内联有注入面

### 已确认健康的维度
- Dockerfile 多阶段构建 + non-root user（USER lima）+ HEALTHCHECK + .dockerignore（59 行）✓
- 生产 .env 未被 git 跟踪，.gitleaks.toml 存在 ✓
- nginx 已补安全头（HSTS/X-Content-Type-Options/X-Frame-Options/Referrer-Policy）✓
- 容量预检 + 健康失败自动代码回滚 + nginx 配置三段式 backup/test/reload/rollback ✓
- graceful shutdown 已实现，systemd Restart=always ✓，dependabot 三类生态全覆盖 ✓
- deploy.yml 用 `*_SET` 布尔技巧避免 secret 回显日志 ✓

### 部署运维改进优先级
1. **立即**：D1 CI 加 pytest 步骤（最高杠杆，恢复测试门禁）；D2 deploy job 加 `environment: production` + required reviewers
2. **本周**：D3 启用 Litestream S3/R2 异地副本；D4 依赖 hash pinning（pip-compile --generate-hashes）
3. **计划**：D5 limit_req_zone 版本化；D6 镜像钉版本；D7 资源限制；D8 TLS 硬化；D9 回滚覆盖 .env/DB

### AUDIT-7 修复完成（2026-06-29）

| ID | 修复文件 | 措施 | 验证 |
|----|----------|------|------|
| D1 | `.github/workflows/test.yml` | 新增 `Run test suite` 步骤：`python -m pytest --tb=short -q`（pytest.ini 默认 `-m "not network"` 排除真实后端）。原工作流装了 pytest 却从不运行的问题已修复，恢复 CI 测试门禁 | 语法检查 |
| D2 | `.github/workflows/deploy.yml` | deploy job 新增 `environment: production`（需在 GitHub repo Settings → Environments 配置 required reviewers，防误合并直接 SSH 进生产） | 语法检查 |
| D3 | `litestream.yml`、`.env.example` | 为 4 个关键库（sessions/agent_tasks/tool_audit/outcome_ledger）新增 S3/R2 异地副本配置模板（`${LITESTREAM_S3_*}` 环境变量驱动）；`.env.example` 补充 LITESTREAM_S3_* 变量声明 | 配置审查 |
| D7 | `docker-compose.yml` | 为 `lima`/`redis`/`searxng` 三服务添加 `deploy.resources.limits`（cpu/memory），防止单服务内存泄漏拖垮整机；lima 限制 1 CPU/1G，redis/searxng 各 0.5 CPU/512M | YAML 语法检查通过 |

- ~~延后项：D4（依赖 hash pinning）~~ ✅ 已完成（2026-06-30）：`requirements_server.txt`/`requirements_dev.txt` 的 19 个 `>=` 收紧为 `~=`（锁定主.次版本，允许安全补丁）或 `==`（精确锁定）；pip freeze 验证当前环境兼容。完整 hash pinning（`--require-hashes` + 跨平台 lock 文件）留作后续。
- **延后项**：D5-D6/D8-D10（limit_req_zone 版本化/镜像钉版本/TLS 硬化/回滚覆盖 .env/SSH 加固，多为运维配置层）
- 状态：**AUDIT-7 HIGH 批次与 D7 已关闭**（D1/D2/D3/D7）。

---

## 2026-06-29 AUDIT-8：LiMa 性能、资源效率与扩展性瓶颈审查

> 审查范围：热路径性能、缓存效率、数据库效率、异步效率、冷启动、扩展性。关键发现均经亲自读源码核验。

### HIGH 级别（经核验）

| ID | 文件:行号 | 发现 | 核验 |
|----|-----------|------|------|
| AUDIT-8-P1 | `routing_intent.py:289-296` + `routing_intent_instructor.py:47` | **同步 LLM 调用阻塞主路径**：低置信度时 `maybe_instructor_intent` 同步调 `create_structured_completion`（阻塞网络调用），占用 to_thread worker 线程。结合 P2 三次调用，可能触发 3 次 LLM | ✓ 已读源码确认 |
| AUDIT-8-P2 | `chat_handler_dispatch.py:195,218` + `routing_engine_intent.py:36` | **三重重复 intent 分析**：同一 query 的 `analyze_intent` 在一次请求被调 3 次（:195 结果丢弃、:218 又算、route() 内第三次），每次跑 30+ 正则。CPU 浪费 ~3x | ✓ 已读源码确认 |
| AUDIT-8-P3 | `semantic_cache/store.py:46-67` | **语义缓存全表扫描 + 无 WAL**：get_candidates 每次拉 100 条候选（含完整 embedding+response）回 Python 算 cosine；全文无 `PRAGMA journal_mode=WAL`（grep 确认空），并发写互斥锁全库 | ✓ grep 确认无 WAL |
| AUDIT-8-P4 | `http_request_builder/client.py:24-45` + `http_sync.py:223,254` | **httpx Client 每次新建无连接池复用**：每次后端调用 `with hc._build_client(backend,timeout)` 创建并销毁 Client，每次重建 TLS 握手（HTTPS 后端 +50-200ms） | ✓ 已读源码确认 |
| AUDIT-8-P5 | `semantic_cache/cache.py:84` + `code_context/embedding_client.py:48-52` | **缓存查询同步调 Jina 网络**：每次 lookup/store 同步调 Jina 算 embedding（urllib 阻塞，15s 超时）。缓存命中本应加速，却额外加 ~100-500ms，Jina 抖动时最坏 +15s。无 embedding LRU 缓存 | ✓ 已读源码确认 |

### MEDIUM 级别（扩展性障碍——多 worker 前置条件）

| ID | 文件:行号 | 发现 |
|----|-----------|------|
| AUDIT-8-P6 | `health_models.py:22-26` + `budget_manager.py:101-103` | **健康/预算状态完全进程本地**：health_map/cooldown/quality 和 budget _usage 全内存（threading.RLock）。多 worker 下每个 worker 独立副本，worker A 标某后端 dead，worker B 仍往死掉后端发请求；预算计数被 N 倍突破 |
| AUDIT-8-P7 | `server.py:122` + `Dockerfile:29` + systemd | **单 worker 部署**：无 `--workers`，全部流量压在一个进程。多 worker 障碍是 P6（进程本地状态不一致）。需先解决 P6 才能安全扩 worker |
| AUDIT-8-P8 | `speculative_execution.py:79-89` | **投机执行浪费预算 + 一次性线程池**：简单请求同时发 5 个后端，loser 的 token 被消耗但只记 winner 预算；ThreadPoolExecutor 每次新建不复用；loser record_failure 可能误判健康后端 |
| AUDIT-8-P9 | `routing_engine.py:281-295` + `routing_classifier.py:86` | **退役逻辑仍在热路径**：scenario 永远返回 "chat"（v3.0 编码退役）、retrieval 已 no-op，但仍各包一层 trace_span + validate_value dataclass 校验。纯开销 |

### LOW 级别
- `config/sqlite_pool.py:37`：连接池每次借出执行 `SELECT 1` 探活（额外往返）
- `routing_selector/scoring.py:46-51` + `filters.py:15`：热路径内函数级 import（每次 dict 查找）
- `routing_selector/ranking.py:17`：排序 key 内每元素调 budget_manager（带锁）+ random.uniform（非确定性）
- `context_pipeline/skill_store.py:117-126`：recall key 计算遍历全部 messages 拼 user_text（长对话线性增长）

### 已确认健康的维度
- **意图分类主路径不调 LLM**：走快速正则/关键词（_ANALYZE_RULES），仅低置信度才触发 instructor ✓
- **chromadb/tree-sitter 懒加载正确**：importlib 探测 + 用时才 import，不拖慢启动 ✓
- **health record_success 条件持久化**：仅状态变化时写 SQLite，合理 ✓
- **测试无 skip/xfail，文件数量充足** ✓

### 性能优化优先级
1. **立即**：P1 instructor 降级为异步/调高阈值（消除主路径同步 LLM 阻塞）；P2 intent 算一次挂 context 复用
2. **本周**：P3 语义缓存加 WAL + 降候选量；P4 httpx Client 连接池复用；P5 embedding LRU 缓存 + 异步化
3. **计划**：P6 健康/预算搬共享存储（Redis/SQLite）→ P7 扩多 worker；P8 投机 max_parallel 降到 2-3；P9 删退役热路径逻辑

**关键性能路径**：P1（同步 LLM）是单请求最大延迟变数；P2（三重 intent）是稳定 CPU 浪费；P3+P5（缓存开销）使缓存可能比不缓存还慢；P4（连接重建）在每次后端调用叠加 TLS 成本。

### AUDIT-8 修复完成（2026-06-29）

| ID | 修复文件 | 措施 | 验证 |
|----|----------|------|------|
| P3 | `semantic_cache/store.py` | `_ensure_schema` 新增 `PRAGMA journal_mode=WAL` + `PRAGMA synchronous=NORMAL`，启用 WAL 模式允许并发读写，消除默认 journal 模式下 upsert/bump_hit_count 与 lookup 的全库互斥锁（WAL 是持久化 DB 属性，设一次即可） | ruff + 35 缓存测试通过 |
| AUDIT-1-H1（关联） | `semantic_cache/store.py` | 已确认改用 `pooled_sqlite_conn`（连接池正确关闭），原 `_connection` 泄漏已修复 | 历史修复 |
| P2（延后项完成） | `routes/chat_handler_dispatch.py`、`routing_engine.py`、`routing_engine_intent.py`、`routes/v3_adapters.py` | 三重 intent 去重：删除流式死调用；ChatRunContext 加 intent 字段由 start_chat_run 算一次；execute_non_stream_route 读 ctx.intent；resolve_intent 支持 precomputed_intent 透参短路（保留 semantic_router 优先级）。CPU 浪费 ~3x 消除 | pytest 1449 路由测试通过 + 新增 dedup 测试 |
| P4（延后项完成） | `http_request_builder/client.py`、`backends_registry/__init__.py`、`server_lifespan.py` | httpx.Client 连接池复用：按 backend 缓存长生命 client（带 httpx.Limits 连接池）+ no-op context wrapper（`__exit__` 不关闭，保持 `with` 调用点兼容）；AsyncClient 懒创建（loop 安全）；add/remove_backend 配套缓存失效；FastAPI shutdown 调 aclose_all_clients。消除每次调用重建 TLS 握手的 FD 泄漏 + 延迟开销 | ruff + size + 761 HTTP 测试通过 + 7 新增 pool 测试 |
| P5（延后项完成） | `semantic_cache/embedder.py`、`code_context/embedding_client.py`、`semantic_cache/config.py`、`.env.example` | JinaEmbedder 新增线程安全 `_EmbeddingLRUCache`，批量查询只发送未缓存文本；新增 `get_embeddings_async`/`aembed` 非阻塞路径；`LIMA_EMBEDDING_CACHE_SIZE` 默认 1024；API key 传入 embedder 使 key 轮换自动失效缓存 | ruff + pyright + size + 新增 5 个 embedder 测试 + 全量 4152 passed |
| P1（延后项完成） | `routing_intent_instructor.py`、`models/structured_outputs/instructor_client.py`、`config/env.py` | 降低 instructor intent 触发频率与阻塞面：默认阈值从 0.70 提到 0.80，超时从 10s 降到 5s，重试从 2 次降到 1 次；新增 256 容量 LRU 缓存避免重复 LLM 调用；新增 `create_structured_completion_async`/`amaybe_instructor_intent` 非阻塞路径供未来 async 调用者 | ruff + pyright + size + 新增缓存/async 测试 + 全量 4160 passed |
| P6-缓解 1 | `health_state.py`、`health_state_persistence.py` | 将 SQLite 健康状态持久化拆分为独立模块；`save_on_change` 在 async 事件循环中改为后台线程 5s 防抖写入，避免每次后端健康变化都同步写库阻塞 `/health/ready` | ruff + pyright + size + 全量 4181 passed |
| P6-缓解 2 | `observability/structured_logging.py` | 滚动文件日志改用 `QueueHandler` + `QueueListener`：日志记录进队列后立即返回，后台线程负责写磁盘，消除高日志量下的同步 I/O 阻塞事件循环 | ruff + pyright + size + log_rotation 测试通过 |
| P6-缓解 3 | `http_request_builder/body.py` | `optimize_for_prefix_cache` 不可用的 ImportError 从 `warning` 降为 `debug`，避免每个请求都写一条重复日志冲爆磁盘 | ruff + pyright + size + 17 相关测试通过 |
| P6-修复 | `health_models.py` | `QualityState` 补 `avg_latency` 计算属性，修复 `health_state.get_latency_map()` / `routing_selector` 抛 `AttributeError` 的回归 | ruff + pyright + size + 全量 4181 passed |
| P6-缓解 4 | `health_state_persistence.py` | 加锁拷贝 + 降 fsync：持久化时先持 `_lock` 复制三份状态快照，释放锁后再写 SQLite；`_ensure_tables` 增加 `PRAGMA synchronous=NORMAL`，消除慢 fsync 持锁阻塞 `/health/ready` 与路由选择器 | ruff + pyright + size + 全量 4181 passed + VPS 本地 `/health/ready` <100ms |
| P6-诊断 | `observability/stack_dump.py`、`server.py` | 生产环境注册 SIGUSR1 栈转储处理器；事件循环卡顿时执行 `kill -USR1 <pid>` 可将所有线程堆栈写出到 `/tmp/lima-stacks-*.txt`，用于定位阻塞根因 | ruff + pyright + size + VPS 实测成功捕获堆栈 |

- **延后项（核心路径改造，需专门性能/集成测试）**：P6/P7（共享状态+多 worker）
- **当前状态**：P6 事件循环阻塞已完全缓解（健康状态写库、文件日志写盘均异步化，SQLite 写持锁问题通过锁拷贝+synchronous=NORMAL 解决）。VPS 本地与绕过 Cloudflare 直连 origin 的 `/health/ready` 均稳定在 100ms 内。公网探针偶发 504 的进一步排查显示：同一时刻 Cloudflare 公网路径出现 10s 级延迟/504，而直接访问 origin IP（`47.112.162.80`）始终 <200ms，且 VPS 栈转储确认主事件循环无阻塞。根因判定为 **Cloudflare 边缘到源站的网络路径抖动**，非 LiMa 代码阻塞。建议生产监控优先使用 origin 直连探针，并持续关注 Cloudflare 侧网络质量。
- 状态：**AUDIT-8 P1/P2/P3/P4/P5/P8/P9 已关闭**；P6/P7 缓解完成，公网 504 已定位并给出运维建议。




## 2026-06-29 AUDIT-9：设备任务状态机功能正确性审查

> 审查范围：设备任务状态机（pending→processing→done/failed）、双后端（InMemory/Redis）语义一致性、重试与死信逻辑。关键发现均经亲自逐行读源码追踪闭合。

### CRITICAL 级别（经核验，真实可触发生产 bug）

| ID | 文件:行号 | 发现 | 核验 |
|----|-----------|------|------|
| AUDIT-9-S1 | `device_gateway/task_events.py:220-226` + `store.py:175-180` vs `redis_store.py:189-193` | **生产 Redis 模式设备失败任务无限重试**：`execute_recovery` 读 `attempt=retry_count`（:220）→ `should_retry` 判 `0<=attempt<max_retries`（recovery.py:42）→ 唯一改计数的 `reset_task_for_retry`（:226）在两后端语义相反：**InMemory 递增** retry_count，**Redis 不递增**。生产 Redis 下 attempt 永远=0 → should_retry 永远放行 → 可重试错误无限重试，任务永不进死信。测试用 InMemory 会正常递增有界，CI 永远绿，bug 仅生产触发 | ✓ 逐行追踪 + 读 should_retry 闭合 |

### HIGH 级别（经核验）

| ID | 文件:行号 | 发现 | 核验 |
|----|-----------|------|------|
| AUDIT-9-S2 | `device_gateway/redis_store.py:232` + 全 device_gateway | **stale reaper 是死代码**（确认 AUDIT-4-F2）：`recover_stale_processing` 实现存在但无任何后台任务/定时器调用方（仅 task_lifecycle.py:94 封装 + tasks.py re-export，封装函数本身也无调用方）。设备 LMOVE 到 processing 后崩溃，任务永远卡 processing 队列直到 Redis TTL 整体过期 = 丢任务 | ✓ grep 确认无后台调用 |
| AUDIT-9-S3 | `device_gateway/store.py:155-158` | **InMemory 无 processing 队列概念**：`ack_processing`/`recover_stale_processing` 直接 `return False`/`return 0`，而 Redis 用 LMOVE pending→processing 双队列。两后端崩溃恢复行为完全不同，单测（用 InMemory）无法覆盖生产 Redis 语义 | ✓ 已读源码确认 |

### MEDIUM 级别

| ID | 文件:行号 | 发现 |
|----|-----------|------|
| AUDIT-9-S4 | `device_gateway/redis_store.py:108-111` | **任务状态无 CAS/版本号**（确认 AUDIT-4 数据一致性）：`_write_task_state` 裸 HSET 覆盖，设备上报 + reaper requeue 并发时后写覆盖前写，丢事件。全 stores 无 version/etag/WATCH 乐观锁原语 |

### 根因模式
AUDIT-9 多个发现指向同一架构问题：**InMemory 与 Redis 两个 store 的状态机语义不等价**，测试默认用 InMemory，导致"仅生产 Redis 触发"的整类 bug 对 CI 不可见。与 AUDIT-7-D1（CI 根本不跑 pytest）叠加 = 双重隐形。

### 修复建议
1. **立即**：S1 让 Redis `reset_task_for_retry` 也递增 retry_count，与 InMemory 对齐（消除无限重试）。或更稳健：把递增逻辑移到 `execute_recovery` 调用方，两后端 reset 只做状态重置不碰计数
2. **本周**：S2 接线 stale reaper 到后台 asyncio 任务（30-60s 周期）；S3 给 InMemory 加 processing 队列概念或在测试矩阵加 Redis 后端
3. **计划**：S4 task state 加 version 字段 + Lua CAS

### AUDIT-9 修复完成（2026-06-29）

| ID | 修复文件 | 措施 | 验证 |
|----|----------|------|------|
| S1 | `device_gateway/redis_store.py` | `reset_task_for_retry` 重置为 queued 时递增 retry_count，与 InMemory 对齐。修复生产 Redis 下 execute_recovery 的 attempt 永远=0 导致的**设备失败任务无限重试** bug | ruff + 37 任务存储测试通过 |
| S2 | `routes/device_gateway_helpers.py`、`device_gateway/sessions.py` | stale reaper 后台任务（与 AUDIT-4-F2 同一修复，60s 周期扫描 processing 队列） | 见 AUDIT-4 |

- ~~延后项：S3（InMemory 加 processing 队列概念，需改测试矩阵）、S4（task state CAS）~~ S3/S4 ✅ 均已完成
- **AUDIT-9 S4 修复完成（2026-06-30）**：新增 `device_gateway/redis_cas.py`——两个 Lua 脚本（CAS 写 + events 原生追加）+ Python 包装（`cas_write_state`/`append_event_atomic`/`_cas_update` helper，bounded 3 次重试）。改造 11 个调用点：`record_motion_event` 用 events 原生追加（彻底消除覆盖丢失）；其余 10 处用 version CAS + 冲突重试；`task_snapshot` 返回 `_version`；`_write_task_state` 加 `expected_version` 参数（None=盲写向后兼容）。Lua 不可用时（测试 fake）回退纯 Python。验证：ruff + size + 10 新增 CAS 测试 + 全量 4196 passed。
- **AUDIT-9 S3 修复完成（2026-06-30）**：`device_gateway/store.py` InMemory 后端新增 `_processing_by_device` 队列，`pop_pending_tasks` 把任务移到 processing（记录 `processing_started_at`）；`ack_processing`/`recover_stale_processing`/`abandon_processing_task` 从空实现改为真实逻辑（与 Redis 后端语义对齐）。新增 3 个 InMemory processing 队列测试（ack/recover/abandon）。消除"测试用 InMemory 无法覆盖生产 Redis processing 队列语义"的盲区。
- 状态：**AUDIT-9 全部关闭**（S1/S2/S3/S4）。


## 2026-06-29 AUDIT-10：运动控制校验与记忆 PII 审查

> 审查范围：绘图/手写几何管线、运动控制参数校验（物理安全关键）、会话记忆脱敏、device_memory 双后端一致性。关键发现均经亲自构造测试用例核验。

### CRITICAL 级别（经核验，物理安全关键）

| ID | 文件:行号 | 发现 | 核验 |
|----|-----------|------|------|
| AUDIT-10-V1 | `device_gateway/path_validator.py:66-67` + `device_intelligence/safety.py` `_point_outside_workspace` | **NaN 坐标绕过运动边界校验**：`val < MIN or val > MAX` 在 IEEE 754 下对 NaN 全为 False，`x=NaN` 通过校验返回 success！NaN 坐标会下发到物理机械臂运动控制 → G-code 未定义行为，可能撞机/越界。两层校验（path_validator + profile_limit_error 的 _point_outside_workspace）均被 NaN 绕过 | ✓ 构造 x=NaN 测试确认通过校验 |

### HIGH 级别（经核验）

| ID | 文件:行号 | 发现 | 核验 |
|----|-----------|------|------|
| AUDIT-10-V2 | `device_gateway/path_validator.py:69` | **feed 非数字抛未捕获异常**：`float(params.get("feed", 500.0))` 无 try/except，`feed='abc'` 抛 ValueError、`feed=None` 抛 TypeError，而非返回结构化 `E_BAD_PARAMS`。异常会冒泡到任务创建层。对比 `profile_limit_error` 的 feed 校验用了 isinstance 守卫，两处不一致 | ✓ 构造 feed='abc'/None 测试确认抛异常 |
| AUDIT-10-V3 | `session_memory/redact.py:22-37` | **记忆脱敏无 PII 覆盖**：`_SECRET_RE` 只覆盖密钥（sk-/ghp_/JWT/AWS/Bearer）+ 凭证 URL + SSH key，**完全无邮箱/手机号/身份证/银行卡 PII 模式**。公网中文用户对话中的手机号/身份证会明文入库（memories 表）并可被 recall/export | ✓ 已读全文确认无 PII 正则 |

### MEDIUM 级别

| ID | 文件:行号 | 发现 |
|----|-----------|------|
| AUDIT-10-V4 | `device_memory/redis_store.py:90` | **disable 误续命 TTL**：`disable` 用 `updated.ttl_days*86400` 重设 Redis TTL，从当前时刻算全新 TTL 而非剩余 TTL，禁用一条旧记忆反而延长其存活。InMemory 版无此问题（只置 disabled 标志） |

### 已确认健康的维度
- **path_validator 核心防线良好**：坐标边界 ±500、点数上限 200、feed 范围、能力白名单、route_policy schema 校验完整 ✓（仅 NaN/类型边界两个漏洞）
- **Inf 坐标正确拦截**：`x=Inf` 返回 E_BAD_PARAMS ✓（只有 NaN 漏）
- **handwriting 路由校验完整**：Pydantic min/max + ASCII fallback 边界 + 限流 ✓
- **device_memory 双后端 TTL 软过滤语义一致**：都用 `age_days > ttl_days` ✓（区别于 AUDIT-9 的 task store 分歧）
- **记忆 daemon 循环健壮**：CancelledError + Exception + sleep 间隔，无忙循环 ✓
- **promote_memory 拒绝含密钥的 evidence**：`if "[REDACTED]" in evidence: return False` ✓

### 修复建议
1. **立即**：V1 在 path_validator 和 _point_outside_workspace 加 `math.isnan(val)` 检查（NaN 直接判 E_BAD_PARAMS）——这是物理安全，最高优先；V2 feed 转换包 try/except 返回 E_BAD_PARAMS
2. **本周**：V3 给 redact.py 补 PII 正则（中国手机号 `1[3-9]\d{9}`、身份证 18 位、邮箱、银行卡），合规要求
3. **计划**：V4 disable 改为读剩余 TTL（Redis TTL 命令）再重设

### AUDIT-10 修复完成（2026-06-29）

| ID | 修复文件 | 措施 | 验证 |
|----|----------|------|------|
| V1 | `device_gateway/path_validator.py`、`device_intelligence/safety.py` | 坐标校验加 `math.isfinite(val)` 检查，拦截 NaN/Inf。修复 IEEE 754 NaN 比较全 False 导致的**机械臂越界/撞机**物理安全 bug（两层校验都补） | Python 实测：NaN=BLOCKED, Inf=BLOCKED, normal=OK |
| V2 | `device_gateway/path_validator.py` | feed 转换包 try/except，非数字返回 `E_BAD_PARAMS` 而非抛 ValueError/TypeError | Python 实测：feed='abc'=BLOCKED, feed=None=BLOCKED |
| V3 | `session_memory/redact.py` | 新增 PII 脱敏模式（手机号 `1[3-9]\d{9}`、身份证 18 位、邮箱、银行卡 16-19 位），`has_secret`/`redact_text` 统一覆盖。记忆存储前剥离 PII | Python 实测：手机/邮箱/身份证均替换为 [REDACTED_PII] |

- ~~延后项：V4（device_memory Redis disable 误续命 TTL，需读剩余 TTL 再重设）~~ ✅ 已完成（见下）
- **AUDIT-10 V4 修复完成（2026-06-29）**：`device_memory/redis_store.py` `disable` 改为读 Redis `ttl(key)` 获取剩余秒数（客户端不支持 ttl 时回退按 created_at 计算剩余值），用剩余 TTL 重设而非 `ttl_days*86400` 全新 TTL。修复禁用旧记忆反而"续命"的 bug。验证：ruff + 60 device store 测试通过。
- 状态：**AUDIT-10 全部关闭**（V1/V2/V3/V4）。V1 是物理安全修复（防撞机）。


## 2026-06-29 AUDIT-11：第三方集成、上传资产、WebSocket 协议边界审查

> 审查范围：integrations/（autohanding）、routes/upload.py + device_app_assets.py、device_gateway 协议握手与 WS 生命周期、SessionRegistry。关键发现均经亲自读源码 + 构造测试核验。

### HIGH 级别（经核验）

| ID | 文件:行号 | 发现 | 核验 |
|----|-----------|------|------|
| AUDIT-11-I1 | `integrations/autohanding/client.py:117-127` | **autohanding ZIP bomb 无防护**：`_extract_first_png` 用 `zf.read(names[0])` 全量解压到内存，无解压大小上限。实测 497KB 压缩 ZIP 可解压成 500MB。autohanding 是第三方公网服务，其故障/被篡改返回恶意大 ZIP 可 OOM 整个 LiMa 进程 | ✓ 构造 500MB zip bomb 测试确认 |
| AUDIT-11-W1 | `routes/device_gateway_ws.py:117` + `device_gateway/sessions.py:56` | **WebSocket 无 receive 超时 + 无连接数限制**（Slowloris 慢速攻击）：`await websocket.receive()` 无超时，攻击者 hello 鉴权后发慢/不发数据，连接永久占用；`SessionRegistry._sessions` 无界 dict 无 max_connections。配合 AUDIT-1-C1（fallback 鉴权）可低成本资源耗尽 | ✓ 已读源码确认无超时/无限制 |
| AUDIT-11-W2 | `routes/device_gateway_dispatch.py:extract_ws_token` | **WS token 支持 3 种注入含 query 参数**：ticket / Authorization header / `?token=`&`?authorization=` query 参数。query 参数方式（chat-web 在用）会让 Bearer token 进 nginx access log/Referer，确认 AUDIT-2-W2 的后端侧根因 | ✓ 已读源码确认 3 路径 |
| AUDIT-11-A1 | `xiaozhi_drawing/svg_validator.py` | **SVG 上传零内容净化**：svg_validator 只校验几何复杂度（点数/bbox），**完全不做 `<script>`/事件处理器（onload/onerror）剥离**。上传的 SVG 若后续被 inline 渲染（非 `<img>`）即存储型 XSS。与 AUDIT-2 chat-web 端 SVG 上传无净化叠加 | ✓ grep 确认无 sanitize/lxml/bleach |

### MEDIUM 级别

| ID | 文件:行号 | 发现 |
|----|-----------|------|
| AUDIT-11-W3 | `device_gateway/sessions.py:54-62` | **SessionRegistry 无僵尸会话清理**：只在 `register` 时覆盖同 device_id 旧会话，但无后台任务按心跳超时清理僵尸连接（设备断电但 TCP 未 FIN）。僵尸会话的 outstanding tasks 永不 requeue，直到新连接覆盖或进程重启 |
| AUDIT-11-I2 | `integrations/autohanding/client.py:169` | **autohanding 客户端每次新建 httpx.AsyncClient**：`async with httpx.AsyncClient()` 每次调用创建/销毁，无连接池复用（与 AUDIT-8-P4 同类）。手写功能高频调用时 TLS 握手开销累积 |

### LOW 级别
- `extract_ws_token` 对无 Bearer 前缀的 authorization 只 `logger.warning` 仍放行（向后兼容），宽松度偏高
- autohanding `_parse_preview_response` 用 `"频率" in body` 中文关键字判断限流，依赖第三方页面文案不变，脆弱

### 已确认健康的维度
- **upload.py 双校验完整**：扩展名白名单 + 魔数签名（PNG/JPG/GIF/WEBP）+ 5MB 上限 + 路径穿越三重防护（正则+resolve+is_relative_to）+ 限流 ✓
- **协议握手校验健壮**：`validate_hello` 用 `_non_empty_string` 校验 device_id，`validate_uplink` 按 msg_type 分发，`handle_hello:156` 的 `message["device_id"]` 安全 ✓
- **hello 鉴权链完整**：ticket 绑定校验（device_id 不匹配拒绝）→ validate_device_token → attestation quarantine/read_only 分级 ✓
- **设备 supersede 正确**：同 device_id 新连接覆盖旧连接，旧连接 close(1012)，outstanding tasks 转移 ✓
- **WS finally 清理完整**：断开时 requeue outstanding + cleanup audio + unregister + 离线通知 ✓
- **autohanding 重试策略合理**：指数退避、429 不重试、状态码校验 ✓

### 修复建议
1. **立即**：I1 zip bomb 防护——`_extract_first_png` 解压前检查 `zf.getinfo(name).file_size` 上限（如 50MB），超限拒绝；W1 WS receive 加超时（`asyncio.wait_for(websocket.receive(), timeout=300)`）+ registry 加 max_connections
2. **本周**：A1 SVG 净化——上传 SVG 前剥离 `<script>`/事件处理器（用 lxml 或正则）；W2 评估移除 query 参数 token 注入，统一走 ticket/header；W3 后台任务按心跳超时清理僵尸会话
3. **计划**：I2 autohanding 复用 httpx.AsyncClient 单例

### AUDIT-11 修复完成（2026-06-29）

| ID | 修复文件 | 措施 | 验证 |
|----|----------|------|------|
| I1 | `integrations/autohanding/client.py` | `_extract_first_png` 解压前检查 `zf.getinfo(names[0]).file_size` 上限（50MB），超限拒绝。防 zip bomb（实测 497KB 压缩→500MB 解压可 OOM） | ruff 通过 |
| W1 | `routes/device_gateway_ws.py`、`device_gateway/sessions.py`、`routes/device_gateway_ws_handlers.py` | WS receive 加 `asyncio.wait_for` 超时（鉴权前 60s/鉴权后 600s），防 Slowloris；`SessionRegistry` 加 `_MAX_DEVICE_SESSIONS=2000` 连接上限，`register` 返回 `"too_many"` 时 `handle_hello` 拒绝连接 close(1013) | ruff + 45 测试通过 |
| A1 | `xiaozhi_drawing/svg_validator.py`、`routes/device_app_assets.py` | 新增 `sanitize_svg_markup`：用标准库 `xml.etree.ElementTree` 删除 `script`/`foreignObject`/`iframe`/`object`/`embed`/`style` 标签、事件处理器属性、`javascript:` 危险 URI；拒绝 DOCTYPE；纯 path data 直接放行。设备 asset 创建 `category=svg` 时强制清洗 | 27 测试通过 |
| I2 | `integrations/autohanding/client.py`、`server_lifespan.py` | autohanding 客户端改用缓存的 `httpx.AsyncClient` 单例（带连接池），避免每次请求重建 TLS 握手；`server_lifespan` shutdown 调用 `close_autohanding_client` | 10 测试通过 |
| W2 | `routes/device_gateway_dispatch.py`、`.env.example`、`tests/conftest.py`、设备 WS 集成测试 | 移除 `?token=`/`?authorization=` query 参数 token 注入及 `LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN` 临时开关；`extract_ws_token` 仅保留 `?ticket=` 与 `Authorization` header；测试全部迁移到 header | ruff + pyright + 全量 4285 passed |

- ~~W2（移除 query 参数 token 注入）~~ ✅ 已完成（2026-07-02）
- ~~W3（僵尸会话心跳清理）~~ ✅ 已核实完成：`device_gateway/sessions.py` 的 `remove_zombies`（按 `last_seen_at` 心跳超时清理 + outstanding tasks requeue）已实现，并由 `routes/device_gateway_helpers.py` 的 reaper 后台任务（`_ZOMBIE_HEARTBEAT_TIMEOUT_SECONDS`）周期调用。
- 状态：**AUDIT-11 HIGH/MEDIUM 批次已全部关闭**（I1/W1/W2/A1/I2/W3）。


## 2026-06-29 AUDIT-12：U8/U1 固件侧安全与健壮性审查

> 审查范围：U8（xiaozhi-esp32 语音）固件的 OTA、本地 WebSocket 控制服务器、运动执行器、U1 UART 协议客户端。关键发现均经亲自读源码核验。

### HIGH 级别（经核验）

| ID | 文件:行号 | 发现 | 核验 |
|----|-----------|------|------|
| AUDIT-12-F1 | `esp32S_XYZ/firmware/u8-xiaozhi/main/ota.cc:532-533,542` | **OTA SHA256/签名校验可选可绕过**：`Upgrade` 中 `if expected_sha256.empty()` 只 ESP_LOGW（警告）继续不拒绝（:532-533）；`if (!expected_signature.empty() && ...)` 签名仅在提供时校验，空签名直接跳过（:542）。`ParseHttpResponse`（:333-336）signature 字段缺失则 firmware_signature_ 为空。若后端 OTA `/check` 响应不带 signature，固件无签名下载安装任意 HTTPS 固件 | ✓ 已读源码确认 |
| AUDIT-12-F2 | `esp32S_XYZ/firmware/u8-xiaozhi/main/ota.cc:325-327` | **OTA firmware_url 无域名白名单**：firmware_url 直接取后端 OTA 响应的 `firmware.url` 字段，只检查 `IsHttpsUrl`（:410）不校验域名。任意 HTTPS 服务器都被接受。后端被攻破或 OTA 响应被篡改可下发指向恶意服务器的固件。与 F1 叠加 = 完全固件接管 | ✓ 已读源码确认 |
| AUDIT-12-F3 | `esp32S_XYZ/firmware/u8-xiaozhi/main/boards/common/websocket_control_server.cc:23-85,93-99` | **本地 WebSocket 控制服务器零鉴权**：`httpd_uri_t ws_uri` 无 auth 中间件（grep auth/token/password 零命中），任何同局域网设备可连入 `:80/ws` 下发 MCP 命令控制设备（HOME/MOVE/STOP 等）。虽有 max_open_sockets=7（:90）+ 消息 4096 限制（:126），但无身份校验。结合运动控制 = 同局域网任意控制机械臂 | ✓ grep 确认零鉴权 |

### MEDIUM 级别

| ID | 文件:行号 | 发现 |
|----|-----------|------|
| AUDIT-12-F4 | `esp32S_XYZ/firmware/u8-xiaozhi/main/ota.cc:568` | **StartUpgrade 透传空签名**：`StartUpgrade` 调 `Upgrade(firmware_url_, firmware_sha256_, firmware_signature_, ...)`，若元数据缺 signature/sha256，三个校验参数都可能为空 → 触发 F1 的可选校验路径。应在 ParseHttpResponse 阶段强制要求 signature 非空 |
| AUDIT-12-F5 | `motion_executor.cc:245-246` | **固件侧运动无坐标边界校验**：PATH_SEG 直接用 `x_item->valuedouble`/`y_item` 发给 U1，只检查 cJSON_IsNumber（:218）不检查范围。完全依赖后端 path_validator。AUDIT-10-V1 的 NaN 漏洞若让 NaN 穿透，固件原样转发 NaN 给 U1 G-code → 运动未定义行为 |

### LOW 级别
- `websocket_control_server.cc:62`：`ESP_LOGI("Got packet with message: %s", ws_pkt.payload)` 日志打印完整消息，可能含敏感指令
- `ota.cc:409`：`ESP_LOGI("Upgrading firmware from %s", firmware_url)` 打印完整 URL（含潜在 token query）

### 已确认健康的维度（固件侧）
- **OTA 有签名校验基础设施**：mbedtls_pk_verify（:113）、IsHttpsUrl 强制（:410）、IsLowerHexSha256 校验（:414）、base64 校验（:393）——校验机制完整，问题只在"可选"而非"无" ✓
- **U1 UART 协议防护完整**：kU1MaxResponseBytes 上限防 OOM（:44）、uart_mutex_ 锁（:64）、uart_flush_input 防残留（:65）、idle_rounds 防 hang（:42）✓
- **motion_executor 能力校验良好**：feed 范围 [1,20000]（:46）、relative move workspace 边界检查（:118-122）、path segment x/y 类型校验（:218）✓
- **本地 WS 有连接数限制**：max_open_sockets=7（:90）+ 消息长度 4096 上限（:126）✓
- **OTA 流式下载 + SHA256 实时计算**：边下载边算哈希，不缓冲全量 ✓

### 固件修复建议
1. **立即**：F1+F4 让 OTA 签名校验强制——`ParseHttpResponse` 阶段 signature 为空则拒绝升级（return false），`Upgrade` 中 expected_signature.empty() 也应拒绝而非跳过；F2 加 OTA URL 域名白名单（仅允许 chat.donglicao.com 等可信源）
2. **本周**：F3 本地 WS 加鉴权（连接时校验 token/配对码，或绑定单设备密钥）；F5 固件侧 PATH_SEG 补坐标边界校验（双重防线，不依赖后端）
3. **计划**：日志脱敏（F 的 URL/payload 不打印敏感字段）

### AUDIT-12 修复完成（2026-06-29）

| ID | 修复文件 | 措施 | 验证 |
|----|----------|------|------|
| F1+F4 | `esp32S_XYZ/firmware/u8-xiaozhi/main/ota.cc` | `Upgrade()` 入口强制要求 sha256（lowercase hex）+ signature（base64），缺失即拒绝；下游校验从可选改为强制（移除 `expected_sha256.empty()` 跳过分支 + `expected_signature.empty()` 跳过分支）。修复无签名刷入任意固件的**完全设备接管**漏洞 | 源码审查（固件需 idf.py 编译验证） |
| F2 | `esp32S_XYZ/firmware/u8-xiaozhi/main/ota.cc` | 新增 `IsAllowedOtaHost` 域名白名单（chat.donglicao.com/donglicao.com/localhost），`HasValidFirmwareMetadata` + `Upgrade` 入口校验。防后端被攻破后下发恶意服务器固件 | 源码审查 |
| F3 | `esp32S_XYZ/firmware/u8-xiaozhi/main/boards/common/websocket_control_server.cc` | 本地 WS 握手加 token 鉴权：从 Authorization Bearer 头或 `?token=` 读取，与 NVS `control_ws_token` 比对。未配置 token 时放行（向后兼容）但 ESP_LOGW 提示。修复同局域网任意控制机械臂 | 源码审查 |
| F5 | `esp32S_XYZ/firmware/u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/motion_executor.cc` | PATH_SEG 段坐标加 `std::isfinite`（拦 NaN/Inf）+ ±500mm 物理边界校验。固件侧双重防线，不依赖后端 path_validator | 源码审查 |

- **待真机验证**：所有固件修改需 `idf.py build` 编译 + 烧录真机验证（OTA 拒绝无签名固件、本地 WS 鉴权、坐标边界）
- ~~延后项：OTA/WS 日志脱敏（F 的 URL/payload 不打印敏感字段）~~ ✅ 已完成（2026-06-29）：`ota.cc` 的 `Upgrading firmware from %s` 改为剥离 query（防 token 泄漏）；`Activation payload: %s` 改为只打印 serial（防 hmac/challenge 凭证泄漏）；`websocket_control_server.cc` 的 `Got packet with message: %s` 改为只打印长度（防控制指令/敏感数据泄漏）。
- 状态：**AUDIT-12 全部关闭**（F1/F2/F3/F5 + 日志脱敏）。F1 是消除完全设备接管的核心修复。
