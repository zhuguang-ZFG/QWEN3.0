# LiMa Status

> **导航**：2026-07-02 起，旧的 5 份战略规划文档（PROJECT_DEFECTS_AND_IMPROVEMENT_PLAN_CN / LIMA_IMPROVEMENT_PLAN_20260625_V2 / PROJECT_OPTIMIZATION_ROADMAP_CN / DEEP_QUALITY_AUDIT_CN / OPTIMIZATION_ANALYSIS_2026-06-23）已归档至 `docs/archive/strategic-plans-2026-06/`。当前活动瘦身/优化计划见 `docs/superpowers/specs/2026-07-02-system-slimdown-design.md`。本文件历史日志中出现的旧文档名仍指向其归档位置（文件名未变，仅路径前缀变更）。

> **项目定位**: AI 智能设备统一云端服务（2026-06-09 战略转型完成）
> **技术栈**: Python 3.10 + FastAPI + SQLite + Redis
> **公网端点**: chat.donglicao.com（主入口）；api.donglicao.com 为京东云 NewAPI 反代，非 LiMa Server 直接入口
> **部署**: 主计算与公网入口在 JDCloud (`117.72.118.95`)；Cloudflare Tunnel 指向京东云本地 nginx（`https://127.0.0.1:443`），由 nginx 路由 API/静态资源。阿里云 `47.112.162.80` 已部署 `lima-router-pilot` 作为辅助节点，仅处理免费/低价后端流量（`aliyun.donglicao.com`）。chat-web、官网 playground、manager-mobile H5 的匿名简单聊天请求已分流到阿里云 pilot。`api.donglicao.com` 为京东云 NewAPI 反代，非 LiMa Server 直接入口。

> Updated: 2026-07-04
> Branch: `main`
> Scale: 约 1180 个 Python 文件 / 130,950 行（2026-06-28 图片模块拆分后）
> Tests: 全量 **4463 passed / 3 skipped / 2 deselected / 0 failed / 2 warnings**（`.venv310` Python 3.10.20）；ruff check clean（含 F401 全局 gate 已启用）；ruff format clean；pyright 目标文件 0 errors；小程序 `vue-tsc` + `uni build` 通过；manager-mobile `vitest` 用例 GREEN。
> 注意：使用系统 Python 3.14 直接运行 `python -m pytest` 会被 `tests/conftest.py` 的 Python 版本 guard 拒绝，这不是 FastAPI/Pydantic 兼容问题，而是 LiMa 仅支持 Python 3.10。已安装 `pytest-timeout`；`httpx2` 已从 `requirements_dev.txt` 移除，功能测试正常，仅保留 starlette testclient 的 deprecation warning。
> 英文站：...（保持不变）
> ⚠️ 运维警示：主 VPS 磁盘已从 98% 降至 **67%**（40G 中 25G 已用，释放约 5G），`litestream` 已纳入 systemd 管理并设置 `MemoryMax=512M`，内存可用约 420M~850M（随负载波动），load average 4~5。京东云节点已完成深度清理（磁盘 33% → **30%**，59G 中 17G 已用，释放约 2G）。登录超时风险显著降低。
> Code Size: **0 个 >300 行文件、0 个 >50 行函数**；`scripts/check_code_size.py` PASS。
> pyright 目标文件 0 errors（sandbox 下仅历史 warning）
> CI/CD：`.github/workflows/test.yml` ✅、`.github/workflows/deploy.yml` ✅、`.github/workflows/deploy-site-v2.yml` ✅、`.github/workflows/deploy-docs-site.yml` ✅（全部绿灯）；自动部署 Aliyun + chat-web + JDCloud + 官网/docs 站流程已就绪（secrets 待配置）。
> Git 镜像：Gitee 镜像已退役，仅维护 GitHub `origin`。
> 安全审计：`findings.md` AUDIT-1 CRITICAL + HIGH 批次已修复部署（C1/C2/C3 + H1~H6）；2026-06-25 全量 pytest 修复项已 Closed；历史 2026-06-18 全量审计安全项已全部 Closed / Accepted。
> 匿名访问：生产环境已允许 `LIMA_ALLOW_ANONYMOUS=1`，`https://chat.donglicao.com/` 无需 API Key 即可聊天。

### 最近完成（2026-07-04）D1~D4 延后债务清理（M4 尾款）

- **范围**：清理 M4 遗留的 4 项延后债务，全部闭环。
- **D4 固件 native 单测 CI 首跑验证**：修复因 P3.1 composable 提取 + P3.3 timeout 常量化导致的 `tests/ci/test_manager_mobile_device_info.py` 断言失效（旧断言只读 `index.vue`，逻辑已迁至 composable；`timeout: 15000` → `SOFTAP_SUBMIT_TIMEOUT_MS`）。测试改为读取 `index.vue` + composable 文件拼接串校验，本地 pytest **23/23 PASS**；确认 CI `firmware-native-tests` job 历史绿灯（U8 OTA/MQTT native 单测已跑通）。
- **D1 `chat/chat.vue` 拆分**：635 → **130 行**，提取 `useChatMessages`（历史/存储）+ `useChatStream`（流式+中断+重生成）+ `useChatHelpers`（滚动/时间/markdown/长按/复制）+ 独立 `chat.scss`。模板/样式与原始逐字节一致（diff 验证）。
- **D2 `index/index.vue` 拆分**：604 → **238 行**，提取 `useHomeData`（设备/任务加载+派生）+ `useHomeNavigation`（8 个跳转）+ `useTaskFormatters`（任务状态 label/color/progress）+ 独立 `index.scss`。模板/样式逐字节一致。
- **D3 Chat Web `styles.css` 按页面拆分**：2060 行 → 5 文件（`css/common.css` 全局重置/滚动条/焦点/微交互、`css/chat.css` 聊天页、`css/playground.css`、`css/auth.css` 登录/注册、`css/pages.css` keys/usage/devices/handwriting）。`hash-assets.mjs` 适配 `css/` 目录哈希；`deploy_chat_web.py` FILES 换为 5 个 CSS。9 个 HTML 按需引用（common + 页面专属）。
- **门禁**：小程序 `vue-tsc` + `uni build` + `vitest`(4) + `check-i18n`(803) 全绿；后端 CI 镜像测试 23/23 PASS；Chat Web esbuild 构建通过（23 assets minified）。
- **小程序**：版本 `3.8.6` → `3.8.7`，微信开发者工具 CLI 上传成功（1.2 MB）。
- **部署**：Chat Web `deploy_chat_web.py` 成功，origin 5 个 CSS + 新 HTML 全 200（`--resolve` 绕 CDN 验证）；旧 `styles.css`(68KB) 保留在 origin 作为 CDN 缓存 HTML 的兜底，Cloudflare ~4h 缓存窗口内新旧两态均可用，无断链。
- **提交**：子模块 `esp32S_XYZ` `f785da5` 已 push；主仓库更新子模块指针 + Chat Web CSS 拆分 + 构建/部署脚本 + 文档同步。

### 最近完成（2026-07-04）M4 全项目 P3 重构/技术债

- **范围**：承接 M3，完成小程序、Chat Web、固件共 6 项 P3 重构/技术债（+2 项延后为债务，已由上方 D1~D4 清理）。
- **P3 已修复**：小程序超时魔法数字统一到 `src/config/timeouts.ts`（8 常量）；非微信端流式完整实现（`fetch` + `getReader` + `AbortController`，替换 P0.4 fail-loud 占位）；3 个超大组件拆分（`device-detail` 761→331、`voiceprint` 691→399、`ultrasonic-config` 667→266，提取 7 个 composable + 1 个纯函数模块）；Chat Web `escapeHtml`/`escapeAttr`/`isAllowedImageUrl` 7 处重复收敛到 `js/utils.js` + esbuild 0.25.12 压缩（styles.css 68KB→49KB）；固件新增 U8 OTA 白名单 + MQTT hex 解码 native 单测（35 用例）并接入 CI；i18n 校验 + vitest 接入 CI `manager-mobile-tests` job。
- **门禁**：`pytest -q` → **4463 passed / 3 skipped / 2 deselected / 0 failed**；`ruff check .` clean；小程序 `vue-tsc` + `uni build` + `vitest`(4) + `check-i18n`(803) 全绿；Chat Web esbuild 构建通过（19 assets minified）。固件 native 单测未本地编译（按决策「只加代码不本地验证」，依赖 CI 首跑）。
- **小程序**：版本 `3.8.5` → `3.8.6`，微信开发者工具 CLI 上传成功（1.2 MB）。
- **延后债务**（均已在 2026-07-04 D1~D4 清理完成）：`chat/chat.vue`(635) 与 `index/index.vue`(604) 拆分；Chat Web `styles.css`(2060 行) 按页面拆分；固件 native 单测 CI 首跑验证。
- **提交**：子模块 `esp32S_XYZ` `223bef7` 已 push；LiMa 主仓库更新子模块指针 + Chat Web 改动 + 文档同步。

### 最近完成（2026-07-03）M3 全项目 P2 LOW 技术债/体验打磨

- **范围**：承接 M2，完成后端（Python/FastAPI）、Chat Web、微信小程序、ESP32 固件（U1/U8）共 15 项 P2 LOW 技术债/体验打磨。
- **P2 已修复**：`http_caller` 重导出符号完整性测试（30 用例）；`probe_loop`/`backend_probe_loop` docstring 交叉引用；`.env.example` 占位密钥去敏化；移除 `requirements_dev.txt` 中 `httpx2`（改用 httpx testclient）；小程序 `tabbarList` TODO + `utils` 注释 console 清理；抽公共 `getMode()` 到 `scripts/get-mode.ts`；子模块移除 `unpackage/res/icons/*.png` 并加 `.gitignore`；压缩主包 `1024x1024.png`；`deploy_chat_web.py` FILES 加 `_headers`（HSTS）；新增 `scripts/check-i18n-keys.mjs`（803 keys 一致性校验）；U1 固件 `min_spiffs.csv` 分区表入库；U8 固件 `sdkconfig.defaults` 默认日志级别 INFO；`docs/getting-started.md` 清理 manager-api/Java 残留；小程序移除未用 `@tanstack/vue-query`、8 个非目标 `uni-mp-*` 平台包及 macOS 专用 darwin 构建包。
- **门禁**：`pytest -q` → **4463 passed / 3 skipped / 2 deselected / 0 failed**；`ruff check` / `ruff format --check` clean；`check_code_size.py` PASS；`pyright` 改动文件 0 errors；小程序 `vue-tsc` + `uni build` 通过；`pnpm test`（vitest）4 passed；`check-i18n-keys.mjs` OK。固件 `pio run`/`idf.py build` 因本机工具链损坏/缺失未执行，改动为低风险配置，后续在完整固件环境补跑。
- **小程序**：版本 `3.8.3` → `3.8.5`，微信开发者工具 CLI 上传成功。清理未用依赖后 `miniprogram-ci` 上传因 `@babel/helper-compilation-targets` 解析到 `lru-cache@11`（应为 `@5`）而报 `_lruCache is not a constructor`；已在 `pnpm-workspace.yaml` 增加 `@babel/helper-compilation-targets>lru-cache: ^5.1.1` override 修复并重新上传（v3.8.5）。
- **提交**：子模块 `esp32S_XYZ` 已 push origin main；LiMa 主仓库更新子模块指针并提交后端/脚本/文档改动。

### 最近完成（2026-07-03）M2 全项目 P1 MEDIUM 质量/文档/测试改进

- **范围**：承接 M1，完成后端（Python/FastAPI）、Chat Web、微信小程序、ESP32 固件（U1/U8）共 15 项 P1 MEDIUM 改进。
- **P1 已修复**：后端静默降级日志级别提升；Chat Web 域名配置收敛 + `deploy_chat_web.py` 远程目录自动创建；小程序类型债务/死代码/alova 统一/urlCheck；U8/U1 固件清理与 schema 版本管理；manager-mobile 引入 vitest 纯函数测试。
- **门禁**：`pytest -q` → **4433 passed / 3 skipped / 2 deselected / 0 failed**；`ruff check` / `ruff format --check` clean；`check_code_size.py` PASS；`pyright` 改动文件 0 errors；小程序 `vue-tsc` + `uni build` 通过；vitest `deepClone` 测试通过。
- **VPS**：主后端 `deploy_unified.py --target aliyun --slice core` 成功，Health OK；Chat Web `deploy_chat_web.py` 修复后成功，nginx reload OK。
- **小程序**：版本 `3.8.2` → `3.8.3`，微信开发者工具 CLI 上传成功（989.2 KB）。
- **提交**：子模块 `esp32S_XYZ` 已 push origin main；LiMa 主仓库将更新子模块指针并提交 `scripts/deploy_chat_web.py` 修复。
- **计划**：M3（P2 LOW）待推进，见 `docs/superpowers/specs/2026-07-03-full-project-improvement-plan.md`。

### 最近完成（2026-07-03）M1 全项目安全/正确性修复 + Aliyun 部署

- **审计范围**：后端 Python/FastAPI + Chat Web + 微信小程序 + ESP32 固件（U1/U8），落盘 `docs/superpowers/specs/2026-07-03-full-project-improvement-plan.md`。
- **P0 已修复**：小程序 NODE_ENV / vite env 泄露 / 非微信流式 fail-loud；Chat Web 图片 URL 白名单；后端 `xiaozhi_drawing/pipeline.py` 静默降级；CI 静默降级门禁扩展；U1 默认禁用 WebUI OTA；U8 端点白名单；固件服务端残留文档清理。
- **门禁**：`pytest -q` → **4433 passed / 3 skipped / 2 deselected / 0 failed**；`ruff check` / `ruff format --check` clean；`check_code_size.py` PASS；`pyright` 改动文件 0 errors；小程序 `vue-tsc` + `uni build` 通过。
- **VPS**：`deploy_unified.py --target aliyun --slice core` 成功，Health OK；`deploy_chat_web.py` 因远程 `/var/www/chat` 目录缺失失败，已记录为 M1 遗留项。
- **提交**：主仓库 + 子模块 `esp32S_XYZ` 均已 push origin main。

### 最近完成（2026-07-02）全量门禁 + 京东云生产部署 + 公网冒烟验证

- **本地全量门禁**：`run_pre_commit_check.py --full` → 4388 passed / 3 skipped / 2 deselected；ruff clean。
- **VPS 部署**：`deploy_unified.py --target jdcloud --slice core` → 883 文件上传 / 0 失败。tar/scp 回退 SFTP 成功。服务重启 Health OK。
- **公网冒烟**：`/health` ok ✅、`/health/ready` ready ✅、`POST /v1/chat/completions`（匿名）→ 200 `cfai_qwen_coder` + 记忆召回 ✅、`/device/v1/app/voice/ticket` → 405 端点可达 ✅。

### 最近完成（2026-07-02）语音端点部署到京东云主生产节点

- **背景**：`deploy_unified.py` 默认连阿里云（LIMA_SERVER=47.112.162.80），但公网入口在京东云（117.72.118.95）。首次部署误打到阿里云，公网 `chat.donglicao.com/device/v1/app/voice/*` 返回 404。
- **修正**：SSH 到京东云（root 密码凭据），sftp 上传 `routes/device_app_voice.py`（新）+ `routes/route_registry.py`（加注册行），备份原 route_registry，清 pyc 缓存，`systemctl restart lima-router`。
- **冒烟验证（公网）**：`/voice/ticket` → 401（鉴权生效）；`/voice/transcribe` → 422（UploadFile 字段校验生效）。不再是 404，端点真实可达。
- **教训/修复**：`deploy_unified.py` 已新增 `--target {aliyun,jdcloud}` 参数，默认 **jdcloud**（生产入口），并新增 `DeployTarget` 值对象贯穿 preflight/backup/deploy/restart/nginx 全流程。支持环境变量 `LIMA_DEPLOY_TARGET`、`LIMA_ALIYUN_PASSWORD`、`LIMA_JDCLOUD_ROOT_PASSWORD`。 dry-run 验证已可正确区分 117.72.118.95 与 47.112.162.80。

### 最近完成（2026-07-02）语音控制检修（自检发现并修复 4 个 bug）

- **BUG-1（M2 frameSize 单位错误）**：`useVoiceStream` 的 `frameSize: 1` 实为 1KB（uni-app 单位是 KB），导致回调风暴且与注释不符。改为 `5`（5KB，对齐后端 FRAME_BYTES）。
- **BUG-2（M0 错误信息泄漏）**：`/voice/transcribe` 失败时把 `{exc}` 拼进返回给客户端的 message（可能含内部地址/堆栈）。改为通用 message，详情只进日志。测试强化为同时断言「不泄漏 mock 异常字符串」。
- **ISSUE-4（M1/M2 意图不一致）**：M1 走后端 `resolve_voice_task`（未知输入默认 write_text），M2 走前端 `frontendIntent`（原默认 draw_generated）—— 同一段语音两模式给出不同意图。前端 fallback 对齐到 write_text。
- **MINOR-7（死代码）**：`StreamStatus` 的 `finalizing` 定义了但从未设置，移除。
- 重新 `build:mp-weixin` + 重新上传微信 v3.8.0（覆盖含 BUG-1 的旧上传）。type-check + 10 后端测试 + ruff + pyright 全过。

### 最近完成（2026-07-02）小程序语音控制绘图机/写字机（M0+M1+M2）

- **需求**：小程序端补齐语音交互，用语音驱动绘图机（draw_generated）/写字机（write_text）。
- **M0 后端**：新增 `routes/device_app_voice.py`（2 端点，82 行薄包装）：
  - `POST /device/v1/app/voice/transcribe`：上传音频 → `get_asr_provider().transcribe` + `resolve_voice_task` → 返回 `{text, intent}`，不派发任务（前端确认后才派发）。剥 WAV RIFF header 取 raw PCM（ASR 期望 16-bit LE mono）。
  - `POST /device/v1/app/voice/ticket`：`ws_ticket.issue()` 签发一次性 WS 票据供 M2 实时流用。
  - TDD：`tests/test_device_app_voice.py` 10 用例全绿；ruff/pyright/check_code_size 通过。
- **M1 小程序按住说话**：`api/voice/voice.ts` + `useVoiceCommand` composable + `voice-command.vue`（确认对话框：可编辑文本/一键切绘图↔写字/派发前强制人工关卡）。复用 `v2SubmitTask`。
- **M2 小程序实时流**：`useVoiceStream` composable 复用 `/v1/voice` WS（只取 transcript 帧，忽略 LLM/TTS），边说边显，松开进同一确认对话框。
- **收尾**：`vue-tsc` type-check 通过；版本 3.7.0→3.8.0（380）；`build:mp-weixin` 成功；微信 CLI 上传成功（1.1MB）；子模块指针已更新。
- **设计文档**：`docs/superpowers/specs/2026-07-02-mini-program-voice-draw-design.md`。

### 最近完成（2026-07-02）系统瘦身（先做减法）

- 四维度过度设计审查后，落地安全瘦身：删手机号鉴权死端点（P2-16，净删 210 行）、U1 固件关 WiFi 编译（P0-2）、5 份重叠战略文档归档（P1-9）、修断链/DEPRECATED 误标/STATUS 矛盾/模块数（43→17）。
- 执行中发现并如实纠正审查报告 5 处误判（`speculative_policy` 是热路径非死代码、98MB node_modules 未入库、progress.md 全在近 3 天等）。
- 记录 P0-3 U8 音频协议 bug（OPUS 发送 vs PCM 声明），待硬件决策排期。

### 最近完成（2026-07-02）AUDIT-11-W2 移除设备 WS query 参数 token 注入

- **实现**：`routes/device_gateway_dispatch.py:extract_ws_token` 彻底移除 `?token=`/`?authorization=` query 参数分支及 `LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN` 临时开关，仅保留 `?ticket=` 与 `Authorization` header；`.env.example`、`tests/conftest.py`、相关单元/集成测试同步清理；`docs/DEVICE_WS_TOKEN_DEPRECATION_CN.md` 更新为 Phase 2 完成。
- **验证**：设备 WS 聚焦测试 71 passed / 1 skipped；全量 `4285 passed, 3 skipped, 2 deselected`；ruff / pyright / code size 均通过；`grep` 确认无遗留 `?token=` 与 env 开关。

### 最近完成（2026-07-02）AUDIT-6-A1 OpenAPI 文档开关测试补齐

- **实现**：新增 `tests/test_server_docs_disabled.py`，默认环境断言 `/docs`、`/redoc`、`/openapi.json` 返回 404；`LIMA_DOCS_ENABLED=1` 时断言返回 200。使用子进程隔离避免污染全局 `app`。
- **验证**：全量 `4285 passed, 3 skipped, 2 deselected`；ruff / pyright / code size 均通过。

### 最近完成（2026-07-01）修复 CI `Tests` workflow 回归

- **背景**：合并 dependabot PR 后 GitHub `Tests` workflow 仍失败 18 个；本地 `scripts/run_pre_commit_check.py --ci --full` 复现。
- **根因 1**：`fastapi>=0.138.2` 引入 `_IncludedRouter`，`server.app.routes` 不再直接暴露 `APIRoute` 叶子对象，路由内省类测试批量失败。
  - 修复：`requirements_server.txt` / `deploy/jdcloud/jdcloud-worker-requirements.txt` 的 FastAPI 范围收紧为 `>=0.136.1,<0.136.3`（排除恶意 0.136.3 同时避开 0.138.x），保留 `starlette>=1.3.1`。
- **根因 2**：`device_gateway/path_validator.py` 对 `write_text`/`draw_generated`/`handwriting` 会丢弃已生成的 `path`，导致 5 个设备任务测试失败。
  - 修复：新增 `_maybe_preserve_path()`，存在有效 path 时校验并保留。
- **验证**：本地全量 `4273 passed`；GitHub Actions `Tests` workflow 已恢复绿灯；`pip-audit` clean。

### 最近完成（2026-07-01）chat-web 匿名聊天分流到阿里云 pilot

- **目标**：让 `app.donglicao.com` / `chat.donglicao.com/chat/` 的匿名简单聊天请求由阿里云 `lima-router-pilot`（仅免费后端）处理。
- **实现**：
  - 新增 `chat-web/js/app-config.js`：运行时判断无 API Key + 默认模型 `lima`/`lima-1.3` + 无 tools/图片时，使用 `https://aliyun.donglicao.com`。
  - `chat-web/chat-api.js` 的 `sendMessage()` / `generateImage()` 统一通过 `LiMaConfig.getApiUrl()` 获取 endpoint。
  - `chat-web/index.html` CSP `connect-src` 增加 `https://aliyun.donglicao.com`。
  - `.gitignore` 增加 `chat-web/dist/`（由 `hash-assets.mjs` 生成）。
- **部署**：
  - GitHub Actions `Deploy Chat Web` workflow 自动构建 hashed assets 并部署到 Cloudflare Pages（`app.donglicao.com`）。
  - 京东云 `/opt/lima-router/chat-web` 源文件通过 `deploy_unified.py --files` 同步，作为 FastAPI `/chat/` 静态回源。
- **验证**：
  - `https://app.donglicao.com/` 返回 HTML 包含 `js/app-config.<hash>.js`，CSP 允许 `aliyun.donglicao.com`。
  - 直接 POST `aliyun.donglicao.com/v1/chat/completions`（Origin: chat.donglicao.com）返回 200，后端 `pollinations_openai`，CORS 正常。
- **后续**：manager-mobile / 官网 playground 的分流按需扩展；建议前端增加 pilot 失败时自动回退主节点。

### 最近完成（2026-07-01）修复 dependabot moderate 漏洞

- **漏洞**：`deploy/jdcloud/jdcloud-worker-requirements.txt` 存在 9 个已知漏洞：
  - `python-dotenv==1.0.1` → CVE-2026-28684
  - `starlette==0.41.3`（fastapi 0.115.6 传递）→ CVE-2025-54121、CVE-2025-62727、CVE-2026-48817/48818 等
- **修复**：将 JDCloud worker 依赖与主 `requirements_server.txt` 安全版本对齐：
  - `fastapi>=0.136.1,<0.136.3`（后续从 `0.138.2` 回退，因 0.138.x 的 `_IncludedRouter` 破坏路由内省测试；仍排除恶意 0.136.3）
  - `starlette>=1.3.1`（覆盖 CVE-2026-54282/54283）
  - `uvicorn[standard]~=0.49.0`
  - `httpx~=0.28.0`
  - `python-dotenv~=1.2.2`
- **验证**：
  - `pip-audit` 扫描修复后 manifest：**0 vulnerabilities**
  - `tests/test_jdcloud_worker.py`：**19 passed**
  - 京东云 VPS `/opt/lima-worker/venv` 已升级并重启服务，`jdcloud-worker.service` active，`/health` 返回 `{"status":"ok"}`
  - 后续 `git push` 不再出现 Dependabot 漏洞提示；本地所有 requirements manifest 扫描均 clean

### 最近完成（2026-07-01）设备 App 图片绘画与图生图能力闭环

- **目标**：把小程序「AI 创作」页面简化为绘画-only，支持文生图、图生图和图片直绘；参考图统一存到 Telegram 素材库。
- **后端**：
  - 新增 `integrations/telegram_bot/client.py`：封装 Telegram Bot 发送图片、获取公开 URL、健康检查；所有请求使用 `trust_env=False` 避免被系统代理干扰。
  - 新增 `device_gateway/gallery_store.py`：SQLite 记录用户素材库（account_id、file_id、thumb_url）。
  - 新增 `routes/device_app_gallery.py`：`/device/v1/app/gallery` 上传/列表/删除/刷新 URL。
  - 扩展 `routes/device_app_images.py`：`/device/v1/app/images/generations` 支持 `image_url` 图生图；复用 `/device/v1/app/devices/{id}/tasks` 的 `draw_generated` capability 下发图片绘画任务。
  - 新增/更新单测：`tests/test_device_app_gallery_*.py`、`tests/test_device_app_images.py`、`tests/test_device_app_tasks.py`；相关测试 56 passed。
- **前端（manager-mobile）**：
  - 重写 `pages/create/create.vue`：移除写字/仿手写，仅保留「AI 绘画」（文生图/图生图）和「图片绘画」。
  - 新增 `pages/create/components/image-picker.vue`：支持相册上传（自动进素材库）和素材库选择。
  - 新增 `api/gallery` 封装；扩展 `api/images` 支持 `image_url`。
  - `pages/index/index.vue` 入口同步调整：第二卡由「AI 写字」改为「图片绘画」。
  - `pnpm run type-check` 通过。
- **部署与验证（京东云 117.72.118.95）**：
  - 部署 Cloudflare Worker 代理 `https://telegram-proxy.donglicao.com` 转发 Telegram Bot API。
  - VPS `.env` 追加 `TELEGRAM_BOT_TOKEN` 与 `TELEGRAM_GALLERY_CHAT_ID`。
  - 端到端验证通过：gallery 上传返回 `fileId`/`thumbUrl`、图生图、图片绘画任务创建均成功。
  - H5 演示部署：manager-mobile 以 `VITE_APP_PUBLIC_BASE=/mobile/` 构建，上传到 `/var/www/chat/mobile/`；nginx 新增 `location ^~ /mobile/` SPA 规则。
  - 演示地址：`https://chat.donglicao.com/mobile/`（浏览器访问，同域调用后端 API）。
- **配置**：`.env.example` 新增 `TELEGRAM_BOT_TOKEN` 与 `TELEGRAM_GALLERY_CHAT_ID`。
- **门禁**：聚焦测试 56 passed；ruff clean；pyright 0 errors。
> 历史归档：2026-06-30 及更早「最近完成」条目 → [`docs/archive/status-log-2026-06.md`](docs/archive/status-log-2026-06.md)

## 退役模块

| 模块 | 状态 | 说明 |
|------|------|------|
| LiMa Code CLI (deepcode-cli) | ✅ 已退役 | 子模块已移除 |
| Telegram bot/operator（通知通道） | ✅ 已退役 | 旧的路由/webhook/出站通知已移除。注意：Telegram Bot API 后来（2026-07-01）被复用为 gallery 图片存储后端，两者是不同用途，见「最近完成」 |
| WeChat 集成 | ✅ 已退役 | 桥接代码已归档 |
| agent_runtime 路由 | ✅ 已退役 | HTTP 路由已移除 |
| Anthropic `/v1/messages` 兼容层 | ✅ 已退役 | 端点与转换函数已移除 |
| channel_gateway（WeChat 绑定层） | ✅ 已退役 | 2026-06-17；23 文件 + 路由 + 13 测试删除；`channel_retirement.py` 标记 |

## 部署状态

- **主 VPS**: Alibaba Cloud 47.112.162.80
- **备用节点**: JDCloud 117.72.118.95
- **公网健康检查**: chat.donglicao.com/health = 200（2026-06-16 19:15 恢复；此前因 `device_ledger.store` 缺失 `configure_ledger_store_from_env` 导致 systemd 反复崩溃）
- **设备网关**: chat.donglicao.com/device/v1/health = 200
- **VPS 启动耗时**: 约 8 秒（`server_lifespan` 关键阶段完成后即可 ready；warm 阶段在后台异步运行）
- **最近恢复操作**:
  - 2026-06-22（文档与部署修复）：重写根 README；刷新 STATUS、docs/DEPLOY_AND_RELEASE_CONVENTION.md、docs/ARCHITECTURE.md、docs/README.md；删除未跟踪 `coverage_output.txt`；修复本地部署密钥损坏问题，生成 `~/.ssh/lima_deploy_ed25519` 并配置 `.env`；简化命令 `python scripts/deploy_unified.py --slice core` 成功部署 1372 文件，health OK。
  - 2026-06-22（代码审查修复）：按优先级修复 `.omk/CODE_REVIEW_ISSUES.md` 中 7 项问题；全量 pytest 2319 passed / 18 skipped / 0 failed；commit `2b918322`、`f05c6f92` push 成功。
  - 2026-06-22：修复 `lima_mcp_stdio/lima_code_query_mcp.py` 静默降级与 chroma `FileRecord` 类型误用；拆分其过长 `handle_request` 及 5 个其他 `long_function`（architecture doc、audio pipeline、ASR/VAD/transcribe、memory consolidation）；修复 `scripts/deploy_unified_preflight.py` 大文件列表备份命令行超长问题；VPS 两次全量部署 2374 文件均成功，backup `/opt/lima-router/backups/unified-core-20260622_070210/runtime-before.tgz`，Health OK，`verify_production_deploy.py` PASS；补全 `device_logic/rate_limit.py`、`tool_gateway/audit.py`、`tool_gateway/governance.py` 单元测试共 44 例，guardian 报告清零（0 错误 / 0 警告 / 0 提示）；移除 Gitee remote 与相关 SSH 配置，仅保留 GitHub `origin`；将 `.guardian/` 和 `ARCHITECTURE_KNOWLEDGE.md` 加入 `.gitignore` 并从索引移除已跟踪的 guardian 文件；`esp32S_XYZ` submodule 有大量未提交修改待用户决定。
  - 2026-06-21：部署 15 个 store/memory/notifier/gateway/lifespan 文件，备份 `/opt/lima-router/backups/unified-files-20260616_190649/runtime-before.tgz`

## 静态站点托管

| 站点 | 域名 | 托管位置 | 状态 |
|------|------|----------|------|
| 文档站 | `docs.donglicao.com` | Cloudflare Pages (`lima-docs`) | ✅ 200 OK |
| 官网 v2 | `www.donglicao.com` | Cloudflare Pages (`lima-www`) | ✅ 200 OK |
| Chat Web | `app.donglicao.com` | Cloudflare Pages (`lima-chat-web`) | ✅ 200 OK；API 指向 `chat.donglicao.com` |

- **自动化部署**：`.github/workflows/deploy-{docs-site,site-v2,chat-web}.yml` 按路径触发 push 到 Pages。
- **已收尾**：JDCloud `.env` 已配置 `LIMA_CORS_ORIGINS=https://app.donglicao.com,https://chat.donglicao.com` 并重启；Aliyun 旧静态文件与 `www.donglicao.com` nginx 配置已清理，备份目录也已删除，释放约 37.7 MB。
- **生产修复**：JDCloud `lima-router` 设备存储/session_bus 已切 Redis，`/device/v1/health` 恢复 `production_ready=true`。
- **利用率审计**：见 `docs/ops/CLOUDFLARE_GITHUB_GOOGLE_AUDIT_2026-06-30.md`。

## 代码质量

| 项目 | 状态 |
|------|------|
| P0 违规 | ✅ 已修复 |
| xiaozhi_v1_compat 重构 → 物理删除 | ✅ 完成（2026-06-26 删除包+门面+退役测试+env 标志） |
| admin_ui 模块化 | ✅ 完成 (482→55, 4 模块) |
| ops_metrics 重构 | ✅ 完成 (3 模块拆分) |
| tasks.py 拆分 | ✅ 完成 (task_recorder.py) |
| legacy 路由/HTTP 栈退役 | ✅ 完成 |
| route_policy backend 字段贯通 | ✅ 完成 |
| Edge-C route_policy 硬契约 | ✅ 完成 |
| 代码质量治理 Q0–Q7 | ✅ 已关闭（见 governance plan） |
| channel_gateway / orchestrate / admin 拆分 | ✅ 完成 |
| Memory/Ledger Redis 后端 | ✅ 完成（env 切换） |

## 已知技术债务与注意事项

- **启动时间**：VPS 关键启动阶段已完成优化，/health ready 约 8 秒；backend profile / retirement 历史数据分析等 warm 阶段在后台异步运行，不再阻塞 ready。
- **本地/远程双环境**：Windows 本地代理后端、FRP `:8088`、VPS 直接后端共存，新增后端需明确拓扑归属
- **context_pipeline 膨胀**：Hot 五模块外仍有大量 Cold 实验代码；见 `docs/CODEBASE_SUBSYSTEM_TIER_CN.md` P0–P4 建议
- **findings 历史**：2026-05 CQ-046~CQ-110 旧记录已归档至 `docs/archive/findings-2026-05.md`；当前 findings.md 仅保留 2026-06-09 战略转型后记录

## 关键文档

| 文档 | 用途 | 优先级 |
|------|------|--------|
| `docs/README.md` | 文档唯一入口与权威规则 | 必读 |
| `STATUS.md` | 当前项目状态（本文件） | 必读 |
| `docs/archive/strategic-plans-2026-06/PROJECT_OPTIMIZATION_ROADMAP_CN.md` | 历史战略路线图（已归档） | 参考 |
| `docs/DEVICE_DEVELOPER_GUIDE_CN.md` | 设备开发、联调、验证入口 | 必读 |
| `docs/CODEBASE_SUBSYSTEM_TIER_CN.md` | 子系统 hot/warm/cold 分层 | 推荐 |
| `AGENTS.md` | 开发约定与命令 | 必读 |
| `docs/ARCHITECTURE.md` | 系统架构 | 推荐 |
| `docs/REQUEST_PIPELINE_AUTHORITY_CN.md` | 生产路由所有权 | 推荐 |
| `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md` | 设备模型路由策略 | 推荐 |
| `docs/ESP32S_XYZ_MANAGEMENT_CN.md` | 产品子模块边界 | 推荐 |
| `docs/LIMA_MEMORY_CN.md` | 持久跨会话记忆 | 推荐 |
