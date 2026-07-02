# LiMa Findings

> 历史归档：2026-06 及更早非审计条目 → [`docs/archive/findings-2026-06-CN.md`](docs/archive/findings-2026-06-CN.md)
> AUDIT 审计批次：2026-06-28/29 AUDIT-1~12 → [`docs/archive/findings-2026-06-audit-CN.md`](docs/archive/findings-2026-06-audit-CN.md)

## 2026-07-02 系统瘦身 P2-17/18/19/20 + 参考改善 T1/T2 全部闭环

- **范围**：P2-17/18（UI 合并）、P2-19（settings 瘦身）、P2-20（except:pass 审查）+ T1-1（语义分类器）、T1-2（管道架构）、T1-3（Hershey 字体）、T2-2（健康探针）、T2-3（任务时间线）、T2-1（FluidNC 迁移准备）
- **P2-20 发现**：83 处 `except:pass/continue` 中仅 3 处是真正的宽泛异常静默吞掉（违反硬规则 #1），其余 80 处是特定异常类型（`json.JSONDecodeError`、`KeyError` 等）的合法控制流。审查脚本需区分 `except Exception:` 与 `except SpecificError:` 才能准确识别违规。
- **P2-19 发现**：6 种语言中 4 种（de/vi/pt_BR/zh_TW）是臆测添加——无实际用户、翻译不完整、i18n 键覆盖率低。裁到 zh_CN+en 后无任何功能损失。
- **P2-17/18 发现**：mine 页面本质是「设置页的子集」——声纹入口、退出登录、关于、设置跳转，全部可合并进 settings。WorkshopHome 与 device-list 数据源相同（`v2GetDevices`），Hero 卡片设计相似，合并为零信息损失。write-draw-panel 已是 2 步简化流，create/ 是高级模式，两者并存合理。
- **T1-1 发现**：n-gram TF-IDF 方案在不引入 sentence-transformers 重型依赖的前提下实现了毫秒级语义匹配（< 1ms），准确率覆盖核心意图（coding/chat/explanation/translation）。比正则规则维护成本低一个量级。
- **T2-3 发现**：Ledger 事件流已天然支持时间线查询，无需 schema 变更——`events_for_task` 已有事件记录，只需聚合视图层。
- **验证**：Python 4391 passed / 0 failed；ruff check clean；pyright 0 errors；vue-tsc 0 errors；mp-weixin 编译成功。

## 2026-07-02 小程序 UI 审查配合核实纠偏：三项指控两项伪判一项属实（BACKLOG-P2-1）

- **背景**：瘦身审查报告提三项 UI 指控（create 937 行嵌套两层 tab、3 首页重叠、settings 744 行杂物），并附「chat 与 create 重叠」隐含问题。逐项核实源码后真伪分明。
- **属实项**：`create.vue` 937 行嵌套两层 tab — **属实**。`mode`(ai-draw/image-draw) + `aiSubMode`(text/image) 两层切换，且两路走不同 API（`generateImage` 云生图 vs `v2SubmitTask` 设备任务），合成 937 行（script 254 + template 240 + style 430，style 占 46% 大头）。应拆两页，已拆（M2）。
- **部分属实项**：3 首页重叠 — **部分属实**。mine 统计卡（设备/在线/任务 3 数字）与 index 智能体页 Hero 设备卡的数据重复；mine「设备管理」「设备配网」两菜单跳底栏已有的 tab（多 1 步冗余跳转）。已去重（M3：mine 删统计+删冗余菜单，转纯账号页；index Hero「设备 X 台」改为「在线 X/总 Y 台」吸收在线统计）。
- **伪判项 1：settings 744 行「杂物」** — **不属实**。逐区块核实，全部是设置页职责（网络设置/缓存管理/隐私权限/通知订阅/注销账号/关于我们/语言设置），无一非设置功能混入。臃肿源于 7 个 section 的标题+卡片壳样式重复未抽组件，加 `useConfigStore`/`systemInfo` 2 处死代码。已抽 `SectionCard` 组件去样式重复 + 删死代码（M1），744→655 行。
- **伪判项 2：chat 与 create 重叠** — **不属实**。chat 用 `chatCompletionStream`(文本流式 LLM)、create 用 `generateImage`+`v2SubmitTask`(生图/设备任务)，零交叉导入，入口逻辑不重复。不动。
- **教训**：审查「行数/嵌套层数」计数可信，但「杂物/重叠」定性不可信。改 UI 前必须逐区块核实每个功能点的归属（是否真在该页职责范围、是否真与它页重复），不能按行数或审查措辞盲改。

## 2026-07-02 agent 配置树合并纠偏：审查「8 棵树 9300 行重复」多数被 gitignore 不入库（BACKLOG-P1-4）

- **背景**：瘦身审查报告称「~9300 行 agent 指令跨 8 棵配置树（`.agent`/`.claude`/`.kimi-code`/`.cursor`/`.joycode`/`andrej-karpathy-skills`/根），Ponytail 规则重复 6 处」，建议合并。
- **纠偏结论**：8 棵树中 **5 棵被 `.gitignore` 忽略、不入库**（`.agent`=行361、`.claude`=行130、`.kimi-code`=行28、`.continue`=行363、`andrej-karpathy-skills`=行47）——这些是各 IDE/Agent 工具的**本地私有配置**，重复是工具生态正常现象，不应也不能「合并」。
- **真正入库的 agent 树**仅 5 个：`.cursor`(2 rules)、`.joycode`(2 memory)、`skills`(14)、`AGENTS.md`、`CLAUDE.md`。其中真正冗余的只有 `.cursor/rules/` 两份：
  - `ponytail.mdc`（`alwaysApply:true`）与 `docs/AGENTS_PONYTAIL.md`（被 `AGENTS.md` 引用为权威 Ponytail 顾问规则源）内容重复。
  - `ecc-workflow.mdc`（`alwaysApply:true`）与 `docs/ECC_WORKFLOW_CN.md`（被 `AGENTS.md` 引用为权威 ECC 流程源）内容重复。
- **处置**：删除 `.cursor/rules/ponytail.mdc` + `ecc-workflow.mdc`，`AGENTS.md` 保持单一权威源；保留 `.cursor/rules/lima-*.mdc`（未入库的本地 Cursor 私有 rules，不影响入库面）。
- **教训**：审查把「本地工具私有配置」也算入「跨树重复」是口径错误。合并前必须 `git ls-files <tree>` 区分入库与本地私有——后者重复无害、前者才是可统一项。

## 2026-07-02 静默降级审查纠偏：审查报告「16 处」实际一等生产路径仅 4 处（BACKLOG-P1-2）

- **背景**：瘦身审查报告称生产路径有 16 处 `except: pass/continue` 静默降级，点名 `voice_pipeline_ws.py`/`mqtt_client.py`/`store_voiceprint.py` 各 2 处。用 Explore 子代理逐点实地核查。
- **纠偏结论**：审查的「计数」准确（这些文件确各有 2 处 pure-swallow），但「严重度」错误——被点名的 6 处**全部合规**：
  - `voice_pipeline_ws.py`：`asyncio.TimeoutError`→continue（队列轮询超时，正常循环）、`asyncio.CancelledError`→pass（关闭时等待已取消 worker）；两处广义 `except Exception`（L123/L131）不是吞——它们 `_send_error` 后 return，worker 广义 handler（L169）有 `warning(exc_info=True)`。
  - `mqtt_client.py`：`asyncio.CancelledError`→pass（stop 时任务取消，兄弟 `except Exception`（L105）有 warning）、`asyncio.TimeoutError`→pass（消息泵 `wait_for` 超时后 drain，惯用法）；`except ImportError`（L187）不是静默——前面有两条 `_log.info`。
  - `store_voiceprint.py`：两处 `sqlite3.OperationalError`→pass 均是 schema 迁移幂等（`# column may not exist yet` / `# Column already exists`），有注释；所有广义 `except Exception`（L51/L150/L185/L208）都有 warning。
- **真正违反 AGENTS.md「禁止静默降级」的一等生产路径 = 4 处**（广义 `except Exception` 裸吞、零日志），本轮已全部修复补日志：
  - `routing_executor_parallel.py`（并行降级执行器）、`speculative_execution.py`（推测竞速内层 future）、`observability/jsonl_store.py`（读遥测文件）、`provider_automation/adapters/cloudflare.py`（编码评分循环）。
- **边界项（本轮不改，记录待排期）**：`packages/provider-probe-offline/provider_probe/reverse/auth_detector.py:64`、`pricing_probe.py:74` 各 1 处——冷离线提供商探测工具，不在生产请求路径，风险低。若后续要求「全仓零裸吞」再统一处理。
- **教训**：修静默降级不能按 grep pattern 计数盲改。窄化异常（`asyncio.TimeoutError`/`sqlite3.OperationalError`/`json.JSONDecodeError`）做控制流是合规的；只有「广义 `except Exception` + 无日志 + 无重抛」才是违规。审查报告的计数可作线索，严重度判定必须逐点复核。

## 2026-07-02 系统瘦身审查：四维度过度设计诊断 + DEPRECATED 标记误标发现

- **背景**：用户质疑「小程序交互复杂化」+「后端过度设计」。对固件/后端/文档/小程序四维度做了量化审查，确认过度设计系统性存在。详见 `docs/superpowers/specs/2026-07-02-system-slimdown-design.md`。
- **关键发现（误标 bug）**：`speculative_policy.py` 和 `capability_matrix.py` 顶部标 `# DEPRECATED v3.0 — coding capability retired`，但实际：
  - `speculative_policy.py` 的 `AFFINITY`/`classify_complexity`/`get_affinity_backends` 被 `speculative.py`（请求流水线推测执行步骤）和 `context_pipeline/complexity.py` **活跃 import 使用** —— 是热路径，非死代码。
  - `capability_matrix.py` 的 `classify_intent` 仍被 `tests/test_capability_matrix_intent.py` 测试。
  - **直接删除会导致生产崩溃**。真实情况是「coding 能力退役，但模块本身未退役」。
- **处理**：已修正两个文件的顶部注释，明确区分「coding 退役」与「模块退役」。`routes/eval_internal.py` 确为退役态（返回 410，测试断言），保持原状。
- **教训**：「DEPRECATED」标记的语义必须精确 —— 标记某个能力的退役 ≠ 标记整个文件可删。删前必须 grep 调用方 + codegraph impact 双重确认。
- **其他 P0 已完成**：修 AGENTS.md 3 处断链（reference/ECC→.claude/ecc、reference/ponytail/ 不存在）；修 STATUS.md Telegram 措辞矛盾（通知通道退役 vs gallery 存储 API 复用，两者不同）；删 `.claude/skills/gitnexus/`（与 AGENTS.md「禁止 GitNexus」冲突）；P0-2 U8 音频协议已选方案 A 并改代码。
- **U8 音频协议矛盾（P0-2，已选方案 A，代码已改）**：用户选择方案 A「固件改 PCM」。已在 U8 固件实现上下行 PCM 透传，同时保留 MQTT/Xiaozhi 的 OPUS 编解码路径不破坏：
  - `AudioStreamPacket` 新增 `format` 字段（默认 `"opus"`）；
  - `protocol.h` 新增 `UsesPcm()` 接口，`WebsocketProtocol` 返回 `true`，`MqttProtocol` 继承默认 `false`；
  - `application.cc` 在协议初始化后调用 `audio_service_.SetSendPcm(protocol_->UsesPcm())`；
  - `websocket_protocol.cc` 对下行音频包设置 `format="pcm"`；
  - `audio_service.cc` 的 `OpusCodecTask` 中：上行按 `send_pcm_` 选择 PCM 透传或 OPUS 编码；下行按 `packet->format` 选择 PCM 透传或 OPUS 解码；`PlaySound` 保持 `format="opus"`。
  - **结果**：U8 连接 LiMa 时，hello 帧 `format="pcm"` 与实际发送格式一致；后端无需新增 OPUS 解码依赖。待实际烧录 U8 后验证实时语音/TTS 回放的端到端效果。
- **BACKLOG-P0-1 已关闭**：`deploy_unified.py` 已支持 `--target {aliyun,jdcloud}`，默认 `jdcloud`，避免默认部署到旧 Aliyun pilot 而生产入口在 JDCloud 的错误。详见 `progress.md` 同日期条目。

## 2026-07-01 前端匿名聊天请求已分流至阿里云 pilot

- **结论**：chat-web、`www.donglicao.com` playground、manager-mobile H5 的匿名简单聊天请求现在会发送到 `https://aliyun.donglicao.com/v1/chat/completions`，由阿里云 `lima-router-pilot`（仅免费后端）处理。
- **实现机制**：
  - **chat-web**：`chat-web/js/app-config.js` 运行时判断无 API Key + 默认模型 + 无 tools/图片时选择 pilot；`chat-api.js` 统一通过 `LiMaConfig.getApiUrl()` 获取 URL；`sendMessage()` 在 pilot 返回 429/503/5xx 或网络错误时自动回退主节点一次。
  - **官网 playground**：`donglicao-site-v2/app/developer/playground/page.tsx` 在 API Key 为空且 endpoint/model 为默认 chat 时自动切换 baseUrl。
  - **manager-mobile**：`utils/index.ts` 新增 `getChatBaseUrl()`，未登录且默认模型时返回 `aliyun.donglicao.com`；`api/chat/chat.ts` 流式/非流式 chat 均使用该 baseUrl。
  - CSP `connect-src` 已增加 `https://aliyun.donglicao.com`。
- **部署**：
  - GitHub Actions `Deploy Chat Web` / `Deploy Next.js Site` workflow 已自动部署到 Cloudflare Pages。
  - 京东云 `/opt/lima-router/chat-web` 源文件已同步，作为 FastAPI `/chat/` 静态回源。
  - 京东云 tunnel 入口由直连 `:8080` 改为 `https://127.0.0.1:443`（跳过 TLS 校验），恢复 nginx 作为入口，从而支持 `/mobile/` H5 目录。
  - manager-mobile H5 构建 base 设为 `/mobile/` 并通过 `scp -r` 部署到 `/var/www/chat/mobile/`。
- **验证**：
  - `https://app.donglicao.com/` 与 `https://www.donglicao.com/developer/playground/` 均引用 `aliyun.donglicao.com`。
  - `https://chat.donglicao.com/mobile/index.html` 返回 H5 入口，资源路径以 `/mobile/assets/` 开头。
  - 直接 POST `aliyun.donglicao.com/v1/chat/completions`（Origin: chat.donglicao.com）返回 200，CORS 正常，后端为 `pollinations_openai`。
- **风险与后续**：
  - Cloudflare Worker 兜底/灰度方案已实施并验证：新增 `cloudflare/workers/chat-router.js`，部署到 `chat.donglicao.com/v1/chat/completions*`；无 Authorization 的匿名 chat 由 Worker 代理到 pilot（响应头 `X-Lima-Backend: aliyun`），pilot 异常时自动回源京东云（`X-Lima-Backend: jdcloud`）。
  - manager-mobile 微信小程序包尚未重新上传发版；H5 已部署。

## 2026-07-01 全栈深度质量检查（LiMa + Web + chat-web + 小程序 + 固件）

### 检查范围与结果

- **LiMa 后端**：pytest 4249 passed / 0 failed；ruff clean；pyright 0 errors；code size PASS（修复后）。
- **donglicao-site-v2**（Next.js 官网）：XSS 0、密钥泄漏 0、SEO 正确、apex→www 重定向安全。发现 1 个 MEDIUM：`public/_headers` 缺 CSP/HSTS/X-Frame-Options（仅 X-Content-Type-Options + Referrer-Policy），加固版仅存在于未启用的 `nginx-headers.conf.example`。
- **chat-web**（Cloudflare Pages 前端）：Turnstile 服务端验证正确（fail-closed）、SRI 完整、无密钥泄漏。发现 5 个 MEDIUM：(1) `_headers` 无 HSTS；(2) `'unsafe-inline' script-src` + sessionStorage token 提升 XSS 影响；(3) Turnstile site key 配置但 secret 缺失时静默放行；(4) `hash-assets.mjs` 遗漏根级 `chat-*.js`（immutable 缓存无 bust）；(5) devices.js status 插值未 escape（当前数据安全）。
- **小程序 manager-mobile**：Bearer bug 已修复、AppID 一致、HTTPS/WSS 全覆盖。发现 4 个 MEDIUM：(1) 设备转移 unionid 发送为 `toPhone` 字段（后端契约待核实）；(2) 上传文件类型验证被注释掉；(3) 登录态基于 accountId 而非 token（可能误跳转登录）；(4) 非 WeChat 端 chat streaming fallback 为死代码。
- **固件 esp32S_XYZ**：AUDIT-12 全部 6 项控制（OTA 签名/URL 白名单/WS 鉴权/坐标边界/日志脱敏）均 PRESENT 且无回归。发现 1 个 MEDIUM：`McpServer::DoToolCall` 跳过 `user_only` 执行门禁（未认证本地 WS 可 `tools/call self.reboot` DoS，固件安装仍被 F1 签名门禁阻断）。4 个 LOW：control_ws_token 无写入者（默认开放）、token 比较非常量时间、activation 失败日志含完整响应体、IDF floor 5.5.2 可升 5.5.3。

### 本次修复（3 项）

1. **`config/settings_core.py` 301 行 → 280 行**（违反 ≤300 硬规则）：提取 `get_key_pool_raw`/`resolve_backend_key`/`get_env` 三个纯函数到新 `config/settings_helpers.py`；`config/settings.py` 更新导入源。code size 检查从 FAIL → PASS。
2. **Turnstile fail-open 警告**（`device_logic/turnstile.py`）：当 `TURNSTILE_SITE_KEY` 已配置但 `TURNSTILE_SECRET_KEY` 为空时，启动日志输出 `WARNING`（之前静默放行，无任何日志）。
3. **死代码清理**（`server_lifespan_phases.py`）：移除 `start_auto_indexer`/`stop_auto_indexer` 定义（commit `ba3d64ee` 已移除调用但保留了函数定义）。

### 待跟进项（需独立排期）

- ~~**donglicao-site-v2 `_headers`**~~：✅ 已完成（2026-07-01 第二轮修复：补 CSP/HSTS/X-Frame-Options/Permissions-Policy）。
- ~~**chat-web `hash-assets.mjs`**~~：✅ 已完成（2026-07-01 第二轮修复：扩展哈希覆盖根级 `chat-*.js`）。
- ~~**chat-web `_headers`**~~：✅ 已完成（2026-07-01 第二轮修复：补 HSTS）。
- ~~**6 个 SAFE dependabot PR**~~：✅ 已手动应用（fastapi 0.138.2、python-multipart 0.0.32、pyright 1.1.411、pytest-timeout 2.4、httpx 0.28.1、websockets 16.0）。
- **小程序设备转移 `toPhone` 字段**：核实后端契约是否期望 unionid。
- **固件 `DoToolCall` user_only 门禁**：在执行路径增加 `user_only` 检查。
- **4 个 RISKY dependabot PR**（torch/torchaudio/dashscope/onnxruntime）建议关闭。
- **7 个需独立审查 PR**（eslint-10/typescript-6/types-node-26/react/tailwindcss/vue/wrangler-action/setup-node）。

### 第二轮修复（2026-07-01，commit 49f55b61）

- **`client_keys/storage.py`**：`update_usage()` 改为 raise `ClientKeyStorageError`（不再静默吞 sqlite3.Error）；`import json` 提到模块级。
- **`access_guard.py`**：`_dynamic_auth_configured` 从 bare `Exception` 收窄为 `(ImportError, AttributeError)`。
- **`device_logic/wechat_gateway.py`**：`response.json()` 移入 try/except（ValueError 捕获）；`import time` 提到模块级。
- **`routes/client_keys.py`**：4 个 mutation 端点返回 typed `KeyMutationResponse`（`response_model_exclude_none=True`）。
- **合并重复测试**：`test_security_headers.py` 删除，唯一 `csp_is_strict` 测试并入 `test_routes_security_headers.py`。

## 2026-07-01 Dependabot / pip-audit 依赖漏洞修复

- **扫描结果**：本地 `.venv310` 运行 `pip-audit --local` 发现 5 个包共 17 个已知漏洞：
  - `cryptography 48.0.0` → GHSA-537c-gmf6-5ccf（OpenSSL 静态链接漏洞）
  - `Pillow 10.4.0` → CVE-2026-25990 / CVE-2026-40192 / CVE-2026-42308 / CVE-2026-42310 / CVE-2026-42311
  - `pip 23.0.1` → CVE-2023-5752 / CVE-2025-8869 / CVE-2026-1703 / CVE-2026-3219 / CVE-2026-6357 / CVE-2026-8643
  - `python-multipart 0.0.30` → CVE-2026-53540（负 Content-Length 导致无界读取）
  - `starlette 1.2.1` → CVE-2026-54282 / CVE-2026-54283（urlencoded 表单限制绕过、URL 主机欺骗）
- **修复操作**：
  - 升级本地 venv：`pip==26.1.2`, `cryptography==48.0.1`, `Pillow==12.2.0`, `python-multipart==0.0.31`, `starlette==1.3.1`。
  - 收紧 `requirements_server.txt`：
    - `python-multipart>=0.0.31,<1.0`
    - `Pillow~=12.2.0`
    - 新增显式下限：`starlette>=1.3.1`（FastAPI 传递依赖）、`cryptography>=48.0.1`（Paramiko 传递依赖）。
- **验证**：
  - `pip-audit --local` → `No known vulnerabilities found`。
  - 聚焦 Pillow 相关测试：`tests/test_svg_converter.py`, `tests/test_svg_converter_sketch.py`, `tests/test_svg_binarize.py` → 33 passed。
  - 聚焦 FastAPI/Starlette 相关测试：`tests/test_device_app_auth.py`, `tests/test_routes_chat_preflight.py`, `tests/test_routing_engine_post.py` → 25 passed。
  - 完整门禁 `scripts/run_pre_commit_check.py --full` → 4239 passed, 3 skipped, ruff 通过。
- **扩展修复（esp32S_XYZ 子模块）**：
  - 子模块仓库同步提交并 push 到 `zhuguang-ZFG/esp32S_XYZ`。
  - `esp32S_XYZ/requirements.txt`：`pytest>=9.0.3`（CVE-2025-71176）。
  - `esp32S_XYZ/firmware/u8-xiaozhi/scripts/Image_Converter/requirements.txt`：`Pillow~=12.2.0`。
- **扫描工具误报说明**：
  - 运行 `pip-audit` 时，本地杀毒软件将 `cyclonedx-python-lib` 的 `vulnerability.cpython-310.pyc` 误报为 `HEUR:HackTool/VulnScan.a` 并删除。
  - 已执行 `--force-reinstall pip-audit` 恢复，`pip-audit --local` 再次运行正常。
- **扩展修复（前端与容器）**：
  - `donglicao-site-v2/package.json`：添加 `overrides` 强制 `postcss>=8.5.10`；`npm audit` 归零，`npm run build` 成功。
  - `docs-site/pnpm-workspace.yaml`：添加 `overrides` 强制 `vite ^6.4.3`、`esbuild ^0.25.0`；`pnpm audit` 归零，`pnpm run build` 成功。
  - `Dockerfile`：基础镜像从浮动 `python:3.10-slim` 固定为 `python:3.10.20-slim-bookworm@sha256:89cef4d55961e885def21b86e34e102e65b7eab8cd281e806a66ff1709c9a455`。
- **额外修复**：
  - `.github/workflows/test.yml`：将错误的 `actions/checkout@v7`、`actions/setup-python@v6`、`actions/cache@v6` 改为正确的 v4/v5/v4。
  - 2026-07-01 新增 CI `pip-audit -r requirements_server.txt` 门禁（`PYTHONUTF8=1`），与 `bandit` 合并到 `Security scan` 步骤。
- **仍未修复的告警**：
  - GitHub push 后仍提示 default branch 有 16 个漏洞（7 high, 9 moderate）。本地可扫描的 manifests 已全部 clean，剩余可能来源：
    - GitHub Dependabot 计数存在延迟/缓存。
    - `esp32S_XYZ` 子模块中其他未扫描的旧 npm/pnpm/Dockerfile manifests（如 `u1-grbl/embedded` 仍有 33 个高危/严重级漏洞，`xiaozhi-esp32-server/main/manager-mobile` 因私有 registry 无法 audit）。
    - Dockerfile 固定 digest 后仍可能存在 Debian 系统级未修补 CVE。
- **风险与后续**：
  - Pillow 大版本 10→12 已确认通过全部图像处理测试；生产部署后需观察 `xiaozhi_drawing/svg_converter.py` 与 `device_logic/captcha.py` 行为。
  - pip 大版本 23→26 仅影响包安装流程，未引入运行时变更。
  - ~~建议后续在 CI 中加入 `pip-audit --requirement requirements_server.txt` 门禁。~~ ✅ 已完成（2026-07-01）：`.github/workflows/test.yml` 新增 `pip-audit -r requirements_server.txt` 步骤，环境变量 `PYTHONUTF8=1` 规避 Windows 编码问题。
  - 子模块中遗留的旧前端构建链（gulp/cheerio/underscore 等）如需继续修复，涉及直接依赖大版本升级，可能破坏 ESP32 固件构建流程，需单独评估。


## 2026-07-02 external_enrichment provider 占位状态确认

- `external_enrichment/providers/nager_date.py` 与 `open_meteo.py` 方法体仅返回硬编码 mock（`# TODO: Actual API call would go here`）。
- 确认：两文件被 `tests/test_external_enrichment.py` 明确用作离线测试 mock（docstring 标注 "offline tests with mock"）。
- 结论：保留，不为瘦身删除测试依赖。真实 API 接入留待功能驱动时再做（YAGNI）。

## 2026-07-02 CodeGraph 死函数复审（13 个候选）

> 候选来自瘦身审查「疑似 0 调用点函数」清单。用 CodeGraph `edges.target` fan-in + 全库 grep 双重确认。

### 删除（12 个，CodeGraph fan-in=0 且 grep 全库无调用点、无装饰器、无同文件引用）

| 文件:行 | 函数 | 说明 |
|---------|------|------|
| token_health.py:110 | `alert_expired_tokens` | 疑似未接 cron，无调用方 |
| model_registry.py:108 | `get_active` | 与 key_pool.get_active_count 名字近但无关联 |
| backends_registry/__init__.py:85 | `get_backend` | 与 health_state.get_backend_* 名字近但无关联 |
| device_gateway/mqtt_client.py:34 | `is_mqtt_enabled` | 调用方直接读 DEVICE.mqtt_enabled |
| device_gateway/mqtt_client.py:46 | `mqtt_send_to_device` | async 投递函数，无调用方 |
| context_pipeline/cache.py:74 | `build_cached_prompt` | 仅改 _metrics 统计，无调用方 |
| route_scorer.py:97 | `task_fit_score` | 编码退役后纯函数无调用方 |
| user_identity/lessons.py:66 | `apply_lesson` | 有文件写副作用但无任何调用方 |
| context_compressor.py:165 | `estimate_context_usage` | 纯计算，无调用方 |
| session_memory/compactor.py:121 | `llm_summarizer_factory` | 工厂函数，无注入式调用方 |
| channel_retirement.py:17 | `is_retired_route_path` | 纯函数，无调用方 |
| key_pool.py:251 | `provider_snapshot` | 委托 pool_snapshot，无调用方（与 provider_automation/snapshot_store 模块名近但无关联） |

### 保留（1 个）

| 文件:行 | 函数 | 保留原因 |
|---------|------|----------|
| observability/prometheus_metrics.py:199 | `record_backend_error` | 有测试覆盖（test_observability_metrics.py:90），疑似预留 prometheus 调度入口，YAGNI 保守保留 |

### 验证
- ruff check 11 个文件 clean
- check_code_size PASS
- 聚焦测试 64 passed（test_token_health/test_model_registry/test_backend_registry/test_route_scorer/test_channel_retirement/test_key_pool）
