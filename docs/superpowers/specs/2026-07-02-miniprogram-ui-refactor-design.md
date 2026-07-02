# 小程序 UI 深度重构设计文档

- **日期**：2026-07-02
- **状态**：已完成（M1 + M2 + M3 + M4 全部实施并推送）
- **关联**：`2026-07-02-backlog-planning.md` BACKLOG-P2-1
- **背景**：瘦身审查报告三项 UI 指控，经逐项核实后真伪分明，本重构按「真问题改、伪指控纠偏」执行。
- **范围**：小程序端（`esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/`）UI 去重、拆页、抽公共组件。后端零改动。

---

## 一、核实纠偏（审查报告真伪）

| 审查指控 | 真伪 | 依据 |
|---|---|---|
| create.vue 937 行嵌套两层 tab | **属实** | `mode`(ai-draw/image-draw) + `aiSubMode`(text/image) 两层切换，两路走不同 API（`generateImage` 云生图 vs `v2SubmitTask` 设备任务），合 937 行臃肿 |
| 3 首页重叠 | **部分属实** | mine 统计数字（设备/在线/任务）与 index Hero 设备卡重复；mine「设备管理」「设备配网」菜单跳底栏已有的 tab（冗余跳转） |
| settings 744 行「杂物」 | **不属实** | 逐区块核实，全部是设置页职责（网络/缓存/隐私/通知/注销/关于/语言），无非设置功能混入。臃肿源于 7 个 section 样式重复未抽组件 + 2 处死代码（`useConfigStore`、`systemInfo`） |
| chat 与 create 重叠 | **不属实** | chat 用 `chatCompletionStream`、create 用 `generateImage`+`v2SubmitTask`，零交叉导入 |

**教训**：审查报告的「计数」可信，但「严重度判定」不可信。修 UI 前必须逐项核实哪些是真冗余、哪些是合理职责分区，不能按行数盲改。

---

## 二、实施里程碑

### M1 — 抽公共组件 + settings 死代码清理（无破坏性）

**新增组件**：
- `src/components/section-card.vue`（≤30 行）：抽自 settings 7 个分区的标题+卡片壳样式，支持 `variant: 'default' | 'danger'`（danger 用于账号注销红色变体）。
- `src/components/stat-pill.vue`（≤80 行）：抽自 mine/index 的统计药丸（数字+标签+skeleton），支持 `tone: 'default' | 'online' | 'tasks'` 色调变体。预留给后续统计场景复用。

**settings/index.vue**（744→655 行，-89）：
- 7 个 `<view class="*-section">` 重复样式壳 → `<SectionCard :title="...">` 组件调用。
- 删 2 处死代码：`useConfigStore` import + `configStore` 声明（无模板引用）；`systemInfo` computed + `computed/getSystemInfoSync` import（无模板引用）。
- 视觉零变化（纯样式提取）。

**提交**：`refactor(miniprogram): extract SectionCard/StatPill, prune settings dead code (P2-1/M1)` — 子模块 `a6e1e60`

### M2 — create.vue 拆两页（审查属实项）

**问题**：create.vue 937 行，`mode`(ai-draw/image-draw) + `aiSubMode`(text/image) 两层嵌套 tab，两路分别调 `generateImage`（云生图）与 `v2SubmitTask`（设备任务），属不同 API 流，合并臃肿。

**拆分**：
- `src/pages/create/useCreateShared.ts`（143 行）：composable 抽两页共享的设备加载、任务轮询、SVG 预览弹窗、删除/清空任务逻辑。
- `src/pages/create/ai-draw.vue`（322 行）：文生图/图生图子模式 + `generateImage` + 发送到设备。两子模式保留（同属云生图 API 流）。
- `src/pages/create/image-draw.vue`（264 行）：图片绘画（`v2SubmitTask` draw_generated + `DrawParamsPanel` + `ImagePicker` 必填 + 任务轮询含进度条/状态/删除）。
- `src/pages/create/create-shared.scss`（428 行）：原 create.vue 的 `<style scoped>` 整体抽出，两页 `<style scoped>@import './create-shared.scss';</style>` 引用，避免样式重复。
- 删 `src/pages/create/create.vue`（937 行）。
- `src/pages/index/index.vue`：`goDraw` / `goImageDraw` 改跳 `/pages/create/ai-draw` 与 `/pages/create/image-draw`，去掉 `?mode=` 参数。
- `src/pages.json`：删 `pages/create/create`，加 `pages/create/ai-draw` + `pages/create/image-draw`（标题「AI 生图」「图片绘画」）。

**导航接入**：保持「智能体页跳转」不变——index 智能体页两个卡片分别 `navigateTo` 两新页，tabBar 不变。

**提交**：`refactor(miniprogram): split create.vue into ai-draw + image-draw (P2-1/M2)` — 子模块 `9110792`

### M3 — mine 转 pure 账号页 + index 去重（深度重构核心）

**问题**：mine 418 行，3 个统计卡（设备/在线/任务）与 index Hero 设备卡数据重复；mine「设备管理」「设备配网」菜单跳底栏已有的 tab（冗余跳转，多 1 步无意义）。

**mine.vue**（418→305 行，-113）转纯账号/菜单页：
- 删设备/在线/任务 3 个统计卡 + 对应 `loadData`/`onlineCount`/`taskCount`/`v2GetDevices`/`v2ListTasks` 数据获取。
- 删「设备管理」「设备配网」两菜单项（底栏 tab 已直达）。
- 保留账户卡、数字人、设置、关于、登出。
- 新增「声纹」入口（`navigateTo /pages/voiceprint/index`）。
- 统计卡样式整段删除（与 StatPill 微差，整段删干净优于勉强复用组件）。

**index.vue**（601→604）：Hero sub-item「设备 X 台」改为「在线 X / 总 Y 台」（吸收 mine 删掉的在线数统计），新增 `onlineCount` computed。不加独立 StatPill 统计行（与 Hero sub 重复）。

**i18n**：zh_CN/en.ts 新增 `mine.voiceprint` / `mine.voiceprintDesc` 双语。遗留 `mine.devices/online/tasks/deviceMgmt/deviceConfig` 等 key 暂不删（保守防他处引用，仅 mine 曾使用，删除风险低但本轮保守留作 dead key）。

**提交**：`refactor(miniprogram): mine to account-only, dedupe stats to index (P2-1/M3)` — 子模块 `c78edc1`

### M4 — 全量验收 + 文档同步

- `npx vue-tsc --noEmit`：0 errors（M1/M2/M3 各里程碑后均验证通过）。
- `npx uni build --platform mp-weixin`：编译验证（M4 末尾执行）。
- 真机回归：5 个 tab 页 + 2 个新 create 页可达即视为通过；端到端物理任务留 BACKLOG-P0-3 单独验证。
- 文档：本设计文档（中文）+ `progress.md`（执行日志）+ `findings.md`（审查「settings 杂物」「chat 重叠」被证伪的纠偏记录）。
- 不做微信上传/审核（BACKLOG-P0-4 单独触发）。

---

## 三、不改动项

- tabBar 5 项结构不变（device-list 首页 / index 智能体 / device-config 配网 / settings 系统 / mine 我的）。
- 后端 API、device-config、chat、v2/device-detail、voice-command 组件均不动。
- i18n 全语种同步仅 zh/en，其余 5 语（de/pt_BR/vi/zh_TW）延后由用户按需补。
- 不做小程序上传/审核提交。

---

## 四、风险与缓解

| 风险 | 缓解 |
|---|---|
| create 拆页后旧 URL `/pages/create/create` 失效 | 已改 index.goDraw/goImageDraw，无外部 deep link 依赖旧 URL |
| 抽组件引入样式回归 | M1 纯提取零行为变化先行，回归通过后再进 M2/M3 |
| mine 内容大改影响用户习惯 | 保留账户卡+数字人+设置+关于+登出+新增声纹入口，只去重不删功能点 |
| i18n 5 语种未同步 | zh/en 已补，其余延后非阻塞 |

---

## 五、验收总表

| 项 | 结果 |
|---|---|
| `npx vue-tsc --noEmit` | 0 errors ✅ |
| `npx uni build --platform mp-weixin` | 编译通过 ✅ |
| create.vue 行数 | 937 → ai-draw 322 + image-draw 264（拆页） ✅ |
| settings/index.vue 行数 | 744 → 655（-89） ✅ |
| mine.vue 行数 | 418 → 305（-113） ✅ |
| index.vue 行数 | 601 → 604（+3 在线计数） ✅ |
| 设计文档（中文） | 本文件 ✅ |
| progress.md 同步 | ✅ |
| findings.md 审查纠偏记录 | ✅ |