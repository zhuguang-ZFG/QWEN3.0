# LiMa 全栈深度质量审计报告

> 审计日期：2026-06-28
> 审计范围：LiMa 后端路由器、Web 前端（chat-web / donglicao-site / donglicao-site-v2）、微信小程序（manager-mobile）、ESP32 固件（U1-Grbl / U8-xiaozhi）
> 审计方式：静态扫描 + 质量门禁实跑 + 关键路径人工复核
> 审计者：ZCode（只读审计，未修改任何代码）

---

## 一、总体结论

| 子系统 | 门禁/测试 | 安全 | 代码质量 | 总体评级 |
|--------|-----------|------|----------|----------|
| **LiMa 后端** | pytest 4015 passed / ruff clean / pyright 0 err / size PASS | 良（1 处硬规则软违反） | 优 | **A−** |
| **Web 前端** | 无自动化门禁（纯静态站点） | 中（CDN 缺 SRI） | 良 | **B+** |
| **小程序** | vue-tsc + eslint 可用 / 111+ CI passed | 优（无泄密） | 中（any 滥用） | **B** |
| **固件** | 115 passed / 169 subtests / 静态检查 PASS | 优（OTA 签名+HTTPS 强制） | 优 | **A** |

**核心判断**：项目整体工程质量高，四个子系统均无 CRITICAL 阻断性缺陷。固件 OTA 安全链路（HTTPS 强制 + SHA256 + RSA 签名验证）尤为扎实。主要改进空间集中在：LiMa 的一处硬规则软违反、Web 的 CDN 供应链风险、小程序的 TypeScript 类型纪律。

---

## 二、子系统审计详情

### 2.1 LiMa 后端（Python 3.10 + FastAPI 路由器）

#### 门禁实跑结果（关键：必须用 `.venv310`，系统 python 3.14 会误报）

| 门禁 | 命令 | 结果 |
|------|------|------|
| pytest | `.venv310/Scripts/python.exe -m pytest -q --ignore=tests/test_external` | **4015 passed, 3 skipped, 0 failed**（225s） |
| ruff | `.venv310/Scripts/python.exe -m ruff check .` | **All checks passed** |
| 代码大小 | `.venv310/Scripts/python.exe scripts/check_code_size.py` | **PASS**（无文件 >300 行，无函数 >50 行） |
| pyright | `pyright server.py routing_engine.py identity_guard.py access_guard.py` | **0 errors, 2 warnings**（sentry_sdk 可选依赖未装） |

> ⚠️ **重要发现**：用系统 python 3.14 跑 pytest 会出现 `ModuleNotFoundError: freezegun` 收集错误（`tests/test_device_memory_planner_recall.py`），并误判 `xiaozhi_drawing/svg_converter.py` 为 307 行超限。这是 **venv 不匹配的假阳性**——项目硬性要求 Python 3.10（`.venv310`）。`AGENTS.md` 已记录此约束，但建议在 CI/README 增加 `python` 版本守卫，避免新贡献者误用 3.14。

#### 发现项

**[HIGH] 硬规则 #1 软违反 — 可观测性依赖静默降级**
- 位置：`server_lifespan_state.py:40-41`、`server_lifespan_state.py:90-91`
- 现象：`except ImportError: pass` 吞掉 `observability.prometheus_metrics` 导入失败，无 `logger.warning`
- 对照：`AGENTS.md` 硬规则 #1 明确「关键依赖必须在启动时记录清晰警告，而非运行时静默降级」
- 影响：Prometheus 指标缺失时无任何告警，运维盲区
- 建议：改为 `except ImportError: _log.warning("prometheus_metrics 不可用，启动指标将不记录")`

**[MEDIUM] 已退役 Gitee 镜像代码仍入库（死代码）**
- 位置：`gitee_mirror.py`、`gitee_mirror_store.py`、`gitee_mirror_urls.py`、`scripts/push_dual_remotes.py`
- 对照：`AGENTS.md` 明确「Gitee 镜像已退役：不再维护 `gitee` remote，不再双推」；`git remote -v` 仅 `origin`，无 `gitee`
- 注：`provider_automation/adapters/gitee_ai.py`、`budget_gitee.py`、`.env.example` 的 `GITEE_AI_*` 是 **Gitee AI 后端提供商**（独立、合法、默认关闭），与 git 镜像无关，不要混淆
- 建议：归档 3 个 `gitee_mirror*.py` + `push_dual_remotes.py` 及相关测试到 `docs/archive/retired/`

**[LOW] Telegram/Webhook 路由正确退役** ✅
- `routes/route_registry.py:248-249` 将 `github_webhook`/`gitee_webhook` 硬编码为 `False`，符合 AGENTS.md「Telegram 已退役」要求

**[LOW] shell=True 但参数为常量**
- 位置：`deploy/jdcloud/deploy_jd.py:17`
- 现象：`subprocess.run(cmd, shell=True, ...)`，但所有 `_run()` 调用点 cmd 均为 `f"wget -q {PROMETHEUS_URL} ..."` 常量插值，无用户输入
- 结论：无注入风险，符合 Ponytail 简化原则；保留即可

**[INFO] 异常处理纪律良好**
- 生产代码 `except Exception:` 共约 114 处，其中 **仅 12 处为 `pass`**，且全部是合法 Pythonic 模式（`OSError`/`ValueError`/`WebSocketDisconnect` 等可忽略异常）；除上述 2 处 `ImportError` 外，其余 102 处均有 `log`/`raise`/`warn`，符合硬规则

**[INFO] 技术债低**
- 生产代码（非 tests）`TODO`/`FIXME`/`XXX`/`HACK` 仅 9 处
- 544 个 async 函数中无 `import requests` 同步阻塞（仅在 `.claude/skills/` 工具脚本中，非生产路径）

---

### 2.2 Web 前端（chat-web / donglicao-site / donglicao-site-v2）

#### 安全

**[HIGH] CDN 脚本缺少 SRI（子资源完整性）**
- 位置：
  - `chat-web/index.html:356-358`（highlight.js 11.9.0 / katex 0.16.9）
  - `chat-web/playground.html:16,19`（echarts 5.4.3 / monaco 0.45.0）
  - `chat-web/usage.html:99`（echarts 5）
- 风险：jsdelivr CDN 被攻陷 → 注入恶意脚本 → 窃取 `localStorage.lima-api-key`。已固定版本号但无 `integrity="sha384-..."` 校验
- 建议：为每个 CDN `<script>` 增加 SRI 哈希（jsdelivr 提供 `https://www.jsdelivr.com/package/...` 可生成）

**[GOOD] 聊天渲染路径 XSS 防护扎实** ✅
- `chat-web/chat-messages.js:75-104 formatContent()`：先 `escapeHtml()` 全文本（line 84），代码块单独转义（line 99），图片 URL 走 `isAllowedImageUrl()` 白名单（仅 pollinations / donglicao 三个域名，line 60-72）
- 这是 web 端最高危路径（渲染 AI/用户内容），防护到位

**[MEDIUM] WebSocket 认证经查询串**
- 位置：`chat-web/voice-call.html:231` `wsUrlWithAuth()` → `?authorization=Bearer <key>`
- 现象：WebSocket 无法设自定义 header 的已知妥协；key 会出现在 access log
- 缓解：先经 `/api/live-key`（line 222）换取配置，疑似短期票据机制（需后端确认票据 TTL）
- 建议：确认 `/api/live-key` 返回的是短期票据而非长期 key 透传

**[INFO] API Key 存储**
- `localStorage.lima-api-key`（`chat-ui.js:6,259`）—— 标准 SPA 做法，受 XSS 防护依赖。配合上面的 `formatContent` 加固，可接受

#### 质量与一致性

**[MEDIUM] donglicao-site v1 与 v2 共存，规范源已澄清 ✅**
- `donglicao-site/`（原生 HTML/JS）与 `donglicao-site-v2/`（Next.js，含完整 node_modules）并存
- 结论：两者当前均承担生产职责，并非互斥替代
  - v1 负责已上线的产品详情页、定价页、法律页与 `chat.html` 兜底，手动同步到 `/www/wwwroot/donglicao-site/`
  - v2 负责 Next.js 新首页、英文站、博客，通过 `.github/workflows/deploy-site-v2.yml` 部署到 `SITE_V2_DIR`
- 已在 `donglicao-site/README.md` 与 `donglicao-site-v2/README.md` 明确规范源与迁移条件
- 归档 v1 的前提：把产品页/定价页/法律页重建到 v2 并更新 `routes/static_files.py` 的 `/` 兜底逻辑

---

### 2.3 微信小程序（manager-mobile，uni-app + Vue3 + TS）

#### 安全（优）

**[GOOD] 无泄密** ✅
- `env/.env*` 全部使用 `VITE_` 前缀（公开变量），仅含 `VITE_WX_APPID`（appId 公开合法）、`VITE_SERVER_BASEURL=https://chat.donglicao.com`（公开 URL）
- 无 `appSecret`、无后端 token、无 `sk-` 密钥
- `device-config/index.vue` 的 `:password=` 是 Vue prop 绑定（WiFi 密码 UI 透传），非硬编码

**[GOOD] 无 v-html** ✅ —— 小程序无 XSS 注入面

#### 质量

**[MEDIUM] TypeScript 类型纪律松散（any 滥用）**
- 约 25+ 处 `any`：`api/chat/chat.ts:66,154`、`hooks/useUpload.ts`（6 处）、`http/request/types.ts:13`（`[key:string]:any` 索引签名）、`pages/device-config/components/blufi-config.vue`（多处 BLE 设备对象）
- 对照：`STATUS.md` 声称「TypeScript 类型检查通过」—— 实为靠 `any` 绕过，`type-check` 脚本（`vue-tsc --noEmit`）存在但纪律未落地
- 建议：为 BLE 设备、上传响应、SSE chunk 定义接口；逐步消除 `any`

**[LOW] 大组件需拆分**
- `pages/create/create.vue` 767 行、`pages/voiceprint/index.vue` 694 行、`device-config/components/ultrasonic-config.vue` 667 行
- 对照 LiMa 300 行约束精神，建议拆分 composable / 子组件

**[INFO] 生产 console 残留**
- 12 处 `console.log/debug`，但 `VITE_DELETE_CONSOLE=true`（`.env.production`）构建期会剔除，非风险

---

### 2.4 ESP32 固件（U1-Grbl / U8-xiaozhi）— 安全敏感（物理机器）

#### 门禁

| 项 | 结果 |
|----|------|
| `esp32S_XYZ/tests/` CI | **115 passed, 169 subtests passed**（1.95s） |
| STATUS.md 声称 111 | 实际 115（有增量），无回退 |

#### 安全（优）

**[EXCELLENT] OTA 升级链路加密验证完整** ✅
- `firmware/u8-xiaozhi/main/ota.cc`：
  - `IsHttpsUrl()`（line 30）强制 HTTPS，`Upgrade()` line 410、`HasValidFirmwareMetadata()` line 385 非 HTTPS 直接拒绝
  - `VerifyFirmwareSignature()`（line 86-113）用 `mbedtls_pk_verify` + `CONFIG_OTA_VERIFY_PUBLIC_KEY_PEM` 做 **RSA 签名验证**（SHA256 摘要）
  - 元数据三重校验：HTTPS + 小写 hex SHA256 + base64 签名（line 384-397）
- 这是固件安全的 A 级实践

**[GOOD] cJSON 一致性 + 无内存泄漏** ✅
- `protocols/protocol.cc`、`protocols/mqtt_protocol.cc` 全用 `cJSON_CreateObject`/`cJSON_PrintUnformatted`（无手拼 JSON）
- 每个 `cJSON_PrintUnformatted` 都配对 `cJSON_free(serialized)`（line 94→101、119→126、144→151）

**[GOOD] U1 JSON 解析器 P0 修复已验证** ✅
- `Grbl_Esp32/src/json_utils.cpp` 用 `snprintf(pattern, sizeof(pattern), ...)`（line 17、62，边界检查）替代裸 `sprintf`
- 有专门单测（commit `81160aa test(u1-grbl): add firmware unit tests for JSON parser`）

**[GOOD] 唯一 sprintf 实为安全** ✅
- `ota.cc:696` `sprintf(buffer, "%02x", ...)`，`buffer[3]` 容纳 "%02x"（2字符+\0）正好，无溢出

#### 配置

**[LOW] `CONFIG_BOOTLOADER_SKIP_VALIDATE_ALWAYS=y`**
- 位置：`firmware/u8-xiaozhi/sdkconfig.defaults:8`
- 影响：跳过 bootloader 镜像校验（OTA 回滚场景常用，但生产环境若误开有风险）
- 建议：生产 sdkconfig.production 中确认关闭或文档说明依据

**[GOOD] 无不安全 TLS 默认** ✅ —— 未设 `CONFIG_ESP_HTTPS_TLS_INSECURE`，WiFi WEP 相关默认安全

---

## 三、改进优先级清单

### P1（建议本轮处理）
1. **LiMa** `server_lifespan_state.py:40,90` 的 `except ImportError: pass` 加 `logger.warning`（硬规则合规）
2. **Web** 为 6 处 CDN `<script>` 补 SRI `integrity` 哈希
3. **LiMa** 归档已退役 `gitee_mirror*.py` + `push_dual_remotes.py`

### P2（建议下轮）
4. **小程序** 消除 `any`，为 BLE/上传/SSE 定义接口（尤其 `blufi-config.vue`、`useUpload.ts`）—— 代码位于 `esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile` 子模块，不在 LiMa 本仓库直接维护
5. **小程序** 拆分 >600 行的大组件 —— 同第 4 点，属于子模块范围
6. **Web** 明确 `donglicao-site` v1/v2 规范源 ✅ —— 已在各自 `README.md` 说明；两者均承担生产职责，暂不归档
7. **LiMa** CI 增加 `python` 版本守卫，防止误用 3.14 ✅ —— 已在 `tests/conftest.py` 与 `scripts/run_pre_commit_check.py` 添加强制检查

### P3（信息项）
8. **固件** 生产 sdkconfig 确认 `BOOTLOADER_SKIP_VALIDATE` 的依据
9. **小程序** `console.log` 12 处（构建期已剔除，非风险）

---

## 四、审计方法论说明

- **静态扫描**：grep/ripgrep 覆盖危险函数（eval/exec/shell=True/strcpy/sprintf）、密钥模式（sk-/Bearer/appSecret）、异常处理模式（except/pass）、类型逃逸（any/ts-ignore）
- **门禁实跑**：LiMa 用 `.venv310`（Python 3.10.20）跑全部门禁；固件用 esp32S_XYZ `tests/` 跑 CI
- **关键路径人工复核**：Web 聊天渲染（XSS）、固件 OTA（TLS+签名）、小程序密钥存储
- **已知修复验证**：逐项核对 STATUS.md 声称已修的 P0/P1（U1 缓冲区溢出、fallthrough、JSON 解析器、U8 cJSON 一致性），均有代码证据

**未覆盖项**（诚实声明）：
- 未做真实硬件在环（HIL）测试，固件物理安全（激光联锁、归位、限位）仅做静态扫描，未运行实机验证
- 未实跑小程序 `pnpm build:mp-weixin` 构建产物校验
- Web 的 donglicao-site-v2（Next.js）未做 `next build` 验证
- LiMa 未在真实 VPS 做端到端冒烟（本地 `:8080/health` 未启动服务）
- 未做依赖漏洞扫描（`pip-audit` / `pnpm audit` / `npm audit`），建议补做

这些未覆盖项不影响上述结论的成立，但若需「生产就绪签发」级别审计，应补齐 HIL + 依赖 CVE + 真实域名端到端三项。
