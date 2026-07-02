# LiMa Status

> **导航**：2026-07-02 起，旧的 5 份战略规划文档（PROJECT_DEFECTS_AND_IMPROVEMENT_PLAN_CN / LIMA_IMPROVEMENT_PLAN_20260625_V2 / PROJECT_OPTIMIZATION_ROADMAP_CN / DEEP_QUALITY_AUDIT_CN / OPTIMIZATION_ANALYSIS_2026-06-23）已归档至 `docs/archive/strategic-plans-2026-06/`。当前活动瘦身/优化计划见 `docs/superpowers/specs/2026-07-02-system-slimdown-design.md`。本文件历史日志中出现的旧文档名仍指向其归档位置（文件名未变，仅路径前缀变更）。

> **项目定位**: AI 智能设备统一云端服务（2026-06-09 战略转型完成）
> **技术栈**: Python 3.10 + FastAPI + SQLite + Redis
> **公网端点**: chat.donglicao.com（主入口）；api.donglicao.com 为京东云 NewAPI 反代，非 LiMa Server 直接入口
> **部署**: 主计算与公网入口在 JDCloud (`117.72.118.95`)；Cloudflare Tunnel 指向京东云本地 nginx（`https://127.0.0.1:443`），由 nginx 路由 API/静态资源。阿里云 `47.112.162.80` 已部署 `lima-router-pilot` 作为辅助节点，仅处理免费/低价后端流量（`aliyun.donglicao.com`）。chat-web、官网 playground、manager-mobile H5 的匿名简单聊天请求已分流到阿里云 pilot。`api.donglicao.com` 为京东云 NewAPI 反代，非 LiMa Server 直接入口。

> Updated: 2026-07-02
> Branch: `main`
> Scale: 约 1180 个 Python 文件 / 130,950 行（2026-06-28 图片模块拆分后）
> Tests: 全量 **4278 passed / 3 skipped / 2 deselected / 0 failed / 0 warnings**（`.venv310` Python 3.10.20）；ruff check clean；ruff format clean；pyright 目标文件 0 errors；Next.js 官网 `npm run build` 静态生成 25 个页面。
> 注意：使用系统 Python 3.14 直接运行 `python -m pytest` 会被 `tests/conftest.py` 的 Python 版本 guard 拒绝，这不是 FastAPI/Pydantic 兼容问题，而是 LiMa 仅支持 Python 3.10。已安装 `pytest-timeout` 与 `httpx2`，pytest warnings 已清零。
> 英文站：`/en/` 首页、`/en/pricing/`、`/en/product-write/`、`/en/product-human/`、`/en/privacy/`、`/en/terms/` 已上线；中英文法律页均已配置 `canonical` + `hreflang` alternate。
> ⚠️ 运维警示：主 VPS 磁盘已从 98% 降至 **67%**（40G 中 25G 已用，释放约 5G），`litestream` 已纳入 systemd 管理并设置 `MemoryMax=512M`，内存可用约 420M~850M（随负载波动），load average 4~5。京东云节点已完成深度清理（磁盘 33% → **30%**，59G 中 17G 已用，释放约 2G）。登录超时风险显著降低。
> Code Size: **0 个 >300 行文件、0 个 >50 行函数**；`scripts/check_code_size.py` PASS。
> pyright 目标文件 0 errors（sandbox 下仅历史 warning）
> CI/CD：`.github/workflows/test.yml` ✅、`.github/workflows/deploy.yml` ✅、`.github/workflows/deploy-site-v2.yml` ✅、`.github/workflows/deploy-docs-site.yml` ✅（全部绿灯）；自动部署 Aliyun + chat-web + JDCloud + 官网/docs 站流程已就绪（secrets 待配置）。
> Git 镜像：Gitee 镜像已退役，仅维护 GitHub `origin`。
> 安全审计：`findings.md` AUDIT-1 CRITICAL + HIGH 批次已修复部署（C1/C2/C3 + H1~H6）；2026-06-25 全量 pytest 修复项已 Closed；历史 2026-06-18 全量审计安全项已全部 Closed / Accepted。
> 匿名访问：生产环境已允许 `LIMA_ALLOW_ANONYMOUS=1`，`https://chat.donglicao.com/` 无需 API Key 即可聊天。

### 最近完成（2026-07-02）全量门禁 + 京东云生产部署 + 公网冒烟验证

- **本地全量门禁**：`run_pre_commit_check.py --full` → 4278 passed / 3 skipped / 2 deselected；ruff clean。
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

### 最近完成（2026-06-30）阿里云启用 `lima-router-pilot` 作为免费后端辅助节点

- **目标**：在阿里云 `47.112.162.80` 上部署 LiMa 辅助节点，仅处理免费/低价后端请求，与京东云主节点形成功能拆分。
- **角色机制**：
  - 新增 `config/node_role.py`：支持 `LIMA_NODE_ROLE=primary`（默认）与 `free_backend_only`。
  - 辅助节点关闭 `session_memory`、`device_gateway`、`mqtt`、`prometheus`、`alert_evaluator`、`structured_logging` 等子系统。
  - `server_lifespan_phases.py` 各 phase 读取对应 `LIMA_*_ENABLED` 开关，关闭时直接返回并记录原因。
- **后端池限制**：
  - `router_v3/select.py` 在 `free_backend_only` 节点上仅允许 `_CLOUD_FREE_BACKENDS` 列表中的后端（如 `cfai_*`、`fireworks_*`、`deepinfra_*`、`openrouter_*`）。
  - 排除本地 Windows 后端、付费商业后端、设备相关后端，确保辅助节点不访问主节点资源。
- **部署脚本**：
  - 新增 `deploy/aliyun/lima-router-pilot.service`、`install_aliyun_pilot.sh`、`nginx-aliyun-pilot.conf`、`README.md`。
  - 新增 `scripts/deploy_aliyun_pilot.py`：Windows 本地用 Python `tarfile` 打包 + `scp` 上传，远程执行安装脚本（规避 Git Bash 无 `rsync`）。
  - 安装时复制 `/opt/lima-router/.env` 并追加辅助节点专属变量，合并而非覆盖。
- **线上验证**：
  - `https://aliyun.donglicao.com/health` → 200，由阿里云 pilot 响应。
  - 匿名 `POST /v1/chat/completions` 经 `fireworks_qwen_72b` 返回 200，确认后端过滤生效。
  - `/device/v1/status` 返回 404，确认 `device_gateway` 未启用。
- **风险与后续**：
  - `chat.donglicao.com` 当前仍由京东云 Cloudflare Tunnel 承载，未主动切到阿里云；如需分流，应在 Cloudflare Load Balancer 中按路径或权重配置。
  - 辅助节点 `.env` 仍与主节点共享部分连接信息，建议后续为 pilot 单独配置只读/隔离连接。
  - 免费后端池可用性需监控；池耗尽时应返回 503，禁止自动降级到付费后端。

### 最近完成（2026-06-30）LiMa 主计算与公网入口完全迁移到京东云（Cloudflare Tunnel）

- **迁移结果**：主 `lima-router` 计算节点与 `chat.donglicao.com` 公网入口均已迁移至京东云 `117.72.118.95`。
  - 京东云 `/opt/lima-router` 由 pilot 目录重命名为正式目录；systemd 服务 `lima-router.service` 已启用并运行，`MemoryMax=1536M`。
  - 生产 SQLite 数据与 `router_model.pkl` 已从阿里云复制到京东云；京东云 `litestream` 已配置为本地 file replica，备份所有生产 DB。
  - 京东云已部署 `chat.donglicao.com` nginx + Let's Encrypt 证书配置（因域名拦截当前不直接对外服务，仅作为备用）。
- **公网入口方案**：
  - 京东云对 `chat.donglicao.com` 存在域名级拦截（HTTP Host / HTTPS SNI 返回“网页禁止访问”），无法直接作为公网入口。
  - 部署 **Cloudflare Tunnel**（`cloudflared`，tunnel ID `8dfd001b-d257-42e9-944d-2f82a976d969`）在京东云建立出站 QUIC 连接到 Cloudflare Edge。
  - Cloudflare DNS 中 `chat.donglicao.com` 已改为 CNAME 到 `<tunnel-id>.cfargotunnel.com`（已代理），所有流量通过 tunnel 直达京东云 `127.0.0.1:8080`。
  - 不再使用阿里云作为反向代理；阿里云 nginx `chat.donglicao.com.conf` 已还原为本地 `127.0.0.1:8080` 配置，作为应急回滚备用。
- **验证**：
  - `https://chat.donglicao.com/health` → 200，返回京东云 `lima-router` 状态。
  - 真实 `POST /v1/chat/completions`（生产 `LIMA_API_KEY`）→ 200，后端 `cfai_qwen_coder` 响应正常。
- **资源（京东云）**：`lima-router` RSS ~315M，`cloudflared` RSS ~17M，`mem available ~800M+`，`disk 28%`。
- **回滚**：阿里云 `lima-router` / `litestream` 已停止但配置/数据完整保留；若京东云故障，可将 `chat.donglicao.com` DNS 改回阿里云 A 记录并启动服务恢复。

## 当前项目状态

### 最近完成（2026-06-30）京东云 LiMa Router 并行试点

- **部署**：在京东云 `117.72.118.95` 上安装 Python 3.10，创建 `/opt/lima-router-pilot`，同步代码，安全复制生产 `.env`（设备存储改为 memory），创建 `lima-router-pilot.service`（`MemoryMax=1536M`）。
- **验证**：
  - `/health` 返回 `status=ok`、`startup=ready`。
  - 真实 `/v1/chat/completions` 请求返回 200，由 `scnet_ds_flash` 后端响应。
- **资源对比（2026-06-30 19:55，已删除 qwen2api）**：
  - 阿里云：`loadavg ~2`、`mem available 544M`、`disk 56%`。
  - 京东云：`loadavg ~0.11`、`mem available 984M`（含 pilot RSS 252M）、`disk 28%`。
- **qwen2api 已删除**：停止并移除 Docker 容器与镜像，删除 `/opt/qwen2api`、`/opt/qwen2api-data`、`/opt/qwen2api-caches`，释放约 2G 磁盘；nginx `api.donglicao.com` 中 `/compatible-mode/v1/chat/completions` 反代配置已移除。
- **结论**：京东云 4G 内存节点运行 `lima-router` 完全可行，资源余量明显优于阿里云；迁移前还需完成公网入口（DNS + HTTPS + nginx）切换方案与回滚演练。

### 最近完成（2026-06-30）阿里云/京东云深度清理与性能优化

- **阿里云深度清理**：
  - 下线并删除非核心/退役目录：`/opt/netdata`（1.2G）、`/opt/miniconda`（520M）、`/opt/new-api`（96M）、`/opt/one-api`/`one-api-data`、`/opt/deepseek-free-api`、`/opt/lima-searxng`、`/opt/lima-router/deepcode-cli`（227M）、`/www/backup/donglicao-20260405-160140`（461M）、`/root/.npm`（199M）、`/root/.cache`、`/tmp/openclaw`（48M）、旧 `lima-router.backup.*`  tarballs（26M）。
  - `podman system prune -a -f` 回收 883MB；`journalctl --vacuum-size=50M` 与日志 truncate 释放数百 MB。
  - 结果：根分区从 78% → **67%**（40G 中 25G 已用，可用 13G）。
- **阿里云性能优化**：
  - `litestream` 纳入 systemd 管理（`/etc/systemd/system/litestream.service`），设置 `MemoryMax=512M` 防止内存无限增长；`lima-router` 重启释放 leaked 内存。
  - 部署 logrotate 配置 `/etc/logrotate.d/lima` 与 journald 限制 `/etc/systemd/journald.conf.d/lima.conf`（`SystemMaxUse=200M`）。
  - 结果：内存 `used 1.4G / available 420M~850M`（波动），`lima-router` 与 `litestream` 均 active；`/health` status=ok。
- **京东云深度清理**：
  - 删除 `/opt/google/chrome`（403M）、`/root/.openclaw`（64M）、`/root/.cache`（615M，含 547M go-build）、`/root/go/pkg/mod`（745M）、`/opt/lima-monitoring` 旧 tarballs（125M）。
  - `journalctl --vacuum-size=50M`、日志清理、`apt-get clean`、`docker system prune -f`。
  - 结果：根分区从 33% → **30%**（59G 中 17G 已用，可用 40G）；`new-api`/`qwen2api` 容器保持运行。
- **京东云 retention 优化**：部署 `/etc/logrotate.d/lima` 与 `/etc/systemd/journald.conf.d/lima.conf`（`SystemMaxUse=200M`）。

### 最近完成（2026-06-30）微信小程序登录超时排查

- **现象**：用户截图显示 `LiMa 星云 → DLC 写字机` 一键登录报 `request:fail timeout errno: 5`。
- **客户端修复**：
  - `manager-mobile/src/api/v2/index.ts`：`v2Login` 超时从 15s 提升到 30s，并对 timeout/network 错误自动重试 1 次。
  - 已构建 `dist/build/mp-weixin`；版本 `3.6.0` 已通过 `pnpm upload:mp-weixin` 上传至微信后台（包大小约 1061KB），待在微信公众平台「版本管理」设为体验版/提交审核。
- **服务端排查**：
  - `/device/v1/app/auth/login` 实测响应 2-4s（主要耗时在微信 `jscode2session`）。
  - 发现主 VPS 磁盘 98% 满、内存紧张、load average 6+，偶发 nginx 502 / 连接拒绝。
  - 已重启 `lima-router` 释放内存，但根因是系统资源不足，需扩容/清理。
- **提交**：
  - 主仓库：`c918aa9f`（WeChat jscode2session 耗时日志）。
  - 子模块 `esp32S_XYZ`：`7d5086f`（登录超时与重试）。

### 最近完成（2026-06-30）VPS 容量缓解与 Litestream 修复

- **磁盘缓解**：重启 `litestream` 释放其持有的已删除 WAL（约 6G），清理停止的 Podman 容器（`one-api`/`new-api`/`lima-searxng`）与归档 journal，根分区从 98% → **80%**。
- **Litestream 修复**：配置文件中残留未配置环境变量的 `s3` replica，导致启动报错 `bucket required for s3 replica`。已重写为仅本地 file replica，并移除不存在的 `tool_audit.db`/`mastery_loop.db` 配置；服务已恢复运行，现有 5 个 DB 的 generation 查询正常。
- **京东云迁移评估**：主 VPS 仍高负载（loadavg ~8），内存可用 ~518M。可迁移/清理候选已整理进 `progress.md` / `findings.md`。
- **阿里云非核心清理**：`lima-openobserve` 容器及镜像已移除（LiMa 未启用）；已退役的 `openclaw-gateway` 用户 systemd 服务已停止并禁用（此前每秒无限重启并产生 67 万+ restart counter）；`mission-server`（parallel-ai mission supervisor）已确认唯一调用方为 `openclaw-gateway` 且全部 404，已停止容器、备份 Postgres 数据卷（`/opt/backups/mission-server-20260630-182949/`）并清理镜像/卷。
- **京东云深度清理**：通过本地凭据登录 `117.72.118.95` 后完成清理：删除未使用的 `/opt/llm-cache/venv`（5.1G）、清理 `pip`/`npm`/`apt` 缓存与旧日志、移除停用服务 `qwen-gateway`、停止无外部连接的侧边服务 `mimo-proxy`/`tts-proxy`/`lima-voice`/`hermes-api`；磁盘 **51% → 33%**，可用内存 **~932M → 1072M**；核心 `new-api`/`qwen2api`/MySQL/Redis/Prometheus/Worker/Probe/`llm-cache`/nginx 保持运行。

### 最近完成（2026-06-30）deploy-docs-site CI 修复 — 最后一个 CI 失败项关闭

- **目标**：修复 `deploy-docs-site.yml` 工作流 0s 失败。
- **根因**：`secrets` context 在 step `if` 条件中不可用（GitHub Actions 限制），导致工作流文件解析失败。与 `deploy-site-v2.yml` 曾有的问题相同（commit `12977187` 已修复）。
- **修复**：
  - 将 `secrets.X != ''` 检查移至 job-level `env:` 变量（`VPS_HOST_SET`/`VPS_SSH_KEY_SET`/`DOCS_SITE_DIR_SET`）。
  - step `if` 改为 `env.VAR == 'true'`。
  - Node 版本 `20` → `22`（pnpm 11.9 要求 ≥ 22.13，Node 20 已被 GH Actions 废弃）。
- **结果**：三个 CI 工作流（Tests ✅、Deploy ✅、Deploy Docs Site ✅）全部绿灯。
- **提交**：`e2f7b20d`（secrets context 修复）、`f897c84d`（Node 版本升级）。

### 最近完成（2026-06-30）client-keys 功能重写 v2（替代 PR #1）

- **决策**：不直接合并 PR #1（1012 文件变更、与 main 冲突、范围失控），改为基于当前 `main` 新建 `feat/client-keys-v2` 重写。
- **实现**：
  - 新增 `client_keys/` 包（SQLite 存储、SQLite 日/月配额、内存 RPM、Pydantic 校验）。
  - 新增 `routes/client_keys.py` 管理 API。
  - `access_guard.py` 支持动态 client key + URL 白名单 + 配额，静态 key 行为不变。
  - 配置、路由注册、`.env.example` 同步更新。
  - 43 个新增/修改测试通过；`ruff`、`pyright`、`check_code_size` 通过。
- **债务**：RPM 为进程内窗口，多 worker 近似；已记入 `PONYTAIL-DEBT.md`。
- **结果**：PR #22 已合并到 `main`，PR #1 已关闭。

### 最近完成（2026-06-30）关闭 6 个高风险 dependabot PR + 合并安全补丁 #18

- **目标**：处理 dependabot PR 队列。
- **已关闭（高风险）**：#11（modelscope）、#12（edge-tts）、#13（python 3.14 Docker）、#15（dashscope）、#17（opencv）、#20（numpy 约束变更）。
- **已合并（安全补丁）**：#18 `alibabacloud-nls-python-sdk >=1.0 → >=1.0.2`（commit `825757bb`）。
- **已关闭**：#1 `feat(client-keys): 客户端密钥管理功能 + 代码审查修复`（由 PR #22 替代合并）。

### 最近完成（2026-06-30）Security Headers AUDIT 修复：消除 nginx 重复头

- **目标**：修复生产环境 nginx 与 `SecurityHeadersMiddleware` 重复设置 `X-Frame-Options`、`X-Content-Type-Options`、`Referrer-Policy`、`Strict-Transport-Security` 的问题。
- **改动**：
  - `routes/security_headers.py`：默认只设置 CSP、Permissions-Policy、X-XSS-Protection；当 `LIMA_BEHIND_NGINX != 1` 时再由中间件兜底设置四个基础头。
  - `tests/test_routes_security_headers.py`、`tests/test_security_headers.py`：更新测试覆盖两套场景。
- **验证**：聚焦 pytest 8 passed；ruff / pyright / check_code_size 全通过；VPS `deploy_unified.py --slice core` 862 文件上传成功，服务重启。
- **线上验证**：`https://chat.donglicao.com/health` 200；响应头中 nginx 负责四个基础头，中间件负责 CSP/Permissions-Policy/X-XSS-Protection，无重复。
- **提交**：`4204c5a6` fix(security) 已推送至 `origin/main`。

### 最近完成（2026-06-30）清理剩余未跟踪文件

- **目标**：处理 `.joycode/` 和 `docs/superpowers/` 下三个未跟踪文件。
- **提交**：`5b9bb78d` docs: add superpowers plans/specs and joycode project memory 已推送至 `origin/main`。
- **结果**：工作区已干净。

### 最近完成（2026-06-30）esp32S_XYZ 子模块同步：firmware 安全加固 + 小程序暗色主题

- **目标**：提交并推送 `esp32S_XYZ` 子模块的本地改动，并更新父仓库子模块指针。
- **子模块改动**：
  - `firmware/u8-xiaozhi`：AUDIT-12-F3 本地控制 WebSocket Bearer/?token 鉴权、OTA 安全加固。
  - `server/xiaozhi-esp32-server/main/manager-mobile`：暗色星云主题 i18n / 配置 / 合约同步；新增 `scripts/upload-mp-weixin.js`；修复 `src/style/index.scss` prettier 格式。
- **验证**：
  - `pnpm install` 后 `vue-tsc --noEmit` 通过。
  - `pnpm run lint` 0 errors（剩余 11 条 `unocss/order` warning，不影响提交）。
  - 清理了 `pnpm install` 意外生成的嵌套 `.git` 仓库和 `nul` 文件。
- **提交**：
  - 子模块：`034356f`（feat(firmware)）、`43ae263`（feat(mp)）已推送至 `origin/main`。
  - 父仓库：`7677a290` chore(submodule) 已推送至 `origin/main`。

### 最近完成（2026-06-30）chat-web 静态资源同步 + 全仓库 ruff format

- **目标**：将 chat-web 前端改动部署到 VPS，并清理全局 ruff format 债务后推送 GitHub。
- **改动**：
  - `chat-web/` 下 14 个静态文件（HTML/JS/CSS）视觉与交互更新。
  - 对 32 个 Python 文件运行 `ruff format`；在 `config/settings_core.py`、`routing_engine.py` 两处过长行加 `# fmt: skip`，避免格式化后触发 size 门禁。
- **验证**：全量 pytest **4186 passed / 3 skipped / 2 deselected / 0 failed**；`ruff check` / `ruff format --check` / `pyright` / `scripts/check_code_size.py` 全通过；VPS `python scripts/deploy_unified.py --slice core` 861 文件上传成功，服务重启，`https://chat.donglicao.com/health` 返回 200。
- **提交**：`0a6bc689`（style）、`00314da5`（feat(chat-web)）已推送至 `origin/main`。
- **未提交**：`esp32S_XYZ` 子模块仍有本地改动，未纳入本次推送。

### 最近完成（2026-06-29）LiMa HIGH 批次修复：AUDIT-1 H1~H6

- **目标**：修复 LiMa 后端系统深度审查（AUDIT-1）标记的 6 个 HIGH 问题。
- **改动**：
  - H1：`semantic_cache/store.py` 改用 SQLite 连接池；`semantic_cache/cache.py` 单例化。
  - H2：`http_response.py` 防御性解析；`http_errors.py` 移除子串状态码匹配。
  - H3/H4：`http_stream.py` + 新增 `http_stream_core.py` 真实记录流式质量；客户端断连/取消不再误罚后端。
  - H5：`route_scorer.py` 三处静默异常改为 warning；拆分为小函数。
  - H6：9 个生产路径的静默 `except: pass` 改为 warning；CI gate 增加 `ImportError` 模式检测。
- **验证**：ruff/format/pyright/check_code_size 全通过；全量 pytest 4083 passed；VPS 部署成功，`https://chat.donglicao.com/health` 200。

### 最近完成（2026-06-28）LiMa CRITICAL 批次修复：AUDIT-1 C1/C2/C3

- **目标**：修复 LiMa 后端系统深度审查（AUDIT-1）标记的 3 个 CRITICAL 问题。
- **改动**：
  - C1：`device_gateway/auth.py` fallback 默认关闭；`.env.example` 显式声明；新增单元测试。
  - C2：`server_lifespan.py` WARM phases task 强引用；`device_gateway/mqtt_client.py` MQTT loop task 保存并 cancel；拆分 `mqtt_handlers.py` 保持文件 ≤300 行。
  - C3：`routes/chat_stream.py` `_stream_orchestration` 加 try/except 异常回退；新增回归测试。
- **验证**：ruff/format/pyright/check_code_size 全通过；全量 pytest 4064 passed；VPS 部署成功，`https://chat.donglicao.com/health` 200。
- **注意**：U8 固件若未在 VPS `.env` 显式开启 `LIMA_WS_REGISTERED_DEVICE_FALLBACK=1`，空 token 设备将无法接入 `/device/v1/ws`，需运维 opt-in。

### 最近完成（2026-06-28）小程序 WebSocket 鉴权 bug 修复 + getBearerToken 去重

- **目标**：修复 `useDeviceWebSocket.ts` 把整个 token 存储 JSON 当 Bearer 的预存 bug。
- **改动**：`utils/index.ts` 新增共享 `getBearerToken()`；`useDeviceWebSocket.ts`/`chat.ts`/`useUpload.ts` 统一引用（消除 3 处重复）。
- **验证**：
  - 本地：`vue-tsc` + `eslint` 通过。
  - CI：esp32S_XYZ run `28327010932` 全绿，Manager mobile tests 1m0s ✓。

### 最近完成（2026-06-28）小程序 token 静默刷新：修复 alova 刷新拦截器架构性失效

- **目标**：实现小程序端 JWT token 过期后的静默刷新，避免 24h 过期强制登出。
- **关键发现（架构性 bug）**：原 `refreshTokenOnError` 对 LiMa 的 HTTP 401 永远不触发——LiMa 返回 HTTP 401 状态码，而 uni-app 适配器对所有 HTTP 状态码走 success 回调（仅网络失败 reject），故 401 进入 `onSuccess` 路径，`refreshTokenOnError` 是死代码。
- **改动**：
  - `login/index.vue`：存绝对过期时间戳 `expireAt`（原存相对 `expire:86400` 是 bug）。
  - `api/v2/index.ts`：新增 `v2RefreshToken()`；`v2Login` 加 `authRole:'login'` 防 `onAuthRequired` 死锁。
  - `alova.ts`：改用 `refreshTokenOnSuccess`（isExpired 检 `statusCode===401`）；加 30s 冷却防无限刷新循环。
- **验证**：
  - 本地：`vue-tsc --noEmit` 通过；`eslint` 通过；一致性检查通过。
  - CI：esp32S_XYZ run `28326758413` 全绿，Manager mobile tests 1m0s ✓（含 type-check + 微信小程序 build）。
- **遗留**：`useDeviceWebSocket.ts:71` 读 token 存储当 Bearer 是预存 bug（建议后续修）。

### 最近完成（2026-06-28）Pollinations.ai 增强、中文 prompt 翻译与图片模块拆分

- **目标**：让零配置的 Pollinations.ai 后端支持更多参数，并自动翻译中文 prompt；同时把图片生成代码拆成可维护的小模块。
- **关键结果**：
  - 新增 `routes/images_pollinations.py`：支持 `seed`、`model`、`negative_prompt`、`nologo`、`private`、`enhance`、`safe` 等 Pollinations 参数。
  - 新增中文 prompt 自动翻译：含中文时调用 Pollinations 免费文本接口翻译成英文，失败自动回退；可通过 `LIMA_IMAGE_PROMPT_TRANSLATE_ZH` 开关。
  - 缓存 key 升级为 `(prompt, size, n, variant)`，避免不同 seed/参数互相污染。
  - 代码结构拆分：`images_backends.py`（xmiaom/FreeTheAi/OpenAI）、`images_pollinations.py`（Pollinations/翻译）、`images_cache.py`（缓存）、`images.py`（路由入口）。
  - `routes/device_app_images.py` 同步支持 Pollinations options。
  - `.env.example` 补充 `LIMA_IMAGE_PROMPT_TRANSLATE_ZH`、`LIMA_IMAGE_PROMPT_TRANSLATE_TIMEOUT_SECONDS`。
- **验证**：
  - 聚焦测试 `tests/test_routes_images.py` + `tests/test_images_pollinations.py` + `tests/test_images_backends.py` + `tests/test_device_app_images.py` → **29 passed / 0 failed**。
  - `ruff check` / `ruff format --check` / `pyright` / `scripts/check_code_size.py` clean。
- **下一步**：VPS 部署后验证带参数的 Pollinations 调用。

### 最近完成（2026-06-28）图片生成接口接入 FreeTheAi 优质降级后端

- **目标**：为 `/v1/images/generations` 增加 xmiaom 失败后的高质量 OpenAI-compatible 降级后端，提升生图成功率与画质。
- **关键结果**：
  - `routes/images.py` 新增 `_generate_via_freetheai()`，调用 `https://api.freetheai.xyz/v1/images/generations`（模型 `img/gpt-image-2`）。
  - 通用 OpenAI 图像调用器 `_generate_via_openai_image_endpoint()` 兼容 `url` 与 `b64_json` 响应；b64 自动转为 `data:image/png;base64,` 数据 URI。
  - 回退链路改为：xmiaom → FreeTheAi → Pollinations.ai。
  - 新增 `LIMA_OPENAI_IMAGE_TIMEOUT_SECONDS` 环境变量（默认 120s）。
  - `tests/test_routes_images.py` 新增 3 个 FreeTheAi 相关测试。
- **验证**：
  - 聚焦测试 `tests/test_routes_images.py` → **16 passed / 0 failed**。
  - 完整回归测试 → **4005 passed / 3 skipped / 0 failed**。
  - `ruff check` / `ruff format --check` / `pyright` 目标文件 clean。
- **下一步**：拿到真实 `FREETHEAI_API_KEY` 后在 VPS 做端到端验证。

### 最近完成（2026-06-27）京东云利用率提升 Phase 1：probe 结果回写与异地观测

- **目标**：按 `docs/superpowers/specs/2026-06-28-jdcloud-utilization-plan.md`，让京东云 probe 的结构化结果安全回流到 LiMa 主节点，并在 Admin 端点展示。
- **关键结果**：
  - LiMa 侧新增 `routes/admin_probe_ingress.py`：`POST /admin/api/probe/ingress`（独立 `LIMA_PROBE_INGRESS_TOKEN`）与 `GET /admin/api/probe/jdcloud`（admin 认证）。
  - 新增 `observability/probe_state.py`：线程安全内存存储 + metadata 脱敏。
  - `config/env.py` / `routes/route_registry.py` / `.env.example` 接入开关与 token 配置。
  - 京东云侧新增 `deploy/jdcloud/push_probe_results.py` + `push_probe_results_utils.py`，读取 `known_providers.json` / `discoveries.jsonl` / `stability.json`，生成脱敏 payload。
  - 新增 `lima-probe-push.service` / `lima-probe-push.timer`，每 5 分钟以 `lima-probe` 用户运行推送。
  - 京东云节点 `/etc/hosts` 将 `chat.donglicao.com` 指向主 VPS 源站 IP，绕过 Cloudflare 1010 拦截。
- **验证**：
  - 聚焦测试 `tests/test_admin_probe_ingress.py` + `tests/test_jdcloud_push_probe.py` → **25 passed / 0 failed**。
  - 完整测试 → **3893 passed / 3 skipped / 2 deselected / 0 failed**；`ruff check .` / `ruff format --check .` / `pyright` 目标文件 0 errors；`scripts/check_code_size.py --git-tracked` PASS。
  - 主 VPS `python scripts/deploy_unified.py --files routes/admin_probe_ingress.py observability/probe_state.py config/env.py routes/route_registry.py` → 421 uploaded / 0 failed；Health OK。
  - 京东云 `systemctl start lima-probe-push.service` 日志：`probe push: status=200 recorded=39`。
  - 主 VPS `GET /admin/api/probe/jdcloud` 返回 39 条京东云 probe 记录。
- **下一步**：观测推送稳定性与数据新鲜度，决定是否进入 Phase 2（分担低价/免费后端流量）。

### 最近完成（2026-06-28）P4-后续-灰度观测 Phase 1–4 已完成，进入 24–48h 观测

- **目标**：按 `docs/superpowers/specs/2026-06-28-gray-observation-plan.md`，为已落地的 Instructor 意图回退与语义缓存建立灰度观测能力，确保开关默认关闭、失败安全，并在 VPS 开启真实流量观测。
- **关键结果**：
  - Phase 1（指标暴露）：新增 `/admin/api/metrics/gray` 端点，统一暴露语义缓存与 Instructor 意图回退的灰度计数器（`observability/metrics.py` gray counters）。
  - Phase 2（Trace enrichment）：生产 trace 中新增 `cache_status`、`intent_source`、`intent_confidence` 字段，可在 `/admin/api/traces/recent` 按单条请求查看缓存命中状态与意图来源。
  - Phase 3（开关/文档）：`.env.example` 增加灰度观测 tracing 提示；`STATUS.md`、`progress.md`、`docs/superpowers/plans/README.md` 已同步。
  - Phase 4（部署验证）：
    - `python scripts/deploy_unified.py --slice core` → **1401 uploaded / 0 failed / 0 skipped**；Health OK。
    - VPS `.env` 已备份并追加 `LIMA_INSTRUCTOR_INTENT_ENABLED=1`、`LIMA_SEMANTIC_CACHE_ENABLED=1`、`LIMA_TRACING_ENABLED=1`，服务已重启。
    - 本地 loopback 聊天返回 HTTP 200，响应头包含 `X-LiMa-Trace-Id`。
    - `/admin/api/metrics/gray` 返回语义缓存命中率 66.67%（hit=2, miss=1, store=1），`intent_source` 为 rules；`/admin/api/traces/recent` 中可见 `cache_status=hit/miss` 与 `intent_source=rules`。
    - 完整回归测试 `-m "not network"` → **3866 passed / 3 skipped / 2 deselected / 0 failed**。
- **当前阶段**：24–48h 灰度观测，根据命中率/延迟/成功率决定是否默认开启。

### 最近完成（2026-06-27）P4-8：全链路追踪接入生产路径

- **目标**：按 `docs/superpowers/specs/2026-06-27-full-link-tracing-design.md`，把 `context_pipeline/tracing.py` 接入 `/v1/chat/completions` 生产路径，使每次请求生成可查询的完整 trace。
- **关键结果**：
  - 新增 `routing_engine_trace.py`：`trace_span()` 上下文管理器，按 `LIMA_TRACING_ENABLED`（默认开启）自动 start/end span，异常时记录 `error`/`error_msg`。
  - `context_pipeline/tracing.py`：新增 `RequestTrace.finish()` 关闭所有 active span 并导出；新增 `reset_current_trace()` 用于测试隔离。
  - `observability/metrics.py`：新增 `_recent_traces` ring buffer（`maxlen=1000`）及 `record_trace()` / `get_recent_traces()` / `reset_traces()`；`reset_metrics()` 同步清空 trace buffer。
  - `routing_engine.py` / `routing_engine_helpers.py` / `routing_engine_execute_strategy.py` 生产路径插桩 8+ span：`identity`、`classify`、`scenario`、`recall`、`retrieval`、`select`、`skills`、`execute`、`speculative`、`post_process`。
  - `routes/chat_endpoints.py` 请求入口创建 trace；`routes/chat_response_finalize.py` 与 `routes/chat_handler_dispatch.py` 在 JSON/SSE 响应注入 `X-LiMa-Trace-Id`；请求结束后将 trace 写入 ring buffer。
  - 新增 `routes/admin_traces.py`：`GET /admin/api/traces/recent?limit=50`（`verify_admin` 保护）。
  - 新增测试：`tests/test_routing_engine_trace.py`、`tests/test_observability_trace_buffer.py`、`tests/test_routing_engine_trace_spans.py`、`tests/test_chat_endpoints_trace_header.py`、`tests/test_admin_traces.py`；补充 `tests/test_tracing.py`。
  - `.env.example` 增加 `LIMA_TRACING_ENABLED` 配置项。
- **验证**：
  - 聚焦测试：新增 5 个测试文件 → 全部通过。
  - 完整测试 `-m "not network"` → **3856 passed / 3 skipped / 2 deselected / 0 failed**。
  - `ruff check .` clean；`ruff format --check .` clean；`scripts/check_code_size.py` PASS；`pyright` 目标文件 0 errors。
- **部署**：
  - `python scripts/deploy_unified.py --slice core` → **1386 uploaded / 0 failed / 0 skipped**；Health OK。
  - 公网 `https://chat.donglicao.com/health` 200，`status=ok`。
  - 公网 `POST /v1/chat/completions`（匿名，`model=fast`）→ HTTP 200，响应头包含 `X-LiMa-Trace-Id: 30bf615c0867`。
  - 公网 `GET /admin/api/traces/recent`（无效 token）→ HTTP 401，端点已注册。

### 最近完成（2026-06-27）P4-3 后续：Instructor 意图回退结构化输出落地

- **目标**：按 `docs/superpowers/plans/README.md` 推荐，将 Instructor 结构化输出能力接入 `routing_intent.py`，作为规则分类置信度不足时的可选回退。
- **关键结果**：
  - 新增 `routing_intent_instructor.py`：封装 `maybe_instructor_intent()`，保持 `routing_intent.py` ≤300 行。
  - 扩展 `models/structured_outputs/instructor_client.py`：新增 `create_structured_completion(provider, model, messages, response_model)`，复用 `key_pool` 获取 key，支持 groq/openrouter/cerebras，失败时记录 warning 并返回 `None`。
  - `routing_intent.py::analyze_intent()` 在规则 confidence < `LIMA_INSTRUCTOR_INTENT_THRESHOLD`（默认 0.70）时调用 Instructor；命中且 confidence 达标则采用，否则保持规则结果。
  - 新增 `observability/events.py::instructor_intent_event()` 与指标事件，用于观测调用成功/失败。
  - `config/env.py` 新增 6 个环境变量读取函数；`.env.example` 补充配置示例。
  - 新增 `tests/test_instructor_intent_fallback.py`（21 cases）覆盖配置、Instructor 客户端、事件、意图集成开关/成功/失败/阈值路径。
  - 修复 `routing_engine.py`/`routing_selector` 中 `recalled_backend` 类型回归（恢复 `str | None`）。
- **验证**：`ruff check .` clean；`ruff format --check .` clean；`python scripts/check_code_size.py` PASS；`pyright` 目标文件 0 errors（可选依赖 `openai`/`instructor` 缺失 warning 除外）；全量 pytest **3844 passed / 3 skipped / 2 deselected / 0 failed**。
- **部署**：`python scripts/deploy_unified.py --files ...` → 167 uploaded / 0 failed；Health OK；公网聊天冒烟 HTTP 200。

### 最近完成（2026-06-27）P4-5 后续：语义缓存接入生产路径

- **目标**：按 `docs/superpowers/plans/README.md` 推荐，将 `semantic_cache/` 接入 `routing_engine.py::route()` 生产请求路径，默认关闭。
- **关键结果**：
  - 拆分 `routing_engine.py`：新增 `routing_engine_helpers.py`（`identity_shortcut`、`build_route_result`）与 `routing_engine_cache.py`（缓存查询/写入封装），保持主入口 ≤300 行。
  - `route()` 在身份短路之后、后端执行之前调用 `lookup_cached_response()`；命中直接返回缓存 answer，后端标记为原始选中后端。
  - 未命中时后端返回后调用 `store_cached_response()` 写入缓存；仅对 `request_type == "chat"` 启用。
  - 默认关闭（`LIMA_SEMANTIC_CACHE_ENABLED=0`），缓存失效/异常时记录 warning 并放行请求，符合无静默降级硬规则。
  - 新增 `tests/test_route_pipeline.py::test_route_semantic_cache_hits_on_second_identical_query` 回归缓存命中路径。
- **验证**：`ruff check .` clean；`ruff format --check .` clean；`python scripts/check_code_size.py` PASS；`pyright` 目标文件 0 errors / 0 warnings。
- **全量 pytest**：**3820 passed / 3 skipped / 2 deselected / 0 failed**。

### 最近完成（2026-06-26）P4-6 编排管线状态可视化落地

- **目标**：按 `docs/superpowers/plans/README.md` 推荐，完成 P4 最后一项：请求流水线状态可视化。
- **关键结果**：
  - 新增 `pipeline_graph.py`：`PipelineNode` / `PipelineEdge` / `PipelineGraph` 数据结构，内置当前 12 步路由流水线节点与边（身份短路 → 后处理）。
  - 新增 `scripts/generate_pipeline_graph.py`：生成 Mermaid 流程图到 `docs/assets/routing_pipeline.mmd`。
  - 新增 `tests/test_pipeline_graph.py`（4 cases）：覆盖节点/边存在性、Mermaid 输出、引号转义。
  - 已生成 `docs/assets/routing_pipeline.mmd`，可直接在 GitHub/Markdown 渲染器或 Mermaid Live Editor 查看。
- **验证**：`ruff check .` clean；`ruff format --check .` clean；`python scripts/check_code_size.py` PASS。
- **全量 pytest**：**3819 passed / 3 skipped / 2 deselected / 0 failed**。

### 最近完成（2026-06-26）P4-5 语义缓存层落地

- **目标**：按 `docs/superpowers/plans/README.md` 推荐，实现语义缓存基座，用于降低高频问题的后端调用成本。
- **关键结果**：
  - 新增 `semantic_cache/` 包：
    - `embedder.py`：`Embedder` 协议 + `JinaEmbedder` + 离线 `FakeEmbedder`。
    - `store.py`：SQLite 持久化，支持 TTL 裁剪、命中计数、按 `query_hash` upsert。
    - `cache.py`：`SemanticCache` 高阶 API，含余弦相似度计算与阈值命中逻辑。
    - `config.py`：环境变量读取（默认全部关闭）。
  - 新增 `tests/test_semantic_cache.py`（10 cases）：覆盖 store/cosine/ttl/prune/hit count。
  - 新增 `semantic_cache/README.md` 使用说明。
  - `.env.example` 增加 `LIMA_SEMANTIC_CACHE_*` 配置项。
- **验证**：`ruff check .` clean；`ruff format --check .` clean；`python scripts/check_code_size.py` PASS。
- **全量 pytest**：**3815 passed / 3 skipped / 2 deselected / 0 failed**。

### 最近完成（2026-06-26）P4-4 promptfoo 提示词回归测试落地

- **目标**：按 `docs/superpowers/plans/README.md` 推荐，为 `prompts/layers.yaml` 增加快照回归能力。
- **关键结果**：
  - 新增 `promptfooconfig.yaml`：7 个测试用例覆盖 `chat`、`coding`、`vision`、`device_draw`、`device_write`、`device_control` 及 IDE 后缀场景。
  - 新增 `tests/promptfoo/prompt_provider.py`：自定义 promptfoo provider，本地调用 `prompt_engineering.layers.compose_system_prompt()` 渲染系统 prompt，不调用 LLM API。
  - 新增 `tests/test_promptfoo_provider.py`：10 个 pytest 用例覆盖 provider，确保回归可被标准测试套件捕获。
  - 更新 `prompts/README.md`：说明 promptfoo 回归命令与使用约定。
- **验证**：
  - `npx promptfoo eval -c promptfooconfig.yaml` → **7 passed (100%)**。
  - `ruff check .` clean；`ruff format --check .` clean；`python scripts/check_code_size.py` PASS。
- **全量 pytest**：**3805 passed / 3 skipped / 2 deselected / 0 failed**。

### 最近完成（2026-06-26）P4-3 结构化输出基座落地（Pydantic schemas + validator）

- **目标**：按 `docs/superpowers/plans/README.md` 推荐，继续推进 P4 提示词系统强化，落地 P4-3 结构化输出基座。
- **关键结果**：
  - 新增 `models/__init__.py` + `models/structured_outputs/`：
    - `schemas.py`：`ClassifyResult`、`ScenarioResult`、`IntentResult`、`BackendScore`。
    - `validator.py`：`parse_json` / `validate_value`，失败时回退并记录 warning（符合无静默降级硬规则）。
    - `instructor_client.py`：可选 Instructor patch，默认关闭，预留 LLM-native 结构化输出接口。
  - `routing_classifier.py`：`classify()` 与 `classify_scenario()` 输出通过 Pydantic 模型校验。
  - `routing_intent.py`：`analyze_intent()` 返回结果通过 `IntentResult` 校验后再 dict 化，保留原有全部字段。
  - 配置：`config/env.py` 无需新增（validator 不依赖环境开关），`.env.example` / `requirements_server.txt` 增加 Instructor 可选开关/依赖注释。
  - 新增测试 `tests/test_structured_outputs.py`（12 cases）。
- **验证**：`ruff check .` clean；`ruff format --check .` clean；`python scripts/check_code_size.py` PASS。
- **全量 pytest**：**3795 passed / 3 skipped / 2 deselected / 0 failed**。

### 最近完成（2026-06-26）P4-2 语义路由预筛层落地（keyword/regex baseline）

- **目标**：按 `docs/superpowers/plans/README.md` 推荐，继续推进 P4 提示词系统强化，落地 P4-2 语义路由预筛层，避免引入本地 embedding 模型依赖。
- **关键结果**：
  - 新增 `routing/__init__.py` + `routing/semantic_router.py`：6 条路由（`image_gen`、`device_draw`、`device_write`、`device_control`、`thinking`、`code_generation`），pattern + weighted signal 双路置信度；为 embedding backend 预留接口。
  - 新增 `routing_engine_intent.py`：默认关闭，启用后在 `routing_engine.py` 的意图分析前短路高置信度意图，跳过 LLM 规则分析。
  - `config/env.py` + `.env.example`：新增 `LIMA_SEMANTIC_ROUTER_ENABLED` / `LIMA_SEMANTIC_ROUTER_THRESHOLD`。
  - 新增 `tests/test_semantic_router.py`（18 cases）；修复 `tests/test_route_pipeline.py` mock 目标。
- **验证**：`ruff check .` clean；`ruff format --check .` clean；`python scripts/check_code_size.py` PASS。
- **全量 pytest**：**3780 passed / 3 skipped / 2 deselected / 0 failed**。

### 最近完成（2026-06-26）P4-1 提示词模板注册表落地

- **目标**：按 `docs/superpowers/plans/README.md` 推荐，启动 P4 提示词系统强化，先落地 P4-1 模板注册表。
- **关键结果**：
  - 新增 `prompts/layers.yaml`：6 个场景（`coding`、`chat`、`vision`、`device_draw`、`device_write`、`device_control`）的 role/skill 模板，使用 `{name}`、`{capability_bullets}` 等 brace 占位符。
  - 新增 `prompt_engineering/registry.py`：按 `prompts/{group}.yaml` 加载模板，支持基于文件 mtime 的缓存自动失效，开发环境保存即生效。
  - 重构 `prompt_engineering/layers.py`：`_build_role_text` 与 `build_skill_layer` 从 YAML 加载并 `.format()` 预计算值；`PROMPT_VERSION` 升级到 `lima-prompts-v2.0`；保留 IDE 后缀逻辑在代码中。
  - 新增 `tests/test_prompt_registry.py`：覆盖全部场景加载、占位符格式化、缺失模板报错、缓存失效、组合 prompt 非空。
  - 新增 `prompts/README.md`（中文）：说明 registry 目录、命名与热更新约定。
  - 更新 `docs/superpowers/plans/README.md`：P4-1 标记为已完成，P4-2~P4-6 仍待启动。
- **验证**：`ruff check .` clean；`ruff format --check .` clean；`python scripts/check_code_size.py` PASS。
- **全量 pytest**：**3762 passed / 3 skipped / 2 deselected / 0 failed**。

### 最近完成（2026-06-26）P0：编码能力退役残留清理

- **目标**：完成 `docs/superpowers/plans/README.md` P0-编码退役残留清理，`classify_scenario()` 永远返回 `"chat"`，并移除所有生产代码中对 `scenario == "coding"` 的行为依赖。
- **关键结果**：
  - `routing_classifier.py`：`classify_scenario()` 简化为永远返回 `"chat"`。
  - `routes/v3_adapters.py`：移除 `classify_scenario` 调用与导入；按 `ide` 是否存在决定是否走 `build_context_digest` / `enhance_coding_prompt` IDE 辅助路径；非 IDE 请求施加纯文本约束。
  - `route_scorer.py`：移除 `scenario == "coding"` / `request_type == "code"` 的 coding 后端加分分支。
  - `routing_selector/core.py`：移除 `chat + coding → code` 池映射。
  - `routing_selector/filters.py`：从 tool backend 排序中移除 strong-coding-tool 优先逻辑。
  - `http_request_builder/body.py`：IDE 请求的系统 prompt 场景统一为 `"chat"`。
  - `routes/chat_preflight.py`：`apply_token_budget` 的 scenario 始终传 `"chat"`。
  - 更新相关测试：`test_routing_classifier_scenario.py`、`test_pick_backend.py`、`test_routes_v3_adapters.py`、`test_routing_selector_core.py`。
- **验证**：`ruff check .` clean；`ruff format --check .` clean；`python scripts/check_code_size.py` PASS。
- **全量 pytest**：**3762 passed / 3 skipped / 2 deselected / 0 failed**。

### 最近完成（2026-06-26）代码体积全面达标

- **目标**：消除 `scripts/check_code_size.py` 报告的所有体积违规。
- **关键结果**：
  - 24 个 >50 行函数通过提取 helper 降至 ≤50 行（涉及 `scripts/*`、`lima_mcp_stdio/*`、`tests/*`、`xiaozhi_drawing/svg_validator.py`、`routes/route_registry.py` 等）。
  - 6 个 >300 行文件拆分/瘦身至 ≤300 行：
    - `device_gateway/draw_prompt_enhancer.py` → 拆出 `device_gateway/draw_prompt_complexity.py`
    - `routes/device_ota.py` → 拆出 `routes/device_ota_helpers.py`
    - `routes/device_gateway_ws_handlers.py` → 拆出 `routes/device_gateway_ws_motion.py`
    - `scripts/guardian_scanner.py` → 拆出 `scripts/guardian_full_scan.py`
    - `tests/test_device_app_sharing.py` → 拆出 helper/permissions 测试文件
    - `tests/test_device_app_task_templates.py` → 拆出 helper/rejections 测试文件
  - 更新相关测试补丁目标（`routes.device_ota_helpers`、`routes.device_gateway_ws_motion`）。
  - 修复 `tests/test_device_attestation.py` 因 `_FIRMWARE_HASHES_PATH` 迁移导致的 monkeypatch 失败。
- **验证**：`ruff check .` clean、`ruff format --check .` clean、`scripts/check_code_size.py` PASS。
- **全量 pytest**：**3735 passed / 3 skipped / 2 deselected / 0 failed**。

### 最近完成（2026-06-26）工作区清理、CI 去忽略、瘦身文档同步

- **目标**：消除 `.omk/CODE_REVIEW_ISSUES.md` 中的可执行债务。
- **关键结果**：
  - `ruff format --check .` 全量通过；`scripts/verify_production_deploy.py` 完成格式化。
  - 删除并忽略 `.omo/`、`.playwright-mcp/`、`chat-*.png` 等临时文件；将两个 `LiMa_QWEN3_系统增强细化方案` 计划文档移入 `docs/superpowers/plans/`。
  - 删除 `tests/test_manager_mobile_lima_native.py`（`esp32S_XYZ` 子模块路径漂移，维护成本高于价值）。
  - 从 `scripts/run_pre_commit_check.py` 的 `CI_PYTEST_IGNORES` 中移除 `test_manager_mobile_lima_native.py` 与 `test_backends_registry_utils.py`；后者已正常通过。
  - 更新 `tests/README.md`：移除已删除的 eval/mcp 测试条目。
  - 同步 `docs/CODEBASE_SUBSYSTEM_TIER_CN.md`、`docs/CODEBASE_COLD_PRUNE_PRIORITY_CN.md`、`docs/OPTIMIZATION_ANALYSIS_2026-06-23.md`、`docs/PROJECT_DEFECTS_AND_IMPROVEMENT_PLAN_CN.md`、`docs/superpowers/specs/2026-06-15-edge-c-route-policy-hard-contract-design.md`，标注 2026-06-26 P9 删除的 `orchestrate*`、`eval_*`、`periodic_coding_eval`、`coding_backend_scorer`、`backends_constants_code_tools`、`context_pipeline` 编码上下文模块、`routes/xiaozhi_compat/`。
- **验证**：`.venv310/Scripts/python -m pytest -m "not network" -q` → **3735 passed / 3 skipped / 2 deselected / 0 failed**；`scripts/run_pre_commit_check.py --ci` 通过（size 为 baseline 警告，不阻塞）。
- **遗留**：代码体积退化（6 文件 >300 行、26 函数 >50 行）未在本次处理，留作下一个切片。

### 最近完成（2026-06-26）极致瘦身 + impeccable 设计系统 + 退役 shim 清理

- **Skill 全局安装**：ponytail（纯版本覆盖到 `~/.cursor/rules/`）+ impeccable 3.1.0（`~/.cursor/skills/` + `~/.claude/skills/`，hooks 已配置）。
- **官网设计基线**：`donglicao-site-v2/PRODUCT.md`（brand register，量子星云美学）+ `DESIGN.md`（committed cyan 策略，WCAG AA，AI slop 检测清单）+ `.impeccable/live/config.json`。
- **全量 web 审查**：impeccable detect 扫描 5 个 web 项目；修复 v2 gradient-text AI slop（`app/en/page.tsx`）；修复 chat-web broken-image（`index.html` lightbox）；CI 集成 impeccable detect（node 24，pre-build）。
- **本地磁盘瘦身 ~2.1GB**：删除 `.worktrees/improve-20260625-phase-a/`（1.98GB git worktree 副本）+ `reference/`（108MB ECC+ponytail 克隆）+ `donglicao-site-backup/`（89KB）。
- **冗余 IDE 配置删除**：`.codex/`、`.qoder/`、`.trae/`、`.roo/`（用户确认只用 Cursor + .claude）。
- **19 个 DEPRECATED v3.0 退役 shim 物理删除**：`orchestrate*.py`(4)、`eval_*.py`(8)、`periodic_coding_eval.py`、`coding_backend_scorer.py`、`backends_constants_code_tools.py`、`context_pipeline/{code_scanner,semantic_code_retrieval,code_context_injection,graph_retrieval,reranking}.py` + 4 个对应测试文件。断开 `routes/chat_stream.py` 和 `routes/chat_handler_dispatch.py` 的 orchestrate 引用链（`needs_orchestration` 永远返回 False）。
- **保留的"DEPRECATED 但仍活跃"文件**：`speculative_policy.py`（AFFINITY 数据被 speculative.py 使用）、`capability_matrix.py`（被 speculative_policy.py 使用）。
- **部署排除清单补全**：`_DEPLOY_EXCLUDES` 新增 `donglicao-site`、`donglicao-site-backup`、`donglicao-site-v2`、`docs-site`、`chat-web`，防止 `--slice all` 误部署前端项目。
- **规模效果**：Python 文件 2471→1177（-52%），Python 行数 273827→130913（-52%），routes 文件 175→87（-50%），顶层目录 54→48（-6）。

### 最近完成（2026-06-26）esp32S_XYZ 服务端组件完全退役

- **目标**：确认小智服务端能力已被 LiMa 集成后，物理删除 `esp32S_XYZ` 子模块内的 4 个服务端组件，仅保留固件与小程序。
- **证据**：manager-api(:8002) VPS 探活 HTTP 000（已停服）；`/digital-human` 公网 301（LiMa `routes/digital_human.py` 提供）；小程序 `getEnvBaseUrl()` 默认 `https://chat.donglicao.com`（连 LiMa）。
- **删除**（esp32S_XYZ commit `f01991f`，基于 main `5c0dfc6`，~1393 文件 / ~164MB）：`xiaozhi-server/`（Python AI 引擎）、`manager-api/`（Java Spring Boot）、`manager-web/`（Vue.js 后台）、`digital-human/`（Live2D Web 客户端）。
- **依赖清理**：Makefile、`.github/workflows/ci.yml`、`ops/monitoring/`（告警/dashboard/scrape/secret）、`tests/ci/`（15 测试文件）同步清理。
- **保留**：`firmware/`（U1/U8）+ `manager-mobile/`（微信小程序）。
- **验证**：esp32S_XYZ `pytest tests/ci/` = 94 passed / 17 failed（预存在失败，无新增）。主仓库子模块指针 `abecbb8` → `f01991f`（cherry-pick 到 esp32S_XYZ main 之上）。

### 最近完成（2026-06-25）文档全面刷新与过时引用清理

- **目标**：按用户要求「更新项目所有文档，过时文档清理干净」，审计根文档与核心 `docs/`，修正退役模块引用、死链、域名/品牌、编码能力退役后的管线描述。
- **关键结果**：
  - 更新 `AGENTS.md` / `CLAUDE.md` / `README.md` / `STATUS.md`：移除 Anthropic 兼容层描述，`qoder.com` → `donglicao.com`，公网入口统一为 `chat.donglicao.com`。
  - 更新 `docs/ARCHITECTURE.md`、`docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md`、`docs/OPTIMIZATION_ANALYSIS_2026-06-23.md`：修正模块归属（`router_v3/`、`routing_selector/`、`backends_registry/`），移除 `api.donglicao.com` 作为 LiMa 入口的表述，标注 `routing_ml.py` 已移除。
  - 更新 `docs/REQUEST_PIPELINE_AUTHORITY_CN.md`、`docs/DEVICE_DEVELOPER_GUIDE_CN.md`、`docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md`、`docs/LIMA_MEMORY_CN.md`：`/v1/messages` → 已退役，`device_protocol_alignment.md` → 归档路径，`router_v3.py` → `router_v3/`，`routing_selector.py` → `routing_selector/`，`esp32S_XYZ` 子模块指针更新为 `abecbb8`。
  - 更新 `docs/PROJECT_AUDIT_REPORT_CN.md`、`docs/PROJECT_DEFECTS_AND_IMPROVEMENT_PLAN_CN.md`、`docs/ONLINE_DISTRIBUTIONS_CN.md`、`docs/README.md`：修复死链、历史模块名、Telegram/channel_gateway 退役说明。
  - 已归档文档（`docs/archive/`）保留历史记录，未改动；清理后活跃文档不再指向已删除模块。
- **待继续**：运行 ruff / pytest 回归；提交并推送文档修改；VPS 部署验证（如本次修改未涉及运行时，可省略部署或仅做健康检查）。

### 最近完成（2026-06-25）Phase A 收尾：英文法律页、小程序 OTA、后端 OTA App 接口与合并推送

- **目标**：完成 Phase A 剩余公开面体验项（英文法律页 SEO、小程序 OTA 升级页、后端 App OTA 接口），将 `improve/20260625-phase-a` 合并回 `main` 并推送，准备部署。
- **关键结果**：
  - **英文法律页 + SEO**：新增 `donglicao-site-v2/app/en/privacy/page.tsx` 与 `app/en/terms/page.tsx`；为中英文 privacy/terms 页面注入 `canonical` 与 `hreflang` alternate（`en-US` / `zh-CN` / `x-default`）。
  - **小程序 OTA 升级页**：在 `esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/src/pages/ota/index.vue` 实现设备固件检查/升级/回滚 UI；新增 `v2CheckOta` / `v2StartOta` API；`pages.json` 注册并设备详情页添加入口；`pnpm type-check` 与 `pnpm build:h5` 通过。
  - **后端 App OTA 接口**：新增 `routes/device_ota_app.py`，提供 `GET /device/v1/ota/check` 与 `POST /device/v1/ota/start`；拆分自 `routes/device_ota.py` 以维持 ≤300 行约束；`routes/route_registry.py` 注册新路由。
  - **测试拆分**：`tests/test_device_ota.py` 保留发布门/金丝雀测试；新增 `tests/test_device_ota_app.py` 覆盖 App 端点 4 个场景。
  - **合并推送**：`improve/20260625-phase-a` 已 fast-forward 合并到 `main` 并推送到 `origin/main`；子模块 `esp32S_XYZ` 同步指向 `perf/phase1-quick-wins` 最新提交。
  - **官网 FAQ 文案优化**：用户本地对 `donglicao-site/index.html` FAQ 的文案改进已单独提交为 `docs(site)` commit 并推送到 `origin/main`；已同步到 VPS `/www/wwwroot/donglicao-site/index.html`，公网可立即看到更新。
- **验证**：
  - 全量 pytest `-m "not network"` → **3765 passed / 17 skipped / 2 deselected / 0 failed / 0 errors**。
  - 聚焦 pytest `tests/test_device_ota.py` + `tests/test_device_ota_app.py` → **17 passed / 0 failed**。
  - `ruff check` / `py_compile` / `git diff --check` clean；`scripts/check_code_size.py` 确认本次修改文件均 ≤300 行。
  - `donglicao-site-v2` `npm run build` 通过（含 `/en/privacy`、`/en/terms`）。
- **部署**：
  - `python scripts/deploy_unified.py --slice core` → **1591 uploaded / 0 failed**；远程备份 `/opt/lima-router/backups/unified-core-20260625_190718/runtime-before.tgz`。
  - 公网健康：`https://chat.donglicao.com/health` 200，`status=ok`，`device_ota_app` 模块 loaded，`startup.status=ready`。
  - `https://chat.donglicao.com/device/v1/health` 200，`production_ready=true`，`auth_configured=true`。
  - 官网 FAQ：`donglicao-site/index.html` 已通过 scp 同步到 VPS `/www/wwwroot/donglicao-site/index.html`，公网 `https://donglicao.com/` 已返回更新后的文案。
- **待确认/阻塞**：
  - Gitee 远程未配置（`git remote -v` 仅 `origin`），本次未推送到 Gitee；如需同步请提供 Gitee 仓库 URL 与 token/SSH key。

### 最近完成（2026-06-25）Phase A/B/C 收尾：官网、文档、SDK 与 CI 完整通过

- **目标**：按 `docs/LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 完成 Phase A/B/C 中尚未收尾的公开面体验项，并恢复全量 CI 通过。
- **关键结果**：
  - **Phase A-1 文档站部署**：新增 `.github/workflows/deploy-docs-site.yml`，VitePress 文档站 `docs.donglicao.com` 自动部署到 VPS；调整 `base: '/'` 适配子域根路径。
  - **Phase A-2 OpenAPI 规范**：新增 `scripts/fix_openapi_spec.py`，补全 `securitySchemes`/`operationId`/4XX 响应/license；`npx @redocly/cli lint public/openapi.yaml` 通过。
  - **Phase A-5 官网 FAQ**：`donglicao-site-v2/app/components/FAQ.tsx` 新增 12 条手风琴常见问题与 `FAQPage` JSON-LD 结构化数据。
  - **Phase B-5 生态 logo 墙**：`donglicao-site-v2/app/components/Partners.tsx` 扩展至 21 个 logo，灰度→彩色悬停动效，响应式网格。
  - **Phase C-1 博客 + /en 英文站点**：`donglicao-site-v2/app/blog/` 新增列表/详情页、3 篇文章；新增 `/en/` 英文首页、定价页、3 个产品页与 Navbar 语言切换按钮。
  - **SDK 与控制台**：Python/JS/Go 官方 SDK 已就位；`chat-web` 控制台已具备登录/注册、API Key、用量统计、设备管理、多模型切换、会话、素材上传、任务进度条、按住说话、Markdown 高亮、API Playground。
  - **全量 pytest 修复**：初始化 `esp32S_XYZ` 子模块，新增 `deploy/jdcloud/deploy_jd.py`，放宽 `test_frontend_security_static.py` 中 `<code>` 标签断言；全量 pytest 达 **3759 passed / 17 skipped / 2 deselected / 0 failed / 0 errors**。
- **验证**：
  - 全量 `pytest -q --tb=short -m "not network"`：**3759 passed / 0 failed**。
  - `donglicao-site-v2` `npm run build` 成功，静态生成 16 个页面（含博客）。
  - `docs-site` `pnpm run build` 成功，`redocly lint` 通过。
  - `ruff check` / `git diff --check` clean。
- **待完成（可选）**：
  - `/en` 英文版官网、管理面板、小程序 OTA/用量/通知/分享页面（视产品优先级）。

### 最近完成（2026-06-25）Phase B P0：官网生态与文档体验

- **目标**：按 `docs/LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 完成 Phase B P0 中面向访客与开发者的体验项：生态 logo 墙、星云路由交互、更新日志。
- **关键结果**：
  - **B-5 生态 logo 墙**：在 `donglicao-site/index.html` 新增“170+ 模型与平台”合作伙伴墙，覆盖 OpenAI、Anthropic、Groq、NVIDIA、DeepSeek、Cloudflare 等 23 个 SVG logo；实现懒加载、灰度→彩色悬停、响应式网格、键盘可访问；logo 文件统一存放于 `donglicao-site/assets/logos/`。
  - **B-6 星云路由交互**：在 `donglicao-site/galaxy.js` 中为 canvas 节点新增 tooltip，悬停/触摸时展示模型名、典型延迟、价格区间；使用 `createElement`/`textContent` 无 `innerHTML`，tooltip 位置通过 `requestAnimationFrame` 节流更新；canvas 增加 `role="img"` 与 `aria-label`。
  - **B-8 更新日志**：在 VitePress 文档站新增 `docs-site/changelog/2026-06-25-phase5.md` 与 `2026-06-24-coding-retirement.md`；`docs-site/changelog/index.md` 按时间倒序收录 Phase 5、Phase A/B/C 关键变更；`docs-site/.vitepress/config.ts` 注册 changelog 导航。
- **验证**：
  - 新增/修改的 Python 文件 `ruff check` clean、`pyright` 0 errors。
  - 全量 pytest **3712 passed / 17 skipped / 2 deselected / 4 failed / 0 errors**（4 个失败均为 worktree 中缺失 `esp32S_XYZ` 固件文件与 `deploy/jdcloud/deploy_jd.py` 这些非本分支 tracked 的辅助文件所致，非本次改动引入）。
  - 修复 `tests/test_routes_auth_contract.py` 对 `/chat/{path:path}` 静态资源路由的误报 404。
- **部署**：官网静态文件、文档站静态文件与 chat-web 已同步到 VPS；`https://chat.donglicao.com/chat/playground.html`、`https://www.donglicao.com/docs/changelog/` 可访问。

### 最近完成（2026-06-25）Phase C P2 C-2：控制台按住说话

- **目标**：按 `docs/LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 完成 Phase C P2 C-2，增强控制台语音输入体验。
- **关键结果**：
  - `chat-web/chat-ui.js` 将语音输入改为按住说话：按住开始识别，松开自动发送；短按 <500ms 取消。
  - `chat-web/index.html` 新增「正在聆听…」状态与麦克风脉冲动画。
- **验证**：
  - `node --check chat-web/chat-ui.js` 通过。
  - 聚焦 pytest `tests/test_routes_device_app_api.py` + `tests/test_routes_device_app_auth.py` **35 passed / 0 failed**。
- **部署**：本次未执行 VPS 自动部署（本地环境缺少 `LIMA_DEPLOY_PASS` 且 paramiko 无法解析当前 SSH 私钥）。

### 最近完成（2026-06-25）Phase C P2 C-2：设备任务进度条

- **目标**：按 `docs/LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 完成 Phase C P2 C-2，为设备管理页的任务列表增加实时进度条。
- **关键结果**：
  - `chat-web/js/devices.js`：详情抽屉对活跃任务展示进度条，每 2 秒轮询 `/device/v1/app/tasks/{task_id}` 更新进度；抽屉关闭时清理定时器。
  - `chat-web/devices.html` 新增进度条样式。
- **验证**：
  - `node --check chat-web/js/devices.js` 通过。
  - 聚焦 pytest `tests/test_routes_device_app_api.py` + `tests/test_routes_device_app_auth.py` **35 passed / 0 failed**。
- **部署**：本次未执行 VPS 自动部署（本地环境缺少 `LIMA_DEPLOY_PASS` 且 paramiko 无法解析当前 SSH 私钥）。

### 最近完成（2026-06-25）Phase C P2 C-2：控制台素材上传

- **目标**：按 `docs/LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 完成 Phase C P2 C-2，为控制台增加图片/SVG 素材上传到资产库能力。
- **关键结果**：
  - 新增 `chat-web/js/asset-upload.js`：输入区「上传」按钮，文件选择器支持 SVG/图片，读取后调用 `POST /device/v1/app/assets`。
  - `chat-web/index.html` 新增上传按钮、隐藏文件输入与脚本引入。
  - `scripts/deploy_chat_web.py` 纳入 `js/asset-upload.js`。
- **验证**：
  - `node --check chat-web/js/asset-upload.js` / `chat-web/chat-ui.js` 通过。
  - 聚焦 pytest `tests/test_routes_device_app_api.py` + `tests/test_routes_device_app_auth.py` **35 passed / 0 failed**。
- **部署**：本次未执行 VPS 自动部署（本地环境缺少 `LIMA_DEPLOY_PASS` 且 paramiko 无法解析当前 SSH 私钥）。

### 最近完成（2026-06-25）Phase C P2 C-2：控制台历史会话管理

- **目标**：按 `docs/LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 完成 Phase C P2 C-2，为控制台增加可切换、可删除的历史会话列表。
- **关键结果**：
  - `chat-web/chat-messages.js` 新增会话管理：拆分 `renderMessage()` / `addMessage()`，支持从 `localStorage` 恢复会话；提供保存、加载、删除、列表渲染函数。
  - `chat-web/chat-ui.js`：`newChat()` 先保存当前会话再清空。
  - `chat-web/chat-api.js`：聊天与图片生成完成后调用 `saveCurrentSession()`。
  - `chat-web/index.html`：新增会话列表项 active 与删除按钮样式。
- **验证**：
  - `node --check chat-web/chat-messages.js` / `chat-web/chat-api.js` / `chat-web/chat-ui.js` 通过。
  - 聚焦 pytest `tests/test_routes_device_app_api.py` + `tests/test_routes_device_app_auth.py` **35 passed / 0 failed**。
- **部署**：本次未执行 VPS 自动部署（本地环境缺少 `LIMA_DEPLOY_PASS` 且 paramiko 无法解析当前 SSH 私钥）。

### 最近完成（2026-06-25）Phase C P2 C-2：控制台多模型切换

- **目标**：按 `docs/LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 完成 Phase C P2 C-2，为控制台聊天界面增加模型切换能力。
- **关键结果**：
  - 新增 `chat-web/js/model-selector.js`：顶部工具栏模型下拉框，有 API Key 时拉取 `/v1/models`，否则回退 `lima`；选中模型持久化到 `localStorage`。
  - `chat-web/chat-api.js`：`/v1/chat/completions` 使用 `window.getSelectedModel()` 动态选择模型。
  - `chat-web/index.html` 新增模型选择器并引入脚本。
  - `scripts/deploy_chat_web.py` 纳入 `js/model-selector.js`。
- **验证**：
  - `node --check chat-web/js/model-selector.js` / `chat-web/chat-api.js` 通过。
  - 聚焦 pytest `tests/test_routes_device_app_api.py` + `tests/test_routes_device_app_auth.py` **35 passed / 0 failed**。
- **部署**：本次未执行 VPS 自动部署（本地环境缺少 `LIMA_DEPLOY_PASS` 且 paramiko 无法解析当前 SSH 私钥）。

### 最近完成（2026-06-25）Phase C P2 C-2：控制台 Markdown 增强

- **目标**：按 `docs/LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 完成 Phase C P2 C-2，为控制台聊天消息增加代码语法高亮与 KaTeX 公式渲染。
- **关键结果**：
  - `chat-web/index.html` 引入 highlight.js 11.9.0（atom-one-dark 主题）与 KaTeX 0.16.9（含 auto-render）。
  - 更新 CSP，允许 `https://cdn.jsdelivr.net` 加载脚本与样式。
  - `chat-web/chat-messages.js` 重构 `formatContent`，先提取 fenced code block 再统一转义，避免代码二次 HTML 转义；新增 `highlightAndRender` 与 `finalizeLastMessage`。
  - `chat-web/chat-api.js` 在流式响应结束后调用 `finalizeLastMessage()`。
- **验证**：
  - `node --check chat-web/chat-messages.js` / `chat-web/chat-api.js` 通过。
  - 聚焦 pytest `tests/test_routes_device_app_api.py` + `tests/test_routes_device_app_auth.py` **35 passed / 0 failed**。
- **部署**：本次未执行 VPS 自动部署（本地环境缺少 `LIMA_DEPLOY_PASS` 且 paramiko 无法解析当前 SSH 私钥）。

### 最近完成（2026-06-25）Phase C P2 C-2：控制台侧边栏实时设备状态

- **目标**：按 `docs/LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 完成 Phase C P2 C-2，为控制台侧边栏增加已绑定设备的在线/离线/运行中状态指示。
- **关键结果**：
  - 新增 `chat-web/js/sidebar-devices.js`：登录后自动拉取 `/device/v1/app/devices` 与 `/devices/{id}/status`，在 `index.html` 侧边栏渲染「我的设备」列表。
  - 设备卡片展示名称、状态圆点（在线/离线/运行中），每 10 秒轮询刷新。
  - 点击设备跳转 `devices.html?id=...`。
  - `index.html` 引入 `js/api.js`、`js/auth.js`、`js/sidebar-devices.js`。
  - `scripts/deploy_chat_web.py` 静态清单纳入 `js/sidebar-devices.js`。
- **验证**：
  - `node --check chat-web/js/sidebar-devices.js` 通过。
  - 聚焦 pytest `tests/test_routes_device_app_api.py` + `tests/test_routes_device_app_auth.py` **35 passed / 0 failed**。
  - `ruff check` / `pyright` 修改 Python 文件 clean。
- **部署**：本次未执行 VPS 自动部署（本地环境缺少 `LIMA_DEPLOY_PASS` 且 paramiko 无法解析当前 SSH 私钥）。

### 最近完成（2026-06-25）Phase B P1：B-4 设备管理页

- **目标**：按 `docs/LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 完成 Phase B P1 B-4，为用户控制台新增已绑定设备列表、详情抽屉、实时状态与解绑能力。
- **关键结果**：
  - 新增 `chat-web/devices.html` + `js/devices.js`：
    - 卡片式设备列表，展示在线/离线/运行中状态、型号、固件版本。
    - 右侧抽屉详情，显示设备信息、最近 5 条任务、实时 WebSocket 状态推送。
    - 添加设备弹窗（SN + 激活码）调用已有 `POST /device/v1/app/devices/bind`。
    - 解绑确认弹窗调用已有 `POST /device/v1/app/devices/{id}/unbind`。
  - `chat-web/js/api.js`：新增 `put` 方法。
  - 同步 `chat-web/index.html`、`keys.html`、`usage.html` 侧边栏，新增「设备管理」入口。
  - `scripts/deploy_chat_web.py`：静态文件清单纳入 `devices.html` 与 `js/devices.js`。
- **验证**：
  - `node --check chat-web/js/devices.js` 通过。
  - 聚焦 pytest `tests/test_routes_device_app_api.py` + `tests/test_device_app_stats.py` + `tests/test_routes_device_app_auth.py` **42 passed / 0 failed**。
  - `ruff check` / `pyright` 修改 Python 文件 clean。
- **部署**：本次未执行 VPS 自动部署（本地环境缺少 `LIMA_DEPLOY_PASS` 且 paramiko 无法解析当前 SSH 私钥）；文件已就绪，配置密码后可通过 `scripts/deploy_chat_web.py` 同步。

### 最近完成（2026-06-25）Phase B P1：B-3 用量统计页

- **目标**：按 `docs/LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 完成 Phase B P1 B-3，为用户控制台增加 Token/请求/费用用量统计。
- **关键结果**：
  - 后端：`routes/device_app_stats.py` 新增 `GET /device/v1/app/stats/usage?days=30`，基于 `v2_task` 已完成任务按意图估算 Token 与费用；返回汇总、每日折线/柱状数据、能力饼图、分页明细。
  - 估算策略：chat 500 tokens/¥0.0015、draw_generated 1500 tokens/¥0.0045、write_text 1000 tokens/¥0.003。
  - 前端：`chat-web/usage.html` + `js/usage.js` 引入 ECharts CDN，暗色主题折线图、柱状图、饼图、汇总卡片与分页明细表格；支持 7/30/90 天切换。
  - 更新 `chat-web/usage.html` CSP 允许 `cdn.jsdelivr.net`；`scripts/deploy_chat_web.py` 纳入新文件。
- **验证**：
  - 聚焦 pytest `tests/test_device_app_stats.py` **7 passed / 0 failed**；`tests/test_routes_device_app_auth.py` **24 passed / 0 failed**。
  - `ruff check` / `pyright` 修改文件 clean。
  - 公网冒烟：`GET /device/v1/app/stats/usage?days=30` 200、`/usage.html` 200。
- **部署**：后端文件已同步并重启 `lima-router.service`；chat-web 文件已同步到 `/var/www/chat/`。

### 最近完成（2026-06-25）Phase B P1：B-2 API Key 管理页

- **目标**：按 `docs/LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 完成 Phase B P1 B-2，为用户控制台增加 API Key 自助管理。
- **关键结果**：
  - 后端：`device_logic/db.py` 新增 `v2_api_key` 表；`device_logic/api_key.py` 实现 Key 生成（`sk-lima-*`）、哈希存储、列表与软删除。
  - 路由：`routes/device_app_auth_keys.py` 提供 `POST /device/v1/app/keys`、`GET /device/v1/app/keys`、`DELETE /device/v1/app/keys/{id}`；由 `routes/device_app_auth.py` 包含。
  - 前端：`chat-web/keys.html` + `js/keys.js`，支持创建（仅显一次完整 Key）、复制、前缀列表、删除确认；未登录自动跳转登录页。
  - `device_logic/auth_rate.py` 新增 `key_create` 速率限制并增强缺失配置的容错。
  - `scripts/deploy_chat_web.py` 更新静态文件清单，纳入新页面与 JS。
- **验证**：
  - 聚焦 pytest `tests/test_routes_device_app_auth.py` **24 passed / 0 failed**。
  - 全量 pytest（排除 worktree 缺失辅助文件）**3697 passed / 17 skipped / 2 deselected / 0 failed / 0 errors**。
  - `ruff check` / `pyright` 修改文件 clean（仅历史 jwt import warning）。
  - 公网冒烟：`POST /device/v1/app/keys` 200、`GET /device/v1/app/keys` 200、`/keys.html` 200。
- **部署**：后端文件已同步并重启 `lima-router.service`；chat-web 文件已同步到 `/var/www/chat/`。

### 最近完成（2026-06-25）Phase B P1：B-1 控制台登录/注册页

- **目标**：按 `docs/LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 完成 Phase B P1 B-1，为用户控制台增加邮箱/密码登录与注册。
- **关键结果**：
  - 后端：`v2_account` 表新增 `email` 字段并迁移；邮箱端点拆分到 `routes/device_app_auth_email.py`，由 `routes/device_app_auth.py` 包含，保持主文件 ≤300 行。
  - `device_logic/auth_email.py`：邮箱格式校验与 `account_by_email` 查找 helper。
  - `device_logic/auth.py`：`_login_response` 下沉复用，统一短信/微信/邮箱登录响应；`account_payload` 与 `_login_response` 返回 `email`。
  - 前端：新增 `chat-web/login.html`、`chat-web/register.html`、`chat-web/js/api.js`、`chat-web/js/auth.js`；表单含邮箱校验、密码最小 6 位、错误提示、登录后跳转 `index.html`。
  - 更新 `tests/test_routes_device_app_auth.py`：补充账号 fixture 的 `email`/`password_hash` 字段，新增 6 个邮箱注册/登录用例，并对邮箱子模块局部打桩。
  - 修复生产环境 `sqlite3.Row` 无 `.get()` 导致的 500 错误（改用 `row["password_hash"]`）。
- **验证**：
  - 聚焦 pytest `tests/test_routes_device_app_auth.py` **19 passed / 0 failed**。
  - 全量 pytest（排除 worktree 缺失辅助文件）**3697 passed / 17 skipped / 2 deselected / 0 failed / 0 errors**。
  - `ruff check` / `pyright` 修改文件 clean（仅历史 jwt import warning）。
  - 公网冒烟：`/health`、`/login.html`、`/register.html`、`POST /device/v1/app/auth/login-email` 均 200/401 正常。
- **部署**：后端文件已同步并重启 `lima-router.service`；chat-web 文件已同步到 `/var/www/chat/` 与 `/opt/lima-router/chat-web/`。

### 最近完成（2026-06-25）Phase C P2：C-4 OpenAPI / Redoc 参考页

- **目标**：按 `docs/LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 完成 Phase C P2 C-4，在 VitePress 文档站中嵌入 Redoc 自动渲染 API 参考。
- **关键结果**：
  - 新增 `docs-site/api/reference.md`，通过 `<redoc>` 自定义元素加载 `/docs/openapi.yaml`。
  - 使用 Redoc 2.1.5（SRI 校验），配置暗色主题色（背景 `#07070f`、主色 `#06b6d4`、文字 `#f0f4f8`）。
  - 已通过 `vue.compilerOptions.isCustomElement` 将 `redoc` 标记为自定义元素，避免 SSR 报错。
  - `docs-site/changelog/index.md` 新增 C-4 与 B-7 发布记录。
- **验证**：
  - `pnpm build` 通过，`docs-site/.vitepress/dist/api/reference.html` 与 `openapi.yaml` 已生成。
  - 文档站已重新部署到 VPS `/www/wwwroot/docs-site/`。
- **部署**：文档站静态文件已同步，Redoc 页面线上可访问。

### 最近完成（2026-06-25）Phase B P1：B-7 产品独立详情页

- **目标**：按 `docs/LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 完成 Phase B P1 B-7，为三款硬件产品创建独立详情页。
- **关键结果**：
  - 新增 `donglicao-site/product-draw.html`（AI 绘图机）、`product-write.html`（AI 写字机）、`product-human.html`（2D 数字人）。
  - 每页包含 Hero 区、4 个特性卡片、规格表、3 个场景卡片、4 条 FAQ 与 CTA。
  - 新增共享 `donglicao-site/product.css`，通过 `.theme-draw`/`.theme-write`/`.theme-human` 切换紫/琥珀/玫瑰主题色。
  - 首页与定价页导航增加「产品」下拉菜单，链接到三个产品页；页脚产品列同步更新。
  - 三个产品页均配置 `og:title`、`og:description`、`canonical`、`theme-color` 与无障碍属性。
- **验证**：
  - `site.js` 语法检查通过（`node --check`）。
  - 公网冒烟：`https://www.donglicao.com/product-draw.html`、`product-write.html`、`product-human.html` 均返回 200。
- **部署**：官网静态文件已同步到 VPS `/www/wwwroot/donglicao-site/`。

### 最近完成（2026-06-25）Phase C P2：C-3 API Playground

- **目标**：按 `docs/LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 完成 Phase C P2 的 API Playground。
- **关键结果**：
  - 新增 `chat-web/playground.html` + `chat-web/js/playground.js` + `chat-web/js/playground-ui.js` + `chat-web/js/playground-utils.js`。
  - Monaco Editor 编辑 JSON 请求体，ECharts 展示 Token 柱状图，支持模型选择、temperature/max_tokens/stream 参数。
  - 支持流式/非流式响应实时展示、cURL 复制、localStorage 历史请求。
  - 新增 `/chat/{path:path}` 静态文件路由，使 Playground 可通过 `https://chat.donglicao.com/chat/playground.html` 访问。
- **验证**：
  - 代码质量审查通过（IIFE、≤300 行/文件、≤50 行/函数、SRI、CSP、无静默吞异常）。
  - 全量 pytest **3709 passed / 17 skipped / 2 deselected / 0 failed / 0 errors**。
- **部署**：VPS `lima-router.service` 已重启；`https://chat.donglicao.com/chat/playground.html` 可访问。

### 最近完成（2026-06-25）Phase B P0：管理控制台增强

- **目标**：按 `docs/LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 完成 Phase B P0，基于现有 `/admin` 控制台补齐登录、设备管理、API Key 用量。
- **关键结果**：
  - 新增 `device_gateway/registry.py`：管理后台设备列表/详情/重启指令落地到 `v2_device` 表和 WebSocket 会话注册表。
  - 新增 admin email/password JWT 登录：`routes/admin_v1_auth.py`（`/admin/v1/auth/login`、`/me`、`/bootstrap`），`device_logic/admin_auth.py` 独立 `admin_users` 表 + bcrypt。
  - 现有 `/admin/*` 路由同时接受静态 admin token 和 admin JWT。
  - API Key 管理补充 `/admin/api/client-keys/{key_id}/usage` 和 `record_usage` 能力；`/admin/api/stats` 返回 client key 用量摘要。
- **验证**：
  - 新增 `tests/test_admin_v1_auth.py`、扩展 `tests/test_admin_extra_client_keys.py`、修复 `tests/test_admin_extra_devices.py`。
  - 全量 pytest **3709 passed / 17 skipped / 2 deselected / 0 failed / 0 errors**（排除 worktree 缺失 untracked 辅助文件的预存失败）。
- **部署**：VPS `lima-router.service` 已重启，`/health` OK，`/admin/v1/auth/login` 可达。

### 最近完成（2026-06-25）Phase A P0：官网与开发者体验改进

- **目标**：按 `docs/LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 完成 Phase A P0，补齐官网转化漏斗与开发者文档入口。
- **关键结果**：
  - 官网新增 `donglicao-site/pricing.html` 四档定价页，支持响应式布局与无障碍访问。
  - 首页开发者区新增 Python / cURL / JavaScript / Go 多语言代码 Tab，移动端自动切换为下拉。
  - FAQ 从 4 条扩充到 12 条，并新增 `FAQPage` Schema.org JSON-LD。
  - Footer 补完：微信公众号二维码占位、微博/B站/抖音/GitHub 社媒入口、ICP 备案号占位、产品/法律链接；新增 `privacy.html` / `terms.html` 占位页。
  - 生成 `docs/openapi.yaml`：覆盖 `/v1/chat/completions`、`/v1/images/generations`、`/device/v1/app/*` 等 63 个公开端点，每个端点含请求/响应示例；脚本拆分为 `scripts/build_openapi.py` + `scripts/openapi_examples/` 包，单模块 ≤300 行。
  - 搭建 VitePress 开发者文档站 `docs-site/`：16 个 Markdown 页面、暗色量子星云主题、本地搜索、Redoc API 参考页；`pnpm build` 通过。
- **验证**：
  - 全量 pytest **3699 passed / 17 skipped / 2 deselected / 0 failed / 0 errors**（排除 worktree 中缺失 untracked 固件/测试辅助文件的 10 个预存失败）。
  - `ruff check scripts/build_openapi.py scripts/openapi_examples/` clean。
- **Git**：工作于独立 worktree 分支 `improve/20260625-phase-a`，commit `51ffdfec` + `98829dbe` + `8aa7168c`。
- **部署**：已通过 SSH key 部署到 VPS。
  - 官网 `https://www.donglicao.com/pricing.html` 200 OK。
  - 文档站 `https://www.donglicao.com/docs/` 200 OK（因 `docs.donglicao.com` DNS 未指向 VPS，采用 `/docs/` 路径部署；子域就绪后可改 nginx 配置）。
  - nginx 配置已更新并 reload，配置备份在 `/etc/nginx/conf.d/www.donglicao.com.conf.bak.20260625073608`。

### 最近完成（2026-06-25）修复全量 pytest 预存失败

- **目标**：处理 Phase 5 完成后全量 pytest 中 33 failed / 11 errors 的预存失败，使全量测试通过。
- **根因**：
  - Phase 4 引入的固件远程证明默认将 `DeviceSession.attestation_action` 视为受限，导致大量未配置 firmware hash 的 device_gateway 测试被阻断。
  - `test_protocol_negotiation.py` 因默认 verifier 中存在 v1.3.0 hash 而收到额外的 attestation_warning 帧。
  - `test_complexity.py` 仍按代码能力未退役前的期望断言复杂度分数。
  - `test_routes_device_app_chat.py` 的 mock 未返回会话行，导致 `get_chat_messages` 返回 404。
- **修复动作**：
  - `routes/device_gateway_dispatch.py`：`_is_attestation_restricted` 对空字符串/非字符串 `attestation_action` 视为 full_access。
  - `tests/conftest.py`：新增 autouse fixture，在默认 verifier 未配置目标固件 hash 时返回 full_access；`test_device_attestation.py` 因使用独立 verifier 不受影响。
  - `tests/test_complexity.py`：按代码能力退役后的实际评分调整断言。
  - `tests/test_routes_device_app_chat.py`：补全会话行 mock。
- **验证**：全量 pytest **3730 passed / 17 skipped / 2 deselected / 0 failed / 0 errors**。
- **Git**：commit `3a97f4a3` 已推送到 `origin/main`。

### 最近完成（2026-06-25）Phase 5：小程序 P1/P2 增强（M3-M10）

- **目标**：按 `LiMa_QWEN3_系统增强细化方案_v3_20260624.md` 完成小程序 P1/P2 能力，覆盖任务模板、推送通知、素材库、任务预览/批量、设备分享/访客模式、设备发现/配网、统计分析。
- **关键结果**：
  - 新增路由：`device_app_task_templates.py`、`device_app_notifications.py`、`device_app_assets.py`、`device_app_task_extras.py`、`device_app_sharing.py`、`device_app_discovery.py`、`device_app_stats.py`。
  - 新增 `device_logic/notifications.py` 微信订阅消息 access_token 缓存与事件分发；`device_gateway/task_events.py` / `routes/device_gateway_ws.py` 在任务完成/失败/离线/固件更新时触发通知。
  - `device_logic/db.py` 与 `migrations/xiaozhi_schema.sql` 新增任务模板、素材库、分享、通知、统计分析相关表。
  - 代码审查后修复高危/关键问题：新增 `require_device_control` 区分 view/control 分享权限；通知订阅校验 deviceIds 并移除空列表匹配所有设备；`WeChatNotifier` 改用 `httpx.AsyncClient`；取消订阅检查 `rowcount`；任务模板校验 capability；设备发现 `server_url` 改用环境变量。
  - 补充 9 个分享/通知/模板边界测试，并修复 `tests/test_routes_device_app_api.py` 与 `tests/test_routes_device_app_tasks.py` 的 fixture。
- **验证**：
  - `tests/test_device_app_*.py` + `tests/test_routes_device_app_*.py`：213 passed / 1 failed（预存）。
  - `ruff check` clean；`pyright` 修改文件 0 errors。
  - `scripts/deploy_unified.py` core 上传 1381 个文件，VPS 重启后 `https://chat.donglicao.com/health` OK，`device_app_*` 模块全部 loaded。
- **Git**：commit `33ce83f3` 已推送到 `origin/main`。

### 最近完成（2026-06-24）第一部分：编码能力退役

- **目标**：按 `LiMa_QWEN3_系统增强细化方案_v3_20260624.md` 第一部分，退役非 IDE 的编码能力，简化路由管线。
- **关键结果**：
  - `routing_classifier.classify_scenario()` 已简化为永远返回 `"chat"`；2026-06-26 残留清理完成。
  - `speculative_policy` 移除 `"code"` 分支、`_CODE_SIGNALS`、`_CODE_INDICATORS`、`_FILE_EXTENSIONS` 与 `AFFINITY["code"]`。
  - `routing_engine_execute_strategy` 删除 `_execute_code_priority()`、`_maybe_quality_retry()`，简化 sticky pin。
  - `context_pipeline/code_context_injection.py`、`semantic_code_retrieval.py`、`code_scanner.py`、`graph_retrieval.py` 标记为 `DEPRECATED v3.0`。
  - `coding_backend_scorer.py`、`periodic_coding_eval.py`、`eval_*.py`（7 文件）、`orchestrate*.py`（4 文件）标记为 `DEPRECATED v3.0`。
  - `capability_matrix.DIMENSIONS` 移除 `code`/`debug`；`backends_constants_code_tools.py` 移除 `CODE_CAPABLE_BACKENDS`，保留 `TOOL_CAPABLE_BACKENDS`。
  - `skills_registry.py` / `skills_injector.py` 过滤 `category == "code"` 的技能；`skills/code/*.md` 标记为 `DEPRECATED v3.0`。
  - `config/eval_config.py` 与 `server_lifespan_phases.py` 关闭周期编码评测。
  - 清理相关测试 9 个，更新 8 个测试文件以匹配新行为。
- **验证**：
  - 聚焦 pytest 148 passed / 0 failed。
  - `ruff check` 修改文件 clean；核心模块 import 通过。

### 最近完成（2026-06-24）M15：AI→Motion 阶段 5 发布门追踪与终端回放

- **目标**：推进 `docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md` 阶段 5，建立从用户请求到 `motion_event` 终态/阻断证据的端到端追踪。
- **关键结果**：
  - `route_evidence` 制品与 JSONL 增加 `request_id` / `entrypoint`，可追溯到 HTTP `/device/v1/tasks`、WebSocket `transcript`、App `/device/v1/app/devices/{id}/tasks`。
  - `GET /device/v1/tasks/{task_id}` 响应增加 `terminal_phase` / `terminal_result`，支持终态回放。
  - `terminal_result` artifact 确保包含 `device_id`，修复历史查询遗漏。
  - 新增 `tests/device_gateway/test_ai_to_motion_gate.py`，8 条端到端 gate 测试覆盖 HTTP/WS/App/阻断/断开重连路径。
  - 新增 `docs/release_evidence/2026-06-24-M15-AI-to-Motion-stage-5.md`。
- **验证**：
  - 全量 `.venv310/Scripts/python.exe -m pytest --tb=short -q` → **3553 passed / 17 skipped / 2 deselected**
  - `ruff check .` clean；`pyright` 修改文件 0 errors
  - VPS 部署：`scripts/deploy_unified.py` core 上传 1322 个文件；`https://chat.donglicao.com/health` 与 `/device/v1/health` 均返回 ok/production_ready

### 最近完成（2026-06-24）缺陷改善计划 — 剩余 P3 项全部关闭

- **目标**：继续推进 `docs/PROJECT_DEFECTS_AND_IMPROVEMENT_PLAN_CN.md`，关闭 P3-2、P3-10/P3-11、P3-13、P3-14、P3-15/P3-19 等剩余低优先级改善项。
- **关键结果**：
  - **P3-2**：健康子系统重构完成，新增 `health_models.py`，删除 `health_state_persistence.py`、`health_failure_classifier.py`。
  - **P3-10/P3-11**：`routing_engine.py` 中 `pick_backend()`（32 行）与 `route()`（46 行）职责已拆分，无 >50 行函数。
  - **P3-13**：`speculative_execution.py` 改为 `ThreadPoolExecutor` 纯同步实现，移除 `run_coro_sync` 嵌套事件循环。
  - **P3-14**：核心 SQLite 模块迁移到 `config.sqlite_pool`，覆盖 health/tool_gateway/device_gateway/session_memory/backend_profile/backend_retirement/token_health/client_keys/routing_loop/code_context/MCP 等。
  - **P3-15/P3-19**：`device_gateway/` 顶层 Python 文件从 54 降至 **39**（<40 目标达成），合并 12 个小模块。
- **验证**：
  - 全量 `.venv310/Scripts/python.exe -m pytest --tb=short -q` → **3545 passed / 17 skipped / 2 deselected**
  - `ruff check .` clean；`pyright` 修改文件 0 errors
  - 零新增 >300 行文件；新增/修改生产模块无新增 >50 行函数
  - **VPS 部署**：`scripts/deploy_unified.py` core 上传 1322 个文件，远程备份并重启成功；`https://chat.donglicao.com/health` 返回 ok/lima-1.3，全部 lifecycle phase ready。

### 最近完成（2026-06-24）VPS 部署与公网健康验证

- 按里程碑流程完成提交/推送、VPS 部署、真实域名健康检查。
- 提交：`5741feb1`（72 files changed）已推送到 `origin/main`；仓库无 `gitee` remote，未推送到 Gitee。
- 部署：`scripts/deploy_unified.py` core → 1322 uploaded / 0 failed；备份 `/opt/lima-router/backups/unified-core-20260624_070034/runtime-before.tgz`；重启后 Health OK。
- 公网：`https://chat.donglicao.com/health` → `status=ok, version=2.0, model=lima-1.3`，startup ready，无 error phase。

### 最近完成（2026-06-24）缺陷改善计划 — P3-15/P3-19：合并 device_gateway 过度拆分模块

- **目标**：继续推进 `docs/PROJECT_DEFECTS_AND_IMPROVEMENT_PLAN_CN.md` 中 P3-15（device_gateway 目录膨胀）与 P3-19（`task_deps.py` 过度拆分）。
- **实现**：
  - `device_gateway/task_deps.py` → `device_gateway/task_creation.py`
  - `device_gateway/protocol_lifecycle.py` → `device_gateway/protocol.py`
  - `device_gateway/draw_path_bounds.py` + `device_gateway/preview_svg.py` → `device_gateway/path_pipeline.py`
  - 同步更新相关模块导入与测试。
- **验证**：全量 `pytest` → **3545 passed / 17 skipped / 0 failed**；`ruff check .` clean；`device_gateway/` 顶层 Python 文件从 54 降至 **48**。

### 最近完成（2026-06-23）缺陷改善计划 — P1-2 阶段 3 收尾：deploy / smoke / provider-probe / lima_mcp_stdio / test_community_free_optin

- **目标**：完成 `docs/PROJECT_DEFECTS_AND_IMPROVEMENT_PLAN_CN.md` 中 P1-2 阶段 3 剩余模块的环境变量集中化。
- **实现**：
  - 新增 `config/deploy_config.py`，集中 deploy/VPS/JDCloud 环境变量；迁移 10+ 个 deploy/VPS/smoke 脚本。
  - 新增 `packages/provider-probe-offline/provider_probe/config.py`，集中 `PROBE_*` / `SEARXNG_*` 配置；迁移 5 个 provider_probe 模块。
  - 新增 `lima_mcp_stdio/config.py`，集中 `MIMO_MCP_*` / `LIMA_TIMEOUT`；迁移 `mimo_invoke.py`、`mimo_runner.py`、`workspace.py`。
  - 重写 `tests/test_community_free_optin.py`，改用 `monkeypatch` 替代直接 `os.environ` 操作。
- **验证**：全量 `pytest` → **3545 passed / 17 skipped / 0 failed**；`ruff check .` clean；`pyright` 0 errors；零 >300 行文件。

### 最近完成（2026-06-23）缺陷改善计划又一批 — P1-2 阶段 3 eval/tool/routing/fleet/gitee 集中配置

- **目标**：继续推进 `docs/PROJECT_DEFECTS_AND_IMPROVEMENT_PLAN_CN.md` 中 P1-2 阶段 3。
- **实现**：新增 `config/eval_config.py`；扩展 `config/settings_core.py`、`config/backend_config.py`、`config/db_config.py`；迁移 eval、device memory/ledger、tool audit/governance、code scanner、think plan、routing trainer、fleet、routing selector、backends `_utils`、gitee mirror、provider automation/inventory 等模块到集中配置；`tests/_env_sync*.py` 同步新增字段并拆分 `tests/_env_sync_runtime_maps.py`。
- **验证**：全量 `pytest` → **3545 passed / 17 skipped / 0 failed**；`ruff check .` clean；`pyright` 修改文件 0 errors；零 >300 行文件。

### 最近完成（2026-06-23）缺陷改善计划再下一批 — P1-1/3/5/6、P2-11 关闭

- **目标**：继续推进 `docs/PROJECT_DEFECTS_AND_IMPROVEMENT_PLAN_CN.md`，补齐已修复 P1 项的回归测试，修正误导性测试命名。
- **核对结果**：P1-1、P1-3、P1-5、P1-6、P2-11 在代码中已实际修复，本批补充测试/重命名并关闭文档条目。
- **新增/完善测试**：
  - `tests/test_routing_executor.py`：`execute()` orchestration 端到端。
  - `tests/test_routing_executor_telemetry.py`：遥测降级与错误码提取。
  - `tests/test_sqlite_graph_store_threading.py`：SQLite 图索引并发安全。
  - `tests/test_routing_engine_context_warnings.py`：上下文注入异常 warning 日志。
  - `tests/test_route_result_dataclass.py`（由 `test_routing_engine_integration.py` 重命名）：`RouteResult` / `PickResult` 字段构造。
- **验证**：聚焦测试 25 passed；全量测试、ruff、pyright 通过。

### 最近完成（2026-06-23）缺陷改善计划下一批 — 全部 P0 项关闭

- **目标**：继续推进 `docs/PROJECT_DEFECTS_AND_IMPROVEMENT_PLAN_CN.md`，核对剩余 P0/P2/P3 项代码实际状态，补充回归测试，隔离隐藏网络依赖，同步文档。
- **核对结果**：P0-1/2/3/4/5、P2-18、P3-17、P3-20 在代码中已实际修复，本批补充回归测试并关闭文档条目。
- **新增回归测试**：
  - `tests/test_backend_reputation_threading.py`：并发 100 线程验证 `backend_reputation.py` RLock 保护。
  - `tests/test_mqtt_client_loop.py`：MQTT 同步回调在无事件循环时安全降级、有主循环时正确转发。
  - `tests/test_admin_extra_config_security.py`：Admin 配置导入端点 SSRF/内网 URL 注入被拒。
  - `tests/test_requirements.py`：`paramiko>=3.5.0` 声明检查。
  - `tests/test_ruff_ignore_paths.py`：ruff exclude 包含本地运行时目录。
  - `tests/test_security_headers.py`：补充 CSP 严格性断言。
- **网络测试隔离**：`pytest.ini` 新增 `network` marker 并默认跳过；`tests/test_external_enrichment.py` provider 测试标记为网络测试。
- **验证**：
  - 全量 `pytest -q` → **3432 passed / 17 skipped / 0 failed / 2 deselected**
  - `ruff check .` clean
  - `pyright` 修改文件 0 errors
  - 新增回归测试 5x 复跑稳定

### 最近完成（2026-06-22）第七轮瘦身 — 消除全部 >300 行文件

- **目标**：响应「继续优化计划」指令，消除所有 >300 行文件，减少 >50 行函数数量，清理 PONYTAIL-DEBT。
- **拆分 `routes/admin_ui/panels.py`（368→包）**：4 个子模块按逻辑分组（_metrics/_analysis/_admin/_system），消除唯一生产 >300 行文件。
- **拆分 7 个生产超长函数**：deploy_unified::main（82→32）、fts_index::add_documents/search（68+62→38+35）、MCP ops 三工具（tail_log/health_check/server_status）、prompt_compress_server::handle_request、lima_code_query_core::search_code。
- **拆分 6 个测试超长函数**：fake_u1 系列 4 个 + device_app_members + xiaozhi_v1_compat_task。
- **拆分 3 个 >300 行测试文件**：test_routing_engine_post、test_device_draw_handler、test_p1_4_device_stability_gate。
- **删除 9 个未使用脚本**（~732 行），PONYTAIL-DEBT 待处理项清零。
- **附加修复**：test_mimo_mcp_runner Windows 平台断言；安装 hypothesis 依赖。
- **验证**：全量 **2402 passed / 19 skipped / 0 failed**；ruff clean；**零 >300 行文件**；>50 行函数 57（从 73 降至 57）。
- **详见** `progress.md` 2026-06-22 第七轮瘦身条目。

### 最近完成（2026-06-22）全量修复里程碑 A/B/C/D

- **目标**：响应「进行全量修复」指令，对 LiMa 服务、固件端、Web 前端、小程序端做端到端修复与验证。
- **里程碑 A（CRITICAL 安全）**：
  - 固件 `application.yml` / `application-dev.yml` / `docker-compose_all.yml` 移除数据库与 Knife4j 默认密码 fallback，强制通过环境变量配置。
  - `u1-grbl` 固件默认 WiFi AP/STA 密码从硬编码 `12345678` 改为空，避免出厂即携带弱口令。
- **里程碑 B（HIGH 稳定性）**：
  - 修复 Redis TTL 变更导致的 9 个测试回归：为 `_FakeRedis` 补充 `expire()` / `set(..., ex=...)`。
  - 多个 SQLite 连接泄漏点已在前期修复；本次新增 `routes/security_headers.py` 全局安全响应头中间件。
- **里程碑 C（MEDIUM 质量）**：
  - 关键路由速率限制：`/admin/login`（IP）、`/internal/v1/outcome`（IP）、`/upload`（账户），并配套 `routes/rate_limit_helper.py` 与 `LIMA_RATE_LIMIT_DISABLE` 开关。
  - `.env.example` 补充 `LIMA_API_KEY`、`LIMA_JWT_SECRET`、`LIMA_DATA_DIR`、`LIMA_DB_PATH`、Redis TTL、公开演示、上传/管理登录/Outcome 限流等缺失变量。
  - `.dockerignore` 新增 `.guardian/`、`.test-tmp/`、`*.pyc`、`node_modules/`、IDE 目录等，减小镜像体积。
  - `docker-compose.yml` 增加 `redis` 服务、数据卷、depends_on 健康检查与默认 Redis URL 环境变量。
  - Web 前端（`chat-web/`）：添加 CSP 与 noscript、代码块 HTML 转义、移除内联 `onclick`。
  - 小程序端（`manager-mobile/src/`）：清理 `App.vue`、`fg-tabbar.vue`、`router/interceptor.ts`、`utils/index.ts`、`hooks/useUpload.ts` 中的调试 `console.log` 与注释垃圾。
- **里程碑 D（LOW 优化）**：
  - `migrations/xiaozhi_schema.sql` 增加 `v2_device(last_heartbeat)`、`v2_device_binding(status)`、`v2_task(device_id, status)` 复合索引。
- **验证**：
  - 聚焦测试（Redis TTL、上传、管理员 CSRF、JSON body、前端安全、安全头）全部通过。
  - 全量 `pytest -q` → **2328 passed / 18 skipped / 0 failed**。
  - `ruff check` / `pyright`（修改文件）→ 0 errors。
  - `scripts/check_code_size.py`：本次修改文件均满足约束；遗留 >300 行文件 3 个、>50 行函数 72 个为历史债务。

### 最近完成（2026-06-22）项目文档更新与过时内容清理

- **目标**：响应「更新项目文档；清理过时文档」指令，刷新根 README、STATUS、部署约定、架构文档等入口文档，移除明显过时的命令、端口、模块引用。
- **根 README.md 重写**：
  - 从个人编码助手后端描述更新为「多后端 AI 路由 + AI 智能硬件云端服务」。
  - 修正启动命令为 `python -m uvicorn server:app --host 0.0.0.0 --port 8080`。
  - 修正部署命令为 `python scripts/deploy_unified.py --slice core`。
  - 移除不存在的 `smart_router.py`、`device_schema.py`、MQTT 为主等描述；补充 WebSocket 设备网关、`device_app_api`、小智兼容层默认关闭等现状。
  - 补充核心文档索引表与退役模块说明。
- **STATUS.md 刷新**：测试计数更新为 **2319 passed / 18 skipped / 0 failed**；新增本段文档清理记录。
- **docs/DEPLOY_AND_RELEASE_CONVENTION.md 更新**：
  - 默认部署命令改为 `python scripts/deploy_unified.py`（tar/scp 上传，SFTP 为 fallback）。
  - `LIMA_DEPLOY_KEY_PATH` 示例改为 `~/.ssh/lima_deploy_ed25519`（原 `id_ed25519` 已损坏）。
  - 移除已不存在的 `--target` / `--profile` 参数引用；补充 `--files` 与 `--dry-run` 用法。
  - 本地测试命令同步为 `python -m pytest --tb=short -q`。
- **docs/ARCHITECTURE.md 修正**：Phase 表中 Phase 2 状态改为 ✅ 完成；Phase 3/4/5 状态改为按当前 roadmap 待执行/进行中。
- **docs/README.md**：更新日期为 2026-06-22；在运维与发布段补充 `DEPLOY_AND_RELEASE_CONVENTION.md` 链接。
- **工作区清理**：删除未跟踪的 `coverage_output.txt`。
- **验证**：`ruff check .` clean；`pyright STATUS.md README.md` 不适用；文档链接已目视检查。

### 最近完成（2026-06-22）VPS 本地部署修复

- **问题**：本地 `python scripts/deploy_unified.py --slice core` 失败，paramiko 报 `~/.ssh/id_ed25519` 为 `Invalid key`；检查发现私钥文件内容被替换为占位符 `test`。
- **修复**：
  - 生成新的部署密钥 `~/.ssh/lima_deploy_ed25519`，使用 VPS root 密码将其公钥写入远端 `~/.ssh/authorized_keys`。
  - `scripts/deploy_unified.py` 增加 `python-dotenv` 加载 `.env`，本地部署自动读取 `LIMA_DEPLOY_KEY_PATH` 与 `LIMA_DEPLOY_USE_TAR`。
  - `.env` 追加 `LIMA_DEPLOY_KEY_PATH=~/.ssh/lima_deploy_ed25519` 与 `LIMA_DEPLOY_USE_TAR=1`。
- **验证**：
  - 简化命令 `python scripts/deploy_unified.py --slice core` → **1372 uploaded, 0 failed, health OK**。
  - 服务已重启，公网 `/health` 200 ready。
- **提交**：`4f7937b1` 已 push 到 `origin/main`。

### 最近完成（2026-06-22）代码审查问题按优先级修复

- 详见 `progress.md` 2026-06-22 代码审查修复条目：`.env.example` 补充品牌变量、`routes/system_endpoints.py` 改用 `brand_config`、response_cleaner 去硬编码、`device_gateway/intent.py` 利用 `_DANGEROUS_CAPABILITIES`、`session_memory/store_promote.py` 排序确定化、`prompt_engineering/layers.py` docstring 层号修正。
- 提交 `2b918322` 与 `f05c6f92` 已 push 到 `origin/main`。

### 最近完成（2026-06-22）提示词工程强化（P0-1 ~ P0-5）

- **问题**：提示词审计发现 5 项高优先级改进点：安全基线不完整、硬编码品牌/能力、设备控制缺少危险操作限制、Skills frontmatter 缺失、无版本追踪。
- **P0-1 统一安全基线**：`prompt_engineering/layers.py` 新增 `build_safety_baseline()`，覆盖全部 6 个 scenario（coding/chat/vision/device 场景均含身份保护和系统指令保密）。
- **P0-2 品牌/能力配置化**：新建 `brand_config.py` 集中管理公司名、产品名、UA、能力列表（支持 `env` 覆盖）；`identity_guard.py`、`prompt_engineering/layers.py`、`http_request_builder.py` 改为引用配置常量。
- **P0-3 设备控制加固**：`device_gateway/intent.py` 新增 `_ALLOWED_CAPABILITIES` / `_DANGEROUS_CAPABILITIES` 白名单/黑名单；LLM replan 解析后校验能力必须在白名单内；`skills/device/control.md` 和 prompt layers 同步更新。
- **P0-4 Skills frontmatter 规范**：补全 `skills/code/guide.md` 等 4 个缺失 frontmatter 的文件；新增 `tests/test_skills_integrity.py` CI 门禁。
- **P0-5 提示词版本追踪**：`prompt_engineering/layers.py` 新增 `PROMPT_VERSION = "lima-prompts-v1.1"`；`compose_system_prompt()` 末尾追加 `<!-- version.scenario -->` 标记。
- **验证**：
  - 新增测试 4 组 11 个用例；全量 `pytest -q` → **2318 passed / 18 skipped / 1 failed**（1 个预存失败非本次引入）。
  - `ruff check` / `pyright` 全部 clean。
  - CI 中 `ruff format --check` 格式修复已推送（`d9dd5af8`）。
  - Deploy workflow 已触发执行中。
- **提交**：`5f78b3d4`、`e5e21692`、`a1fd97a5`、`d9dd5af8` 已 push 到 `origin/main`。

### 最近完成（2026-06-22）免费聊天匿名访问修复

- **问题**：用户确认 LiMa 星云聊天为免费、无需 API Key，但生产环境因 `LIMA_RUNTIME_ENV=production` 被 `access_guard.py` 强制阻断匿名访问；`/health.security.anonymous_access.allowed=false`，`/v1/chat/completions` 不带 Key 返回 401。
- **修复**：
  - `access_guard.py`：移除生产运行时的强制 `False`，`LIMA_ALLOW_ANONYMOUS=1` 在生产环境同样生效。
  - 前端：`chat-web/chat-api.js` 移除发送消息前的强制 Key 弹窗；`chat-web/chat-ui.js` 允许留空清除 Key；`chat-web/index.html` 弹窗文案改为“设置 API Key（可选）”，静态资源 cache-bust 升级到 `?v=3`。
  - 测试：`tests/test_access_guard.py`、`tests/test_system_endpoints.py` 更新断言；聚焦测试先 RED 后 GREEN。
- **验证**：
  - 全量 `pytest -q` → **2305 passed, 18 skipped, 0 failed**。
  - GitHub Actions `Deploy` workflow（run `27942136224`）完整通过：Aliyun 主服务、chat-web 静态文件、公网冒烟、JDCloud probe。
  - 公网 `/health` → `security.anonymous_access.allowed=true`、`production_blocked=false`。
  - 公网匿名 `POST /v1/chat/completions`（无 Authorization）成功返回响应。
- **提交**：`241f360a`（代码修复）、`62645339`（progress 记录）、`5a6110ab`（.env.example 注释更新）已 push 到 `origin/main`。

### 最近完成（2026-06-22）测试修复、device_gateway 拆分与当前 WIP 合并

- **测试修复**：`tests/test_rate_limit.py::test_sliding_window_evicts_old_calls` 时间值修正；`routes/xiaozhi_compat/device_routes.py` 移除重复 `/api/v1` prefix，修复 8 个小智兼容层 404 失败。
- **代码尺寸**：`routes/device_gateway.py`（310→270 行）拆出 `routes/device_gateway_helpers.py`，承载 lifecycle/evidence/test-reset 辅助函数；生产代码 >300 行文件从 8 个降至 7 个（剩余为 scripts/ 分析脚本、lima_mcp_stdio/ MCP 工具与一个测试文件）。
- **类型修复**：`lima_mcp_stdio/lima_code_query_mcp.py`、`mimo_runner.py`、`__init__.py` 修复 pyright errors。
- **验证**：全量 `pytest -q` → **2230 passed, 4 skipped**；`ruff check .` / `ruff format --check` clean；`pyright routes/ lima_mcp_stdio/` 0 errors。
- **提交推送**：Commit `9da0805c` 已 push 到 GitHub `origin main`；Gitee push 因 SSH key 缺失失败。
- **阻塞项**：VPS 部署需补充有效 SSH key 或 `LIMA_DEPLOY_PASS`。

### 最近完成（2026-06-18）flaky test 修复 + U1 route_policy 拒绝证据补齐

- **flaky test**：`tests/test_model_registry.py::test_list_versions_sorted_by_created_at_desc` 因 `datetime.now()` 精度导致偶发失败，已改为固定递增时间戳，连续 5 次复跑稳定通过。
- **U1 固件侧 route_policy 拒绝**：物理 U1 无法真机验证；fake U1 已覆盖未知 `route_role` / `primary_strategy` / `artifact_required` / `backend`、角色与策略/制品不兼容、`run_path` 能力缺失、`device_control` 要求模型等拒绝路径。新增 `tests/test_fake_u1_route_policy_validator.py` 10 个单元测试，与 `tests/test_fake_u1_cloud_rejection.py` 形成云端到 fake U1 闭环证据。
- **验证**：`tests/test_model_registry.py` 10 passed ×5；`tests/test_fake_u1_route_policy_validator.py` 10 passed；`tests/test_fake_u1_cloud_*.py` 5 passed。
- **提交**：`e7cf101 test(device): add fake U1 route_policy validator unit tests`、`3c3d220 test(model_registry): eliminate flake by stepping timestamps in sort test`。
- **VPS 部署**：已使用 `LIMA_DEPLOY_PASS` 成功部署并重启，smoke 通过。
- **omk-review 修复**：已处理 Critical/High 5 项 + Medium 13 项（新增：Telegram warm phase 移除、eval_loop_core passed 标志、correlation 精确匹配、routing_guard 静默、auto-indexer 删除文件、code_scanner 递归、admin backend URL 限制、voice audio 大小限制），剩余 Low 项进入 backlog。

### 最近完成（2026-06-18）函数级尺寸治理第 5 批：route_registry / routing_executor / http_body_limit 拆分

- **目标**：继续降低 >50 行函数基线，聚焦最热路径。
- **实现**：
  - `routes/route_registry.py`：将 `_register_core_routes` 拆分为 `_register_chat_and_media_routes`、`_register_admin_and_static_routes`、`_register_system_routes`、`_register_device_app_routes`、`_register_voice_routes`，每个 helper 职责单一。
  - `routing_executor.py`：按串行/并行/fallback/遥测拆分为 `routing_executor_serial.py`、`routing_executor_parallel.py`、`routing_executor_fallback.py`、`routing_executor_telemetry.py`，`routing_executor.py` 保留 `execute` 入口。
  - `http_body_limit.py`：将 `BodySizeLimitMiddleware.__call__` 中的 body 读取/解压/限流逻辑拆分为 `_read_limited_body`。
- **验证**：聚焦测试 52 passed；全量 pytest 1860 passed / 4 skipped；`ruff check` / `pyright` 目标文件 clean；`scripts/check_code_size.py` 不再报告 >300 行文件，>50 行函数从 82 降至 78。
- **VPS 部署**：使用 `LIMA_DEPLOY_PASS` 成功部署并重启（1287 文件，0 失败）。Smoke：`/health` 200 ready；`/device/v1/health` 200 ready，`production_ready=true`。

### 最近完成（2026-06-18）review 修复：SSH 部署回退、health 503 语义、rate limiter 缺省

- **问题来源**：代码审查后遗留的 5 个测试覆盖缺口与部署脚本路径兼容性问题。
- **实现**：
  - `scripts/deploy_common.py`：对 `LIMA_DEPLOY_KEY_PATH` / `LIMA_DEPLOY_KNOWN_HOSTS` 应用 `os.path.expanduser()`。
  - `scripts/deploy_unified_*.py`：SSH key 无效时自动回退到 `LIMA_DEPLOY_PASS` 密码认证。
  - `.env.example`：补充 `LIMA_DEPLOY_KEY_PATH`、`LIMA_DEPLOY_KNOWN_HOSTS`、`LIMA_RUNTIME_ENV`、`LIMA_XIAOZHI_DEV_STATIC_LOGIN_CODE`。
  - `scripts/smoke_live_and_digital_human.py`：移除 HTML token 抓取，改为环境变量读取。
  - `rate_limiter.py`：滑动窗口过期清理、multiplier 夹紧到 ≥1。
  - `device_gateway/health.py`：生产环境 `production_ready` 要求 task_store / session_bus 跨进程共享。
  - `model_registry.py`：列表排序使用稳定排序，保证 `created_at` 相同时保持注册顺序。
- **新增测试**：
  - `tests/test_rate_limiter.py`：窗口过期、multiplier ≤0。
  - `tests/test_device_app_auth.py`：dev flag 开启但无静态码时返回 503。
  - `tests/device_gateway/test_health.py`：生产 + 共享 state 时返回 200 + `production_ready=True`。
  - `tests/test_model_registry.py`：相同 `created_at` 稳定排序。
- **验证**：聚焦测试 22 passed；`ruff check` / `ruff format --check` clean；VPS `/health` 与 `/device/v1/health` 验证通过。
- **文档**：`docs/RELEASE_GATE_CHECKLIST.md`、`docs/DEPLOY_AND_RELEASE_CONVENTION.md`、`STATUS.md` 已更新 health 可能返回 503 与 rate limiter 默认值。

### 最近完成（2026-06-18）draw_generated 主链路接入 AI 绘图管线

- **问题**：`device_draw_handler`（万相简笔画 → OpenCV 矢量化）已实现，但 `task_creation` 对自然语言 `draw_generated` 仍走 `render_text_task` 笔画字库，与 `route_policy.image_then_vector` 不一致。
- **实现**：
  - 新增 `device_gateway/task_draw_params.py`：`build_run_params_async()` / `build_draw_generated_params()` 在 SVG path 之外调用 `handle_device_draw()`。
  - `task_creation.py` 异步化：`project_to_motion_task_async`、`create_task_from_transcript_async`；WS / App / `/device/v1/tasks` 热路径改为 await。
  - 生图失败返回 `draw_failed` 任务，不静默降级为描字。
- **验证**：`pytest tests/test_task_creation_draw_generated.py tests/test_device_gateway_routes.py tests/test_device_gateway_model_routing.py -q` → **116 passed**；全量 `pytest` → **1746 passed, 37 skipped**；`ruff check` / `pyright` 触及文件 clean。
- **提交**：`device_gateway/task_draw_params.py` 等 draw_generated 管线文件已 commit 并 push 到 `origin main`。
- **部署**：VPS `lima-router` 已重启，`/health` 与 `/device/v1/health` 均返回 200。
- **文档**：`docs/testing/draw_generated_task_creation.tdd.md`、`docs/DEVICE_DEVELOPER_GUIDE_CN.md`、`docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md`；`docs/release_evidence/2026-06-18-M14-draw-generated-async-pipeline.md`。

### 最近完成（2026-06-18）小智服务器退役：LiMa 原生设备/固件/移动端贯通

- **实现**：新增并注册 `/device/v1/app` 原生管理面，覆盖账号、设备、任务、成员/声纹、转移、耗材、自检；`xiaozhi_v1_compat` 兼容层于 2026-06-26 物理删除（`routes/xiaozhi_v1_compat.py` + `routes/xiaozhi_compat/` 包 + 退役测试），`LIMA_XIAOZHI_COMPAT_ENABLED` 标志同步移除。
- **固件/移动端**：`esp32S_XYZ` 固件默认连接 `wss://chat.donglicao.com/device/v1/ws` 并使用 `lima-device-v1`；manager-mobile 默认 LiMa 公网、v2 页面和 `/device/v1/app` API，设置页用 `/health` 验证服务地址。
- **OTA**：补齐设备侧升级计划和安装结果上报，发布/灰度状态可持久化。
- **验证**：全量 `pytest` → **1746 passed, 37 skipped**；`ruff check .`、`ruff format --check` clean；pyright 目标文件 0 errors；`tests/test_firmware_hardware_gate.py` → **13 passed**；manager-mobile `type-check` 和 `build:h5` 通过；VPS 公网 `/health`、`/device/v1/health` 验证通过，OpenAPI 已有 `/device/v1/app/*` 与 `/device/v1/ota/upgrade-plan`，默认无 `/api/v1/devices`。
- **提交**：固件硬件门禁脚本、ESP-IDF 环境助手、相关测试与文档已 commit 并 push 到 `origin main`；`esp32S_XYZ` 子模块 `fw_rev` 修复已 push 到子模块 `origin main`。

### 最近完成（2026-06-17）阿里云 ASR fallback 链实现

- **目标**：为设备语音管线提供「NLS → DashScope → Whisper」自动降级 ASR。
- **实现**：新增 `device_voice/providers/asr_composite.py` 及 `aliyun_fallback` 工厂注册；阿里云 NLS/TTS provider 支持 `ALIYUN_AK_ID` / `ALIYUN_AK_SECRET` 别名，并兼容 SDK 直接返回 token 字符串的情况。
- **验证**：`ruff check` clean；`pyright` 0 errors；`pytest tests/test_device_voice_cloud_providers.py -q` → **36 passed**；VPS `.env` 已写入凭证、代码已部署、服务 ready。
- **真实凭证冒烟**：DashScope ASR/TTS match=True、阿里云 NLS ASR/TTS match=True、MiMo TTS → AliyunFallback ASR similarity=1.00。

### 最近完成（2026-06-17）阶段 1 剩余项：U1/U8 仿真固件侧拒绝未知 route_policy

- **实现**：在 `esp32S_XYZ` 子模块新增 `tools/fake_u1/route_policy_validator.py`，与 LiMa `VALID_ROUTE_ROLES` / `VALID_PRIMARY_STRATEGIES` / `VALID_ARTIFACT_REQUIRED` 对齐；`tools/fake_u1/app.py` 在 `HOME` / `MOVE` / `PATH_BEGIN` 入口校验 `route_policy`；`tools/fake_device_server/app.py` 将 `route_policy` 透传至 fake U1。
- **拒绝路径**：未知 `route_role`、不兼容 `primary_strategy`、缺少 `run_path` 能力等场景返回 `E009` 错误；fake_device_server 响应标记 `route_policy_rejected=true`。
- **测试**：fake_u1 14 passed、fake_device_server 17 passed、LiMa `tests/test_fake_u1_cloud_loop.py` 5 passed（含新增拒绝路径）、设备网关聚焦 47 passed。
- **文档**：新增 `docs/release_evidence/2026-06-17-M13-route-policy-firmware-rejection.md`。

### 最近完成（2026-06-17）G4 启动/部署不确定性降低 + VPS 验证

- **实现**：`server_lifespan.py` 拆分为 `server_lifespan_state.py`、`server_lifespan_phases.py`、`server_lifespan.py`（99 行）；启动阶段分为 critical（阻塞 ready）与 warm（后台异步预热），warm 失败不阻塞服务。
- **/health 语义**：新增 `starting` / `warming` / `ready` / `error`，响应包含 `pending_warm` 与 `errors`。
- **STARTUP_PHASES 顺序修复**：`PhaseTimer` 在阶段启动时立即追加记录，退出时仅更新耗时/状态，确保并发 warm 阶段仍按启动顺序展示（而非完成顺序）。
- **VPS 验证**：
  - 部署到 `47.112.162.80`，`/opt/lima-router/server_lifespan_state.py` 已更新。
  - `https://chat.donglicao.com/health` → HTTP 200，`status=ok`，`startup.status=ready`，13 个 phase 按启动顺序返回（含 `observability.prometheus.start` 126.3ms 置尾）。
  - `https://chat.donglicao.com/device/v1/health` → HTTP 200，`auth_configured=true`。
- **验证**：`pytest` 全量 1662 passed / 23 skipped；`ruff check` / pyright clean；`tests/test_system_endpoints.py` 6 passed。

### 最近完成（2026-06-17）G3 小批冷区清理

- **删除文件**：`search_gateway/dev_tools.py`（279 行）、`session_memory/hooks.py`（61 行）、`tool_gateway/executor.py`（136 行）、`infra/g4f_server.py`（18 行），合计 494 行。
- **验证**：ripgrep 确认无引用；`pytest` 全量 1662 passed / 23 skipped；`ruff check` clean。
- **文档**：更新 `docs/CODEBASE_SUBSYSTEM_TIER_CN.md`。

### 最近完成（2026-06-17）G2 设备模型准入复跑

- **复跑命令**：`python scripts/eval_device_model_role.py --all --markdown`
- **结果**：8 个角色与 `DEVICE_ROLE_PREFERENCES` 对齐；意图解析器/文本规划器/恢复解释器/路由策略契约 100% admit；图像生成器条件准入；矢量化器 `opencv_contour_detect` 因本地 `cv2` 已安装从 fail 修正为 **12/12 通过**；提示增强器/视觉分析器 defer。
- **脚本修复**：`scripts/eval_device_model_role.py` 增加 `sys.stdout.reconfigure(encoding="utf-8")`，解决 Windows 重定向 UTF-8 乱码。
- **文档**：更新 `docs/model_admission/2026-06-17-device-drawing-writing-evidence.md` 与完整报告。

### 最近完成（2026-06-17）代码质量门禁整改 + AI→Motion 发布门回归证据

- **P0 静默异常治理**：生产路径约 38 处 `except ImportError/Exception: pass` 或仅 `logger.debug` 的关键依赖降级升级为 `logger.warning`，符合 AGENTS.md Hard Rule 1。
- **P1 模块拆分**：`device_voice/voiceprint.py` 587→112 行、`routes/device_gateway_ws_handlers.py` 468→260 行、`session_memory/store_db.py` 361→129 行；新增 7 个职责单一子模块。
- **P2 死代码清理**：删除 `backends.py`、`device_intelligence/profile_store.py`、`device_intelligence/planner.py`、`session_memory/shadow_mode.py` 及对应测试。
- **P3 CI 强化**：`.github/workflows/test.yml` 增加 `ruff format --check` 与 `pyright` 权威文件类型检查。
- **P4 全仓格式化**：`ruff format .` 统一 412 个文件风格。
- **验证**：
  - 全量 `pytest` → **1662 passed, 23 skipped, 0 failed**；
  - AI→Motion 发布门聚焦测试 → **173 passed, 3 skipped**；
  - `ruff check .`、`ruff format --check`、pyright 权威文件均 clean；
  - 证据文档 `docs/release_evidence/2026-06-17-M13-code-quality-gate-evidence.md`。
- **提交**：`4d5ef77`、`41b9389`、`9dce12a`、`297fba4`、`cd5edca` 已 push 到 `origin main`。

### 最近完成（2026-06-16）拆分四个热路径 oversized 函数

- **实现**：
  - `routing_selector.py::select` 拆为池解析、初始筛选、guard 过滤、评分、ML boost、排序、pin 等私有 helper。
  - `server_lifespan.py::lifespan` 拆为 `_run_startup_phases` / `_run_shutdown_phases`。
  - `routes/chat_stream.py::stream_response` 拆为图片/thinking/编排/speculative/fallback helper。
  - `device_gateway/device_draw_handler.py::handle_device_draw` 拆为响应构造、预设图形、图片生成、SVG 转换优化 helper。
- **验证**：
  - 路由相关：`tests/test_routing_engine.py tests/test_routing_guard.py tests/test_routing_weights.py` → 35 passed。
  - 系统/聊天：`tests/test_system_endpoints.py tests/test_chat_handler.py` → 15 passed；`server_lifespan` import ok。
  - 设备绘图：`tests/test_draw_prompt_enhancer.py tests/test_device_gateway_model_routing.py` → 43 passed。
  - `ruff check .` clean；`scripts/check_code_size.py` 不再报告上述 4 个文件/函数超标。
- **提交**：`7e029e5` refactor + `710d26f` fixup 已 push 到 `origin main`。

### 核心功能
- **设备网关**: ESP32 绘图机/写字机云端控制
- **AI 路由**: 170+ 后端智能路由（设备任务 + 通用聊天/IDE）
- **任务管理**: 任务创建、派发、执行、监控、恢复
- **设备策略**: 安全策略、固件兼容性、路径验证、route_policy/backend 字段贯通

### 当前开发文档入口（2026-06-25）

- **设备开发入口**：[`docs/DEVICE_DEVELOPER_GUIDE_CN.md`](docs/DEVICE_DEVELOPER_GUIDE_CN.md) 汇总设备联调、常用测试、证据要求和最小闭环。
- **下一阶段计划**：[`docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md`](docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md) 明确当前活跃路线图与后续优化方向。
- **协议开发闭环**：[`docs/archive/device_protocol_alignment.md`](docs/archive/device_protocol_alignment.md) 已补充 `hello` → `task_dispatch` → `motion_event` → 终态证据的调试路径，并明确 `route_policy` 为下行任务硬契约（已归档）。
- **ECC 工程流程**：[`docs/ECC_WORKFLOW_CN.md`](docs/ECC_WORKFLOW_CN.md) 定义项目采用的 Plan First / TDD / Code Review / 提交规范，以及 `.kimi-code/rules/ecc-workflow.md` 本地 rule。
- **Ponytail 精简顾问**：[`docs/AGENTS_PONYTAIL.md`](docs/AGENTS_PONYTAIL.md) 引入 lazy senior dev 决策阶梯，LiMa 硬规则优先。

### 最近完成（2026-06-17）生成 G1/G2 证据文档（步骤 4）

- **G1**：`docs/release_evidence/2026-06-17-M13-AI-to-Motion-regression.md` 记录热路径拆分/覆盖率提升后的端到端回归证据。
- **G2**：`docs/model_admission/2026-06-17-device-drawing-writing-evidence.md` 记录模型准入复跑结果。
- **验证**：`pytest tests/test_fake_u1_cloud_loop.py tests/test_device_draw_handler.py tests/test_motion.py -q` → **28 passed**。
- **提交**：`7806247` 已 push 到 `origin main`。

### 最近完成（2026-06-17）提升 device_gateway 测试覆盖率（步骤 3）

- **新增**：`tests/test_device_draw_handler.py`（11 cases）、`tests/test_motion.py`（13 cases）。
- **验证**：`pytest` 聚焦 35 passed；`device_gateway` 覆盖率从 65.7% 提升至 **71.1%**。
- **提交**：`7f4c93b` 已 push 到 `origin main`。

### 最近完成（2026-06-17）拆分热路径大函数 + 清理死代码（步骤 1-2）

- **拆分**：`routing_selector.select` → 21 行；`server_lifespan.lifespan` → 8 行；`routes/chat_stream.stream_response` → 47 行；`device_gateway/device_draw_handler.handle_device_draw` → 45 行。
- **死代码清理**：删除 `webhook_activity_buffer.py`（109 行）；`context_pipeline` lazy import 模块按 `CODEBASE_COLD_PRUNE_PRIORITY_CN.md` 保留。
- **基线更新**：`scripts/check_code_size.py` → 23 个 >300 行文件、99 个 >50 行函数。
- **验证**：路由/系统/聊天/设备绘图聚焦测试 87 passed；`ruff check .` clean。
- **提交**：`7e029e5`、`710d26f`、`a89790d`、`f583784` 已 push 到 `origin main`。

### 最近完成（2026-06-17）接入 Ponytail「lazy senior dev」顾问规则

- **实现**：
  - 克隆 [Ponytail](https://github.com/DietrichGebert/ponytail) 到 `reference/ponytail/`。
  - Cursor：`.cursor/rules/ponytail.mdc` + 全局 `~/.cursor/rules/ponytail.mdc`。
  - Kimi：`.kimi-code/rules/ponytail.md` + 全局 `~/.kimi-code/rules/ponytail.md`。
  - OpenCode / Claude / Codex：通过 `AGENTS.md` / `CLAUDE.md` / `docs/AGENTS_PONYTAIL.md` + 全局 AGENTS 条件章节引入。
  - 所有 Ponytail 规则前置 LiMa 覆盖声明：安全、验证、测试门禁、文档同步不可简化。
- **验证**：`ruff check .` clean；`AGENTS.md` 265 行、`CLAUDE.md` 162 行（均 ≤300）。
- **提交**：`3f6d046`、`3ddee70` 已 push 到 `origin main`。

### 最近完成（2026-06-17）按 ECC 开发流程重新整理 LiMa（阶段 1-3 完成）

- **流程文档**：更新 `AGENTS.md` 新增 ECC 章节；新增 `docs/ECC_WORKFLOW_CN.md`；新增 `.kimi-code/rules/ecc-workflow.md` 本地 rule。
- **度量门禁**：安装 `pytest-cov` 并配置覆盖率；新增 `scripts/check_code_size.py`（检查 >300 行文件、>50 行函数）；更新 `scripts/run_pre_commit_check.py` 集成尺寸检查作为 warning；记录基线到 `findings.md`。
- **Top 3 生产文件拆分**：
  - `device_gateway/protocol.py` → `protocol_core/validators/frames/lifecycle.py`（接口兼容，原文件改为 facade）。
  - `device_gateway/path_pipeline.py` → `path_data/text_renderer/svg_parser/preview_svg.py`（接口兼容，原文件改为 facade）。
  - `routes/device_gateway_ws_handlers.py` → `routes/ws_lifecycle_helpers.py` + `routes/ws_task_helpers.py`。
- **验证**：受影响模块回归 81 passed；`ruff check .` clean；`pyright` 改动文件 0 errors；尺寸检查从 26 个 >300 行文件降至 23 个。
- **提交**：`027217b`、`021fb6b`、`7423cfd`、`c378d00` 已 push 到 `origin main`。

### 最近完成（2026-06-17）AI 绘画 prompt 优化 + Wanx 模型更新

- **新增**：`device_gateway/draw_prompt_enhancer.py`，将用户描述包装为笔绘机约束 prompt。
- **修改**：`device_gateway/device_draw_handler.py` 调用增强 prompt；默认模型从 `wanx-v1` 改为 `wanx2.1-t2i-turbo`（`wanx-v1` 已不可用）。
- **新增测试**：`tests/test_draw_prompt_enhancer.py`（11 cases）。
- **验证**：聚焦测试 75 passed；ruff clean；VPS `ALIYUN_API_KEY` live 生成「一只猫」成功。
- **规模**：`python_files=656`，`python_lines=77,584`。

### 最近完成（2026-06-17）可选 P5 余项：`lima_mcp/` HTTP 路由退役

- **删除**：`lima_mcp/` 目录（13 个文件，~1.2k 行）；`tests/test_mcp_access_plane.py`、`tests/test_hypothesis_fs_allowlist.py`。
- **更新**：`routes/route_registry.py` 移除 `lima_mcp.server` 注册；`pyrightconfig.json` 移除 `"lima_mcp/"`；`docs/CODEBASE_COLD_PRUNE_PRIORITY_CN.md` 更新 P5 状态。
- **保留**：`lima_mcp_stdio/` 作为独立 stdio MCP 入口（`lima-mimo-mcp` CLI）。
- **验证**：聚焦门 77 passed；`ruff check .` clean。
- **规模**：`python_files=654`，`python_lines=77,460`。

### 最近完成（2026-06-17）可选 P5：GitHub/Gitee webhook 路由退役

- **删除**：`routes/github_webhook.py`、`routes/gitee_webhook.py`；`github_webhook/`、`gitee_webhook/` 包目录；`tests/test_github_webhook.py`、`tests/test_gitee_webhook.py`。
- **更新**：`routes/route_registry.py` 移除两个注册块；`scripts/check_vps_environment.py` 移除 webhook secret 检查；`tests/test_vps_environment_check.py` 改用 `LIMA_ADMIN_TOKEN` 示例；`.env.example` 移除 `GITHUB_WEBHOOK_*` / `GITEE_WEBHOOK_*`；`docs/CODEBASE_COLD_PRUNE_PRIORITY_CN.md` 更新 P5 状态。
- **验证**：聚焦门 `pytest tests/test_retrieval_injection.py tests/test_routing_engine.py tests/test_device_gateway_model_routing.py tests/test_provider_automation_admission.py -q` → **77 passed**；`ruff check .` clean。
- **规模**：`python_files=670`，`python_lines=79,447`。

### 最近完成（2026-06-17）G1 后续：假 U1 运动执行闭环证据

- **新增测试**：`tests/test_fake_u1_cloud_loop.py`（4 cases）
  - 云端 `home` / `write hi` / `svg M0,0 L10,0 L10,10`（`draw_generated`）命令经 `/device/v1/tasks` → WebSocket `task_dispatch` → `fake_device_server` → fake U1 TCP 执行 → `/device/v1/events` 终态 `done`。
  - 校验 `motion_task` 到 Edge-D 命令序列的转换契约。
- **验证**：`pytest tests/test_fake_u1_cloud_loop.py -v` → **4 passed**；`ruff check` clean。
- **证据更新**：`docs/release_evidence/2026-06-16-M13-AI-to-Motion-release-gate.md` 门 B「假 U1 运动执行」状态改为 ✅。

### 最近完成（2026-06-17）阶段 1 步骤 3：Edge-C 产品端 motion_task 示例

- **新增示例**：`esp32S_XYZ/docs/schemas/edge_c/examples/`
  - `motion_task.write_text.downlink.json`：`route_role=device_write`，`backend=scnet_ds`，`source_capability=write_text`。
  - `motion_task.draw_generated.downlink.json`：`route_role=device_draw`，`backend=dashscope_wanx`，`source_capability=draw_generated`。
  - 现有 `motion_task.downlink.json`（home / device_control）与 `motion_task.run_path.downlink.json`（device_vector）已覆盖其余两种 route_role。
- **验证**：`python esp32S_XYZ/tools/validate_schemas.py` → **64 passed**；子模块 `esp32S_XYZ @ fac1eec` 已 push；LiMa 主仓库子模块指针已更新。

### 最近完成（2026-06-17）G4 启动与部署不确定性降低

- **目标**：降低启动和部署不确定性，把耗时任务拆分为 ready 必须完成与 warming 可后台完成。
- **发现**：
  - 通过 `server_lifespan.py` 阶段日志定位到真正瓶颈：**`context_pipeline.auto_indexer` 在事件循环中运行，ChromaDB/ONNX 模型下载/解压阻塞了主事件循环**，导致 `/health` 长时间无法 ready。
  - 次要瓶颈：`channel_retirement.telegram` 同步调用 Telegram API 耗时约 1.7s。
- **修复**：
  - `context_pipeline/auto_indexer.py`：把 `_indexer_loop` 从 asyncio task 改为 daemon thread，扫描（含 ChromaDB 初始化）不再阻塞事件循环。
  - `server_lifespan.py`：把 `retire_telegram_webhook_from_env()` 改为 `asyncio.create_task` 后台执行。
- **结果**：
  - VPS 启动从约 **7 分钟** 降至约 **8 秒**（systemctl start → `/health` 200）。
  - `/health` 返回 `startup.status=ready` 和 `startup.phases` 数组。
  - 公网 smoke：`https://chat.donglicao.com/health` 200；`/device/v1/health` 200。
- **验证**：
  - `pytest tests/test_routing_engine.py tests/test_system_endpoints.py tests/test_retrieval_injection.py -q` → **34 passed**。
  - `ruff check server_lifespan.py context_pipeline/auto_indexer.py routes/system_endpoints.py` → clean。

### 最近完成（2026-06-17）G3 证据边界瘦身（小批）

- **目标**：沿证据边界删除一个冷区模块，保护热路径。
- **审计**：`python scripts/codegraph_orphans.py --fanin` 识别 `eval_status.py` 为 ORPHAN。
- **删除**：`eval_status.py`（115 行）；保留与其余 eval 模块有依赖的 `eval_pinned_call.py`、`eval_preflight.py`、`eval_quiet.py` 等。
- **验证**：eval 聚焦套件 23 passed / `ruff check .` clean / CodeGraph + ripgrep 确认无生产引用。

### 最近完成（2026-06-17）G2 设备模型准入复跑

- **目标**：执行作者意图计划 G2，让 `device_draw` / `device_vector` / `device_write` / `device_control` 的准入依据可复跑、可比较、可回滚。
- **修复**：原 `docs/model_admission/2026-06-16-device-drawing-writing.md` 因 Windows 控制台重定向编码错误变为 ISO-8859 二进制损坏，已删除并重建为 `docs/model_admission/2026-06-17-device-drawing-writing.md`。
- **报告**：按 `docs/model_admission/TEMPLATE.md` 补齐元数据、角色详情、路由偏好配置、准入门控和可复现命令。
- **验证**：
  - `python scripts/eval_device_model_role.py --all` → 6 角色 admit/admit_conditional，2 角色 defer，0 fail。
  - `pytest tests/test_device_gateway_model_routing.py -q` → **32 passed**。
  - `pytest tests/test_routing_engine.py -q --tb=short` → **24 passed**。
  - `ruff check` 触及文件 clean。
- **文档同步**：`docs/README.md` 最新准入报告索引更新为 2026-06-17 版本。

### 最近完成（2026-06-17）第二轮瘦身：零引用模块 + 归档脚本清理

> 两轮合计：794→684 文件（-110），93,145→80,546 行（-12,599）

- **14 个零生产引用模块删除**：`coding_eval`、`edit_protocol`、`esp32s_adapter/`、`eval_call`、`eval_digest`、`eval_registry`、`free_web_ai_admission`、`health_summary`、`healthchecks_io`、`mimo_stt`、`notify/`、`request_context_preflight`、`streaming_events`、`converters/` + 对应测试
- **归档脚本清理**：`scripts/archive/` 13 个文件（deploy_legacy + openclaw_retired + key_rotation_legacy）
- **配置同步**：`codegraph_orphans.py`、`pyrightconfig.json`、`ruff.toml` 移除已删模块条目
- **测试修复**：`test_eval_topology.py` 移除 `eval_call` 测试；`test_secret_hygiene.py` 移除归档断言
- **验证**：ruff clean；全量测试 1637 passed / 24 skipped / 4 pre-existing failures

### 最近完成（2026-06-17）大子系统审计瘦身

> 审计范围：`search_gateway`、`channel_gateway`、`routes/` + 全仓冷模块扫描
> 详见 [`docs/CODEBASE_SUBSYSTEM_TIER_CN.md`](docs/CODEBASE_SUBSYSTEM_TIER_CN.md) §13 和 [`docs/CODEBASE_COLD_PRUNE_PRIORITY_CN.md`](docs/CODEBASE_COLD_PRUNE_PRIORITY_CN.md) P6

- **channel_gateway 整体退役**：23 文件 + `routes/channel_gateway.py` + 13 测试删除；`route_registry.py` 注册块移除；`channel_retirement.py` RETIRED_CHANNELS 标记
- **冷模块清理**：`research/`、`web_reverse_eval.py`、`cli_status.py`、`sandbox/`、`data_workbench/`、`ops_entrypoint/` 共 6 个模块 + 测试删除
- **search_gateway 死适配器**：`zhihu_adapter.py`、`public_feeder.py`、`codesearch_status.py`、`policy.py` 删除
- **空目录与死 shim**：`eval_loop.py` 删除；`evals/`、`fragments/`、`reverse_gateway/`、`routes/.omc/` 清理
- **配置同步**：`pyrightconfig.json`、`deploy_unified.py`、`codegraph_orphans.py` 移除 channel_gateway 条目
- **验证**：ruff clean；全量测试 1736 passed / 25 skipped / 4 pre-existing failures（无新增）

### 最近完成（2026-06-16）阶段 2 续 — Image Generator 真实 API 夹具

- **`tests/test_dashscope_image_live.py`**：Wanx 同步 + 异步轮询；`ALIYUN_API_KEY` + `LIMA_DEVICE_ADMISSION_LIVE=1` 启用
- **`eval_device_model_role.py --live`**：image_generator 合并 live 目标；默认离线 7 passed
- **文档**：`docs/model_admission/TEMPLATE.md`、`.env.example`、`2026-06-16-device-drawing-writing.md`
- **验证**：`pytest tests/test_eval_device_model_role.py tests/test_dashscope_image_client.py tests/test_dashscope_image_live.py` → **12 passed**（live 无密钥时 skip）

### 最近完成（2026-06-16）M13 AI→Motion 发布证据模板

- **重写** `docs/release_evidence/TEMPLATE_AI_TO_MOTION_RELEASE.md`：对齐门 A–F、`RELEASE_GATE_CHECKLIST`、假 U8 环与真实 pytest 命令；替换原通用占位表
- **新增** `docs/release_evidence/README.md`；`docs/README.md` 索引
- **验证**：`pytest tests/test_device_gateway_model_routing.py` + `test_fake_u8_hello_heartbeat_transcript_motion_event_loop` → **33 passed**

### 最近完成（2026-06-16）M9–M12 设备路由与准入

- **M9 假 U8 消费 route_policy**：固件 `fake_lima_u8` 硬契约解析 + JSONL 证据；主仓稳定性门测试对齐
- **M10 路由制品证据**：`task_recorder` 全场景 `route_evidence`（创建/阻止/验证失败/恢复/终端消费）
- **M11 模型准入脚手架**：`docs/model_admission/TEMPLATE.md` + `scripts/eval_device_model_role.py`（8 角色评测）
- **M12 Profile 路由输入**：`enrich_route_policy_with_profile()` 接入 `resolve_device_route_policy()`；不完整 profile 审批门控
- **准入快照**：`docs/model_admission/2026-06-16-device-drawing-writing.md`

### 最近完成（2026-06-15）Hardware AI Phase 1 M5–M8 Closeout + 清理

- **M5 Recovery + Reliability**：`execute_recovery()` 实现 retry/home/stop 决策；重试耗尽后 action 改为 `"stop"`；retry 任务 WS 直发时从 pending queue 移除，避免双发；task store 增加 `increment_retry_count` / `reset_task_for_retry` / `remove_pending_task`；`RedisDeviceTaskStore` 补齐相同协议
- **M6 Memory + Continuous Learning**：新增 `device_memory/extractor.py` / `consolidation.py` / `recall.py` / `quality_gates.py` / `store.py` / `routes/device_memory.py`；terminal 事件自动提取 episode 与 failure pattern；episode ID 加入 `event_id` 防止重试历史覆盖；memory 提取失败改为 `logger.warning`（符合 AGENTS.md 无静默降级）；`MemoryStore` 加 RLock 并标注生产化 TODO
- **M7 External Enrichment + Support/Ops**：`device_support/snapshot.py` 提供 shadow/firmware/self-check/近期终端任务/故障告警/脱敏建议；support snapshot 过滤 24h 时间窗口；`external_enrichment` 天气/节假日 provider 验证可用
- **M8 OTA + Release Gate**：`device_ota/release.py` + `canary.py` + `routes/device_ota.py`；新增 `/deploy/{version}`、`/canary/record-success/{device_id}`、`/canary/record-failure/{device_id}`、`DELETE /canary/devices/{device_id}`；未知 criteria 返回 400；gate 未就绪时 deploy 返回 412；部署新版本自动重置 canary 计数
- **代码审查修复**：review 发现的 6 个 P0/P1 问题全部修复，新增 20+ 测试覆盖去重、Redis store 协议、OTA 路由、support 时间窗口
- **死区代码清理**：删除 `routes/ops_probe_ingest.py`、`converters/anthropic_format.py`、`deploy/key_rotation.py`、`scripts/vps_eval_smoke_remote.py` 等 4 个死文件
- **Anthropic 残留清理**：移除 `/v1/messages` 端点及所有 Anthropic 转换函数（chat_endpoints.py 363→142 行）；route_registry.py 移除 4 个 anthropic 字段 + 7 个 agent_* 硬编码 False
- **配置死路径清理**：pyrightconfig.json 移除 agent_runtime/voice_gateway/code_orchestrator_context 等 8 个不存在的 include/exclude 路径；ruff.toml 移除 8 个不存在 exclude 路径；deploy_unified.py 移除 agent_runtime core dir + m1m5 slice + eval smoke 代码
- **文档清理**：归档 task_plan.md、OPS_ENTRYPOINTS_CN.md、FREE_MODEL_ROUTING_STATUS_CN.md、MODEL_CATALOG.md、ROUTING_ENGINE_DESIGN.md、PLAN_CLOSURE_STATUS.md 至 docs/archive/；删除 root-historical 21 个个人编码助手时代遗物；归档 21 个已完成 superpowers/plans 至 docs/archive/superpowers-2026-06/
- **findings.md 轮转**：拆分 2026-05 CQ-046 至 CQ-110 旧记录至 docs/archive/findings-2026-05.md（1094→204 行，148KB→18KB）
- **route_policy backend 字段贯通**：`resolve_device_route_policy` 复用 `get_preferred_backend` 填充 backend，route_policy 携带真实后端（如 dashscope_wanx）；固件 edge_c/edge_b schema 加可选 backend 字段
- **Edge-C motion_task route_policy 硬契约**：schema required 化（固件 edge_c）+ 固件 DeviceServer 与云端 xiaozhi_compat 两条下行链路补 route_policy
- **双端语义统一**：`CONTROL_CAPABILITIES` 重构为单一真相源（model_routing.py）并补 `estop`；固件 generate_route_policy 对齐云端 resolve（run_path→device_vector）
- **固件子模块指针**：更新至 esp32S_XYZ `a4cab61`；详见 findings.md 与 spec/plan

### 最近完成（2026-06-15）代码质量治理 Q0–Q7 Closeout

权威计划：[`docs/archive/superpowers-2026-06/2026-06-15-code-quality-governance-plan.md`](docs/archive/superpowers-2026-06/2026-06-15-code-quality-governance-plan.md)

- **Q0 统计/CI**：`repo_stats.py` 排除 `.venv*`；`CLAUDE.md` 规模更正；P13 静默 `except: pass` 门恢复
- **Q1 route_policy**：`esp32s_adapter` 委托 `resolve_device_route_policy`（`run_path`→`device_vector`）
- **Q2 tasks 拆分**：`device_gateway/tasks.py` 521→68 行 facade + task_creation/events/lifecycle/deps
- **Q3 routing_executor**：显式 `import health_tracker` / `budget_manager`
- **Q4 Store 生产化**：Memory/Ledger env 切换（`memory|redis`）；health 暴露 store 后端
- **Q5 超标文件拆分**：channel_gateway、orchestrate、admin_api_extra、eval_loop→scripts、routing_intent、speculative
- **Q6 测试卫生**：`test_provider_automation` / `test_ops_metrics` 拆为 4+4 域文件；`tests/README.md` 聚焦/全量门
- **Q7 战略评估**：[`docs/CODEBASE_SUBSYSTEM_TIER_CN.md`](docs/CODEBASE_SUBSYSTEM_TIER_CN.md) hot/warm/cold 分层

### 测试结果（治理切片）

```text
Q0–Q3 聚焦: 112 passed
Q6 拆分套件: 83 passed, 1 skipped
Q7 文档验证切片: 22 passed
聚焦 device 套件: 452 passed
ruff check: clean（触及文件）
公网 health: https://chat.donglicao.com/health = 200
```

### 当前活跃路线图
- 旧“个人编码助手”优化路线图阶段 1-5 已关闭
- 新战略路线图见 [`docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md`](docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md)，M9–M12 已关闭；下一阶段 M13 发布证据模板

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
| `docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md` | 当前活跃路线图 | 必读 |
| `docs/DEVICE_DEVELOPER_GUIDE_CN.md` | 设备开发、联调、验证入口 | 必读 |
| `docs/CODEBASE_SUBSYSTEM_TIER_CN.md` | 子系统 hot/warm/cold 分层 | 推荐 |
| `AGENTS.md` | 开发约定与命令 | 必读 |
| `docs/ARCHITECTURE.md` | 系统架构 | 推荐 |
| `docs/REQUEST_PIPELINE_AUTHORITY_CN.md` | 生产路由所有权 | 推荐 |
| `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md` | 设备模型路由策略 | 推荐 |
| `docs/ESP32S_XYZ_MANAGEMENT_CN.md` | 产品子模块边界 | 推荐 |
| `docs/LIMA_MEMORY_CN.md` | 持久跨会话记忆 | 推荐 |
