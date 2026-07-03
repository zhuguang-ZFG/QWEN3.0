# LiMa 全项目改善计划（2026-07-03，执行版）

> 本计划基于 2026-07-03 三份全项目审计（后端 Python / Chat Web + 小程序 / ESP32 固件）制定。按 P0→P3 顺序执行，每项独立提交。所有文档用中文（AGENTS.md 硬规则）。禁 `git add .`，仅暂存相关文件。
>
> **仓库拓扑**：主仓库 `D:/QWEN3.0`（后端 + Chat Web + docs）；子模块 `esp32S_XYZ`（固件 + 小程序）。子模块改动流程：先在 `esp32S_XYZ/` 内提交推送 → 回父仓库 `git add esp32S_XYZ && git commit -m "chore: bump esp32S_XYZ submodule — <说明>" && git push origin main`。
>
> **发现统计**：3 CRITICAL · 11 HIGH · ~20 MEDIUM · ~15 LOW

---

# P0 — CRITICAL + HIGH 安全/正确性（M1 里程碑，立即修复）

## P0.1 微信小程序上传私钥核实与清理【CRI-F1 / LOW-W2】
**位置**：`esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/secrets/private.wxbf3c1e0013b46343.key`（1675B）
**现状**：子模块 `manager-mobile/.gitignore:31` 已写 `secrets/`，`git ls-files` 未跟踪。但需核实历史。
**步骤**：
1. 在 `esp32S_XYZ/` 子模块内执行：`git log --all --full-history --oneline -- 'server/xiaozhi-esp32-server/main/manager-mobile/secrets/private.wxbf3c1e0013b46343.key'`
2. **若曾提交**（有输出）→ 需用户决策：在 mp.weixin.qq.com 重置上传密钥后，用 `git filter-repo --invert-paths --path secrets/private.wxbf3c1e0013b46343.key` 清理历史，强制推送子模块
3. **若未提交**（无输出，当前证据倾向）→ 在 `manager-mobile/README.md` 顶部加「## 密钥保管」段落，说明 `secrets/*.key` 仅本地保存、已 gitignore、勿提交；确认 `.gitignore` 含 `secrets/` 与 `*.key` 两行
**验证**：`git ls-files esp32S_XYZ | grep -i '
--.key$'` 无输出；历史扫描无记录
**提交**：子模块 `docs(manager-mobile): document private upload key handling` → 父仓库指针更新

## P0.2 生产 NODE_ENV 错误【CRI-F2】
**位置**：`esp32S_XYZ/.../manager-mobile/env/.env.production:2` 与 `env/.env.test:2`
**现状**：两文件均为 `NODE_ENV = 'development'`，污染 vite 压缩/tree-shake
**目标**：
```diff
- NODE_ENV = 'development'
+ NODE_ENV = 'production'   # .env.production
+ NODE_ENV = 'test'         # .env.test
```
**步骤**：编辑 `.env.production` 第 2 行 → `NODE_ENV = 'production'`；编辑 `.env.test` 第 2 行 → `NODE_ENV = 'test'`
**验证**：`npx uni build --platform mp-weixin`，对比 `dist/build/mp-weixin` 体积应明显小于改前；`grep -r "NODE_ENV" env/` 确认无残留 development
**提交**：子模块 `fix(env): correct NODE_ENV for production/test builds` → 父仓库指针更新

## P0.3 vite.config.ts 环境变量泄露【CRI-F3】
**位置**：`esp32S_XYZ/.../manager-mobile/vite.config.ts:33,43,55`
**现状**：三处裸 `console.log('command, mode -> ', command, mode)` / `console.log('UNI_PLATFORM -> ', UNI_PLATFORM)` / `console.log('环境变量 env -> ', env)`，第 55 行打印全部 env（含 token 来源）。注意 `vite.config.ts:248` 的 `esbuild.drop` 只作用于业务代码，不影响 config 自身。
**目标**：移除三处 `console.log`，或包守卫：
```typescript
if (process.env.LIMA_DEBUG_BUILD === '1') console.log('command, mode -> ', command, mode)
```
（第 55 行的 env 打印必须直接删除，不得保留任何形式）
**验证**：`npx uni build --platform mp-weixin` 构建日志中 `grep -i "env ->\|UNI_PLATFORM\|command, mode"` 无输出
**提交**：子模块 `fix(build): stop leaking env vars in vite config logs` → 父仓库指针更新

## P0.4 流式对话非微信端静默失败【HIGH-F1】
**位置**：`esp32S_XYZ/.../manager-mobile/src/api/chat/chat.ts:76-78` 与 `:116-119`
**现状**：
```typescript
// #ifndef MP-WEIXIN
const pollTimer: ReturnType<typeof setInterval> | null = null  // 永远 null，从未启动
// #endif
...
abort: () => {
  requestTask.abort?.()
  // #ifndef MP-WEIXIN
  if (pollTimer) clearInterval(pollTimer)  // 永远 false
  // #endif
}
```
H5/App 端流式只能拿首包、无后续 chunk、无报错（uni.request 在非微信端不支持 `onChunkReceived` 流式）。
**目标（P0 最小修复）**：`#ifndef MP-WEIXIN` 分支改为 fail-loud，立即抛错避免静默失败：
```typescript
// #ifndef MP-WEIXIN
throw new Error('chatStream: streaming currently supported only on mp-weixin; use chatCompletion for non-mp clients')
// #endif
```
完整修复（P3.6）推迟：用 `fetch` + `response.body.getReader()` 实现非微信端 SSE 读取，配 `AbortController` 实现 abort。
**步骤**：先做最小修复，在 `:76-78` 替换为 throw；同步更新函数 JSDoc 标注平台限制
**验证**：H5 构建后调用 chatStream 应抛出明确错误（而非静默空响应）；`npx vue-tsc --noEmit` 0 errors
**提交**：子模块 `fix(chat): fail loud on non-mp-weixin streaming instead of silent no-op` → 父仓库指针更新

## P0.5 Chat Web 图片 URL XSS 域名白名单【HIGH-F6】
**位置**：`chat-web/chat-api.js:47-60`（图片生成分支）；复用函数在 `chat-web/chat-messages.js:60-73`（`isAllowedImageUrl`）
**现状**：`chat-api.js:50-53` 只校验 http/https 协议，**未做域名白名单**；`:58` `mediaHtml` 含 `escapeAttr(url)` 后 `:60` `innerHTML = mediaHtml`。`isAllowedImageUrl`（白名单 `image.pollinations.ai / chat.donglicao.com / api.donglicao.com`）只用于 markdown 路径。`js/devices.js:118,271,309` 多处 innerHTML 拼接（:123-124 已用 `escapeHtml`，需逐一确认其余）。
**目标**：在 `chat-api.js` 内引入 `isAllowedImageUrl`（与 chat-messages.js 同源白名单），对 `json.data[0].url` 校验：
```javascript
// chat-api.js 第 48 行后插入：
if (!isAllowedImageUrl(url)) throw new Error('图片地址来源不在白名单');
```
并在 `chat-api.js` 顶部定义 `isAllowedImageUrl`（复制 chat-messages.js:60-73 实现）。
**步骤**：1) chat-api.js 顶部加 `isAllowedImageUrl` 函数定义；2) `:48` url 取出后加白名单校验；3) 审查 `js/devices.js` 所有 `${...}` innerHTML 插值点（:118,271,309 等），确认每个动态值经 `escapeHtml`（:123-124 已合规，作为模板）
**验证**：浏览器 console 手动注入 `json.data[0].url='https://evil.com/x.png'` 应被拒；`grep -n "innerHTML" chat-web/js/devices.js` 逐行确认 escape
**提交**：主仓库 `fix(chat-web): enforce image URL allowlist in generate-image path`

## P0.6 后端静默降级硬规则违反【HIGH-B1】
**位置**：`xiaozhi_drawing/pipeline.py:122-123`
**现状**：
```python
122:    except ImportError:
123:        pass
```
`scikit-image` 是 `requirements_server.txt` 声明运行时依赖，ImportError 不应静默（AGENTS.md 点名禁止 `except ImportError: pass`）。
**目标**：
```python
    except ImportError as exc:
        logger.warning("scikit-image unavailable, falling back to ximgproc/morphological thinning: %s", exc)
```
**步骤**：1) 确认文件顶部已有 `logger`（若无则 `import logging; logger = logging.getLogger(__name__)`）；2) 替换 `:122-123`
**验证**：`python -m pytest tests/test_ci_gates.py -k p13 -v` 通过；`ruff check xiaozhi_drawing/pipeline.py`
**提交**：主仓库 `fix(drawing): warn on skimage import fallback instead of silent pass`

## P0.7 CI 静默降级门禁盲区【HIGH-B2】
**位置**：`tests/test_ci_gates.py:171-190`（`_p13_scan_paths`）
**现状**：仅扫 `device_gateway/`、`routes/`、根 `routing_*.py`/`http_*.py`/`server*.py`，遗漏 `xiaozhi_drawing/`、`context_pipeline/`、`session_memory/`、`observability/`、`code_context/`、`local_retrieval/`、`semantic_cache/` 等。
**目标**：改为排除式扫描——遍历 `ROOT` 下所有 `.py`，排除 `_P13_SKIP_DIRS`（已有 `data/.agents/.codegraph/venv/.venv*` 等）外加 `tests/scripts/reference/esp32S_XYZ/provider-probe-offline`。
**步骤**：重写 `_p13_scan_paths()`：
```python
def _p13_scan_paths() -> list[Path]:
    skip = _P13_SKIP_DIRS | {"tests", "scripts", "reference", "esp32S_XYZ", "provider-probe-offline"}
    out: list[Path] = []
    for p in sorted(ROOT.rglob("*.py")):
        if not p.is_file():
            continue
        if any(part in skip or part.startswith(".venv") for part in p.parts):
            continue
        out.append(p)
    return out
```
**验证**：`python -m pytest tests/test_ci_gates.py -k p13 -v` 通过；手动确认 `xiaozhi_drawing/pipeline.py` 在扫描列表内
**提交**：主仓库 `test(ci-gates): scan all production dirs for silent exception pass`

## P0.8 U1 OTA 安全加固【HIGH-W1】（需用户决策）
**位置**：`esp32S_XYZ/firmware/u1-grbl/Grbl_Esp32/src/WebUI/WebServer.cpp`（`/updatefw` 无签名/SHA）；`Config.h:130`（`#define ENABLE_AUTHENTICATION` 注释掉）、`Config.h:138-139`（明文 `admin`/`user`）
**决策**：STATUS.md 标注 U1 WiFi 启用为「待用户决策的产品权衡」。执行前需用户确认走 A 还是 B：
- **A. WiFi 不启用（推荐默认）**：`Config.h` 顶部加 `#define OTA_DISABLED_BY_DEFAULT` 并在 WebServer.cpp `/updatefw` 入口 `#ifdef OTA_DISABLED_BY_DEFAULT` 直接返回 403；注释说明启用前置条件（需先实现 B）
- **B. WiFi 启用**：移植 U8 `ota.cc:108 VerifyFirmwareSignature` 的 mbedtls 方案；`ENABLE_AUTHENTICATION` 取消注释；密码改 NVS 注入（参考 U8 mqtt NVS 模式）
**验证**：A 分支 `pio run -e release_esp32s3` 构建通过，`/updatefw` 返回 403；B 分支真机刷未签名固件被拒
**提交**：子模块 `fix(u1-ota): disable unsigned OTA by default` 或 `feat(u1-ota): enforce firmware signature verification` → 父仓库指针更新

## P0.9 U8 端点签名/白名单下发【HIGH-W2】（需用户决策）
**位置**：`esp32S_XYZ/firmware/u8-xiaozhi/main/ota.cc:282-323`（OTA 服务器响应 `mqtt`/`websocket` 段直接写 NVS，无签名）
**决策**：执行前需用户确认走「签名」还是「白名单」：
- **白名单方案（推荐，较简单）**：固件内置允许端点集合 `{chat.donglicao.com}`，`ota.cc:282-323` 解析出的 host 若不在白名单则拒绝写入 NVS 并 `ESP_LOGE`
- **签名方案**：OTA 服务器对 `mqtt`/`websocket` 段签名，固件用 `VerifyFirmwareSignature` 同公钥校验
**步骤**（白名单方案）：在 `ota.cc` 加 `IsAllowedEndpointHost(const std::string& host)`，`:282-323` 写 NVS 前校验
**验证**：真机用篡改端点的 OTA 响应测试，应被拒且日志报错
**提交**：子模块 `fix(u8-ota): allowlist server-pushed mqtt/websocket endpoints` → 父仓库指针更新

## P0.10 固件服务端残留基础设施清理 + 文档对齐【HIGH-W3】
**位置**：`esp32S_XYZ/server/xiaozhi-esp32-server/Dockerfile-server:3`（`COPY main/xiaozhi-server .` 复制已删目录）；`server/xiaozhi-esp32-server/README.md`（377 行上游 README，无删除标注）；`esp32S_XYZ/README.md:21`；`docs/getting-started.md:117-130` 与 CI 章节（~195 行）；`Makefile:15,29,38`
**现状**：服务端组件已于 2026-06-25 物理删除（`esp32S_XYZ/STATUS.md:13-15`），但 Dockerfile/README/getting-started/Makefile 仍指向已删目录。
**步骤**：
1. 删除 `Dockerfile-server`（无法构建）—— `git rm server/xiaozhi-esp32-server/Dockerfile-server`
2. `server/xiaozhi-esp32-server/README.md` 顶部加横幅：「⚠️ 本目录服务端组件（xiaozhi-server/manager-api/manager-web/digital-human）已于 2026-06-25 物理删除，能力迁移至 LiMa 主项目 device_gateway（见 D:\QWEN3.0\routes\device_app_*.py）。下方为上游历史 README，仅作参考。」
3. `esp32S_XYZ/README.md:21` 改「云端服务 (Python/Java/Vue/uni-app)」为「云端能力已迁移至 LiMa 主项目 device_gateway」
4. `docs/getting-started.md:117-130` 移除 `cd server/xiaozhi-esp32-server/main/xiaozhi-server` / `main/manager-api` 运行命令；CI 章节删「Java 测试 manager-api 76+」
5. `Makefile:15,29,38` 删 `build-server`/`test-java` help 文本
**验证**：`grep -rn "xiaozhi-server\|manager-api" esp32S_XYZ/README.md esp32S_XYZ/docs/getting-started.md esp32S_XYZ/Makefile` 仅在横幅/归档说明中出现；`make help` 无悬空文本
**提交**：子模块 `docs: mark deleted server components as migrated to LiMa device_gateway` → 父仓库指针更新

---

# P1 — MEDIUM 质量门禁 + 文档同步（M2 里程碑）

## 后端
- **P1.1** `session_memory/outcome_ledger/db.py:57-58` `except sqlite3.OperationalError: pass  # column already exists` → 改 `logger.debug("outcome column already exists, skipping: %s", col)`；`session_memory/store_voiceprint.py:172,256` 同理改 `logger.debug`（行为正确，幂等迁移，仅满足「非静默」字面规则）。确认各文件顶部有 logger。
- **P1.2** `observability/jsonl_store.py:38-39,46-48,52-54,76-78` 四处 `except OSError: pass` / `except FileNotFoundError: pass`（审计日志轮转）→ 改 `_log.warning("audit log rotation step failed: %s", type(exc).__name__)`（append-only 路径失败不应静默）。注意 `:80-81` 主 append 已有 `logger.warning`，合规。
- **P1.3** 文档同步：`AGENTS.md:141` 把「代码上下文 | code_context_injection.py | DEPRECATED v3.0」改为「代码上下文 | 已物理删除（v3.0 退役）」；`AGENTS.md:108,134,135` 把 `routing_engine.route()`/`routing_executor.execute()`/`http_caller.py` 改为包路径（`routing_engine/` 包、`routing_executor/` 包、`http_caller.py` thin re-export）；`AGENTS.md:38` 的 `pyright server.py routing_engine.py` 改为 `pyright server.py routing_engine/`；`docs/REQUEST_PIPELINE_AUTHORITY_CN.md:40` 同步删除 code_context_injection 行。
- **P1.4** `code_context/chroma_vector_store.py:29` `_log.debug("chromadb not installed, using in-memory fallback")` → `_log.warning(...)`（AGENTS.md:194 要求清晰警告）。

## 小程序
- **P1.5** 类型债务收敛（89 处 any / 15 处 as any）：优先 `src/api/v2/index.ts`、`src/utils/index.ts:7,76,433,437,444`、`src/api/chat/chat.ts:68,156`、`src/pages/device-config/components/wifi-config.vue:78,90`、`src/pages/v2/device-detail/index.vue:267`、`pages.config.ts:34`（`tabBar as any` 改正）、复核 `src/types/uni-pages.d.ts:98` `@ts-ignore`。分文件小步提交，每步 `npx vue-tsc --noEmit`。
- **P1.6** 删除死代码 `src/store/config.ts`：`fetchPublicConfig`（:42-45）仅写回默认值，旧版 `/user/pub-config` 已退役。先 grep 全树 `useConfigStore`/`fetchPublicConfig` 调用方，移除引用后删文件；清理 `store/user.ts:38-40` 与 persist 的双写不一致。
- **P1.7** API 层统一封装：11+ 处直调 `uni.request`/`uni.uploadFile`/`uni.downloadFile`（`api/v2/index.ts:23`、`api/chat/chat.ts:32,137`、`hooks/useServerUrl.ts:40`、`hooks/useUpload.ts:138`、`utils/uploadFile.ts:271`、`wifi-config.vue:38,65,82`、`wifi-selector.vue:53,80`、`create-utils.ts:78`）改走 `src/http/request/alova.ts`；移除 `alova.ts:154` 调试日志 `console.error('errorMessage===>', ...)`。
- **P1.8** 路由悬空：`src/types/uni-pages.d.ts:19` 引用 `/pages/mine/mine`（源不存在）→ 重新生成（`npx uni build --platform mp-weixin` 后 uni 插件刷新 `uni-pages.d.ts`），确认 `src/pages.json` 与 `dist/build/mp-weixin/app.json` 一致、无 `pages/mine/mine`。
- **P1.9** `manifest.config.ts:90` `urlCheck: false` → 加注释「开发期关闭，生产构建改 true」；确认 `aliyun.donglicao.com` 在小程序后台 request 白名单。

## Chat Web
- **P1.10** 域名配置统一：`chat-web/js/app-config.js:9-10`（`PRIMARY_ORIGIN`/`PILOT_ORIGIN`）、`js/app-boot.js:5-7`（`apiOrigin`/`wsOrigin`/`turnstileSiteKey`）、`index.html:10` CSP、`src/utils/index.ts:184-187,203`（`getChatBaseUrl` 硬编码 `aliyun.donglicao.com`）→ 收敛到 `app-config.js` 单一配置点，其余引用。

## 固件
- **P1.11** U8 死代码清理：`firmware/u8-xiaozhi/main/CMakeLists.txt:48-50,245-260` 移除 ml307/nt26/dual_network/rndis/esp_video 非目标板源码的无条件 append（目标板 `dlc_motor_control_p1_ai_board.cc:38` 仅继承 `WifiBoard`）。
- **P1.12** 协议版本管理：`docs/schemas/edge_{a,b,c,d}/*.json` 加 `schema_version` 字段（从 "1.0.0" 起）；固件与服务端协商版本不匹配时 fail-loud。
- **P1.13** U1 `platformio.ini:42-50` `[env]` 段（espressif32@3.0.0/esp32dev）与 `[env:release_esp32s3]:54`（6.8.1/esp32-s3-devkitc-1）矛盾 → 清理 `[env]` 段或加 `# inherited base, override in env:release_esp32s3` 注释。
- **P1.14** `docs/schemas/edge_a/README.md:3`、`edge_c/README.md:32,61` 引用的 `manager-api`/`BusinessServer`/`DeviceServer` 实现入口改指向 LiMa 主项目 `D:\QWEN3.0\routes\device_app_*.py` 与 `device_gateway/`。

## 测试基建
- **P1.15** 引入前端测试：小程序 `pnpm add -D vitest @vue/test-utils jsdom`，加 `vitest.config.ts`；优先覆盖 `src/utils/index.ts` 纯函数（`deepClone`、`sm2Encrypt/Decrypt`、`getEnvBaseUrl`、`isUrl`）；加 `package.json` script `"test": "vitest run"`。Chat Web 无构建链，暂缓。

**P1 验证**：后端 `python -m pytest --tb=short -q` + `ruff check .` + `pyright <改文件>` + `python scripts/check_code_size.py`；小程序 `npx vue-tsc --noEmit` + `npx uni build --platform mp-weixin` + `pnpm test`；固件 `pio run -e release_esp32s3`(U1) / `idf.py build`(U8)。

---

# P2 — LOW 清理（M3 里程碑，批量处理）

| # | 位置 | 行动 | 验证 |
|---|------|------|------|
| P2.1 | `http_caller.py`(41行 facade) | 加重导出符号完整性特征化测试 `tests/test_http_caller_reexports.py` | `pytest tests/test_http_caller_reexports.py` |
| P2.2 | `probe_loop.py`/`backend_probe_loop.py` | 各 docstring 顶部加交叉引用（参考 `health_probe.py:1-6` 模式） | `pyright` |
| P2.3 | `.env.example:9` | `LIMA_API_KEY=sk-lima-test-key` → `<set-your-lima-api-key>`；`:5` 同理 | `grep sk- .env.example` 无形似密钥 |
| P2.4 | `requirements_dev.txt` `httpx2~=2.5` | 评估移除，改 testclient 兼容方案 | `pytest tests/` |
| P2.5 | 小程序 `tabbarList.ts:23` TODO、`utils/index.ts:80` 注释 console | 清理 | `vue-tsc` |
| P2.6 | `manifest.config.ts:8-12` + `pages.config.ts:6-10` | 抽公共 `getMode()` 到 `scripts/get-mode.ts` | `uni build` |
| P2.7 | 子模块 `unpackage/res/icons/*.png` | `git rm`，加 `.gitignore` `unpackage/` | `git ls-files \| grep unpackage` 无 |
| P2.8 | `src/static/app/icons/1024x1024.png`(447KB) | 压缩或移出主包；评估启用 `subPackages`（`vite.config.ts:90` 已配 `pages-sub` 但目录不存在） | 构建体积对比 |
| P2.9 | `scripts/deploy_chat_web.py:34-63` | FILES 列表加 `_headers` | 部署后 `curl -I` 见 HSTS |
| P2.10 | `src/i18n/{zh_CN,en}.ts`(1700+行) | 加 `scripts/check-i18n-keys.mjs` CI 校验 key 一致性 | 脚本退出码 0 |
| P2.11 | U1 `platformio.ini:49` `min_spiffs.csv` | 分区表文件入库 `firmware/u1-grbl/extra/min_spiffs.csv` | `pio run` |
| P2.12 | U8 生产日志 | `sdkconfig.defaults` 加 `CONFIG_LOG_DEFAULT_LEVEL_INFO=y` 裁剪 | 构建日志确认 |
| P2.13 | `esp32S_XYZ/Makefile:15,29,38` | 删 build-server/test-java help（P0.10 已含，确认闭环） | `make help` |
| P2.14 | `getting-started.md` CI 章节 | 删 Java manager-api 测试（P0.10 已含，确认闭环） | grep |
| P2.15 | 小程序依赖冗余 | `pnpm remove @tanstack/vue-query`（未用）+ 9 个非目标 `@dcloudio/uni-mp-{alipay,baidu,jd,kuaishou,lark,qq,toutiao,xhs}` + macOS `@esbuild/darwin-*`/`@rollup/rollup-darwin-*` | `pnpm install` + `uni build` |

---

# P3 — 重构/技术债（M4 里程碑，按子系统拆分交付）

- **P3.1** 小程序超大组件拆分（目标单文件 ≤300 行）：`pages/v2/device-detail/index.vue`(761) 抽 `useDeviceDetail` composable + 子组件；`voiceprint/index.vue`(691)、`ultrasonic-config.vue`(667)、`chat/chat.vue`(635)、`index/index.vue`(604) 同理。每文件拆分独立提交 + type-check。
- **P3.2** Chat Web 模块化：`styles.css`(2060 行) 按页面拆分；`escapeHtml`/`escapeAttr`/`isAllowedImageUrl` 等 7 处重复（`chat-messages.js:43`、`js/api.js`、`js/devices.js`、`js/handwriting.js`、`js/keys.js`、`js/playground-utils.js`、`js/sidebar-devices.js`、`js/usage.js`）收敛到 `js/utils.js`（P0.5 在 chat-api.js 内的临时复制同步移除）；评估引入 esbuild 轻量打包。
- **P3.3** 小程序魔法数字统一：timeout 散落 `api/chat/chat.ts:47,150`(120000)、`hooks/useServerUrl.ts:43`(3000)、`http/request/alova.ts:82`(15000)、`api/v2/index.ts:18`(LOGIN_TIMEOUT_MS=30000)、`alova.ts:26`(REFRESH_COOLDOWN_MS=30000)、`blufi-config.vue:164`(10000)、`wifi-config.vue:41,75,85`(3000/15000/15000) → 抽 `src/config/timeouts.ts`。
- **P3.4** 固件核心模块单测 + CI 编译：为 `application.cc`(1246)、`ota.cc`(795)、`mqtt_protocol.cc`(390) 加 native 单测（参考现有 `test_u8_protocol_logic.cpp`）；将 U1/U8 纳入 CI 编译矩阵（`.github/workflows/ci.yml` 加 `idf.py build`/`pio run` job）。
- **P3.5** i18n 自动化校验（与 P2.10 配合）：`scripts/check-i18n-keys.mjs` 比对 `zh_CN.ts`/`en.ts` key 集合，CI 强制一致。
- **P3.6** 非微信端流式完整实现（推迟自 P0.4）：`src/api/chat/chat.ts` 用 `fetch` + `response.body.getReader()` 实现 SSE，配 `AbortController`，保持 `{ abort }` 接口。

---

# 跨阶段约定

## 验证命令清单（每阶段结项前全跑相关项）
```
# 后端
python -m pytest --tb=short -q
ruff check .
ruff format --check
pyright <改后文件>
python scripts/check_code_size.py
python scripts/run_pre_commit_check.py --full   # 生产变更

# 小程序（esp32S_XYZ/.../manager-mobile/）
npx vue-tsc --noEmit
npx uni build --platform mp-weixin
pnpm test                                        # P1.15 后

# 固件（esp32S_XYZ/）
pio run -e release_esp32s3      # U1
idf.py build                    # U8

# VPS 生产部署（主仓库后端/Chat Web 改动后）
python scripts/deploy_unified.py --slice core
python scripts/deploy_chat_web.py
curl -sf https://chat.donglicao.com/health
```

## 提交规范
- conventional commits：`fix(...)` / `feat(...)` / `test(...)` / `docs(...)` / `chore(...)` / `refactor(...)`
- 禁 `git add .`，仅暂存相关文件；禁暂存 `.claude/`、参考仓库、临时脚本、`.env`、`.lima-data/`
- 子模块改动 → 子模块内提交推送 → 父仓库 `git add esp32S_XYZ && git commit -m "chore: bump esp32S_XYZ submodule — <说明>" && git push origin main`
- 小程序改动额外触发「小程序一键上传」流程（AGENTS.md 常用命令）：type-check → build → 微信开发者工具 CLI upload → `manifest.config.ts` versionName/versionCode +1 → 子模块提交推送 → 父仓库指针更新

## 文档同步（每阶段结项）
- 更新 `STATUS.md` / `progress.md` / `findings.md`，附结项证据（命令输出、前后对比）
- 新增/更新 `docs/**/*.md` 用中文
- 本计划文件即执行文档，每阶段完成后在本文件顶部追加 `## M<N> 执行记录` 段落

## 需用户决策项（执行时停下确认，不得自行假设）
1. **P0.1** 私钥是否曾进 git 历史（`git log --all` 有无输出）→ 决定是否轮换密钥 + filter-repo
2. **P0.8** U1 WiFi 是否启用 → A 禁用分支 / B 加固分支
3. **P0.9** U8 端点加固 → 白名单方案 / 签名方案
4. **P1.15** 前端测试框架 → vitest（推荐）/ 其他
5. **P3.2** Chat Web 是否引入 esbuild 打包（影响模块化深度）

## 里程碑交付顺序
- **M1 = P0 全部**（10 项安全/正确性）→ 主仓库 + 子模块各一批提交 → VPS 部署验证 → 更新 progress.md
- **M2 = P1 全部**（质量门禁 + 文档 + 测试基建）
- **M3 = P2 全部**（LOW 批量清理）
- **M4 = P3 全部**（重构/技术债，可按子系统多次交付）
- 每里程碑完成更新 progress.md 并提议下一里程碑（AGENTS.md 里程碑协作协议）

## 风险与回滚
- **P0.1 filter-repo**：备份子仓库，强推后通知 fork 持有者
- **P0.8/P0.9 固件 OTA**：必须真机验证 fail-closed，避免锁死设备；保留旧固件回滚镜像
- **P1.5 类型清理**：可能暴露运行时 bug，分文件小步提交 + 每步 type-check
- **VPS 部署**：`deploy_unified.py` 自动备份至 `/opt/lima-router/backups/`

## 积极面（无需改动，记录备查）
后端主请求路径函数密度控制极佳（0 超 50 行）；U8 OTA 主体安全为最佳实践（fail-closed + HTTPS + 白名单 + SHA256 + 签名 + 日志脱敏）；CodeGraph + Ponytail + 581 测试 + CI 门禁成熟度高；固件 TODO/硬编码凭证已清零。本计划聚焦门禁边缘目录、文档同步、前端/固件测试缺口与子模块残留基础设施。
