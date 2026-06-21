# 小智 / LiMa manager-mobile 小程序深度优化设计

## 1. 项目现状

- **技术栈**：uni-app v3 + Vue 3 + Vite，目标平台 mp-weixin / H5 / App。
- **源码规模**：`src` 下约 15 900 行 Vue/TS，多个文件超过项目 300 行/函数 50 行约束。
- **构建产物**：`dist/build/mp-weixin` 约 **2.6 MB**；其中 JS 总计约 **650 KB**（`common/vendor.js` 195 KB + i18n 170 KB + 页面逻辑），静态资源约 **1.7 MB**。
- **包结构**：`src/pages-sub` 为空，所有非 tab 页面仍在主包；`vite.config.ts` 已开启分包入口但未实际使用。
- **运行时瓶颈**：
  - 每次网络请求都同步读取 `uni.getStorageSync('token')` 并 `JSON.parse`（`src/http/request/alova.ts`）。
  - 6 个语言包全部同步打包进主包，启动即加载约 170 KB。
  - 多处 `v-for` 使用 `index` 作为 key，聊天流式输出时整列表重绘。
  - `mine.vue` 对每台设备串行拉取任务，`onShow` 频繁触发。
  - Pinia persistedstate 使用同步 storage，且 `lang.ts` 重复手动写入同一 key。
- **构建/依赖**：
  - `dist` 中残留已删除页面（`pages/agent`、`pages/login/index`、`pages/register`、`pages/forgot-password` 等）。
  - `wot-design-uni` 全量复制到产物，未使用组件也被打包。
  - 存在未使用依赖：`@tanstack/vue-query`、`z-paging`、`js-cookie`；`dayjs` 只在构建时用于注入 BUILD_TIME。
  - `App.vue` 全局引入 `abortcontroller-polyfill`，现代环境已原生支持。
  - 大量 `console.log` 残留，生产构建依赖 `VITE_DELETE_CONSOLE` 环境变量。

## 2. 优化目标

1. **降低首包体积**：主包 JS 从 ~650 KB 降至 ~300–400 KB；构建产物总大小明显下降。
2. **提升运行时性能**：减少同步 storage 调用、避免列表全量重绘、减少不必要的网络请求。
3. **提升可维护性**：拆分超大文件/函数，统一 i18n，移除死代码与未使用依赖。
4. **符合项目规约**：单文件 ≤300 行、单函数 ≤50 行；无 `except Exception: pass` 式静默吞异常。

## 3. 方案对比

| 方案 | 描述 | 优点 | 缺点 | 推荐度 |
|---|---|---|---|---|
| A. 仅做运行时小修 | 清理日志、缓存 token、换 key、并行请求 | 风险极低，改动少 | 不能解决包体积与文件过大的根本问题 | 低 |
| B. 仅做架构重构 | 拆分文件、分包、组件化 | 长期可维护性好 | 工作量大、验证周期长、无法快速看到体积收益 | 中 |
| **C. 速赢 + 重构分阶段** | 先做低风险、高影响的体积/性能速赢；再拆分文件与重构交互 | 见效快、风险可控、逐步交付 | 需要分两次验收 | **高** |

**推荐方案 C**：先速赢释放首包体积与运行性能，再对复杂页面做结构性拆分。

## 4. 详细设计

### 阶段一：速赢（低风险、高影响）

#### 4.1 清理陈旧构建产物
- 删除 `dist/build/mp-weixin` 后重新构建，避免残留已删除页面。
- 在 CI/部署脚本中执行清理后构建；建议将 `dist/` 加入 `.gitignore` 或不再提交构建产物。

#### 4.2 语言包懒加载
- 文件：`src/i18n/index.ts`
- 实现：改为 `const loaders = { zh_CN: () => import('./zh_CN'), ... }`，启动仅加载默认语言，切换时异步加载。
- 预期：首包减少 ~140 KB。

#### 4.3 按需引入组件库
- 文件：`src/pages.json` / `pages.config.ts` / `vite.config.ts`
- 实现：
  - 在 `easycom` 中精确配置实际使用的 `wd-*` 组件白名单，避免 `wot-design-uni` 全量复制。
  - 或在 `Components` 插件中使用 `globs: ['src/components/**']` 并关闭对 `wot-design-uni` 的自动全量扫描。
- 预期：减少 50–100 KB。

#### 4.4 认证信息内存缓存
- 文件：`src/http/request/alova.ts`
- 实现：
  - 启动时读取一次 `token`、`app_language` 到内存变量。
  - 登录、退出、切换语言时同步更新内存与 storage。
  - `beforeRequest` 中直接读取内存变量。
- 预期：消除每次请求的同步 storage 与 JSON.parse 开销。

#### 4.5 baseURL / 运行环境缓存
- 文件：`src/utils/index.ts`
- 实现：缓存 `getEnvBaseUrl()` / `getEnvBaseUploadUrl()` 的结果，因为小程序环境版本在运行期间不变；`getAccountInfoSync` 与 storage override 只解析一次。

#### 4.6 移除/条件化全局 polyfill
- 文件：`src/App.vue`
- 实现：移除 `import 'abortcontroller-polyfill/...'`；若必须兼容旧基础库，改为 `typeof AbortController === 'undefined'` 时动态引入。

#### 4.7 清理调试日志
- 文件：`src/http/request/alova.ts`、`src/utils/uploadFile.ts`、`src/pages/settings/index.vue` 等
- 实现：删除非必要 `console.log`；将 `vite.config.ts` 的 `esbuild.drop` 默认设为 `['console', 'debugger']`（或至少生产环境无条件 drop console）。

#### 4.8 `v-for` 使用业务 key
- 文件：
  - `src/pages/chat/chat.vue`
  - `src/pages/chat-history/detail.vue`
  - `src/pages/v2/device-detail/index.vue`
- 实现：使用消息 ID / 日志内容签名 + index 作为 key；无 ID 时生成 `id + content-hash`。

#### 4.9 并行化 mine 页请求
- 文件：`src/pages/mine/mine.vue`
- 实现：
  - `v2GetDevices` 后用 `Promise.all` 并行拉取各设备任务，并加 10s 超时。
  - 增加内存缓存 + TTL（如 10s），避免每次 `onShow` 重复请求。

#### 4.10 卸载未使用依赖
- 文件：`package.json`
- 操作：移除 `@tanstack/vue-query`、`z-paging`、`js-cookie`。
- `dayjs` 若仅用于 `vite.config.ts` 的 BUILD_TIME，可用原生 `Date` 替换；若运行时未使用则一并移除。

#### 4.11 Pinia 持久化去重
- 文件：`src/store/lang.ts`
- 实现：移除手动 `uni.setStorageSync('app_language', lang)`，让 `pinia-plugin-persistedstate` 统一处理；或自定义异步 storage 适配器。

### 阶段二：代码质量与结构优化

#### 4.12 拆分 `src/utils/index.ts`
当前 403 行，职责混杂。拆分为：
- `utils/url.ts`：`currRoute`、`getUrlObj`、`getLastPage`、`getAllPages`、`needLoginPages`
- `utils/env.ts`：`getEnvBaseUrl`、`getEnvBaseUploadUrl`、`buildEdgeAClientWsUrl`、运行时 override
- `utils/crypto.ts`：`generateSm2KeyPairHex`、`sm2Encrypt`、`sm2Decrypt`
- `utils/function.ts`：`debounce`、`deepClone`
- `utils/badge.ts`：`updateM6PendingTabBarBadge`、`applyM6PendingTabBarBadge`

#### 4.13 拆分超大页面与组件
- `src/pages/chat/chat.vue`（534 行）
  - `components/chat/ChatMessageList.vue`
  - `components/chat/ChatInputBar.vue`
  - `composables/useChatHistory.ts`
  - `composables/useChatStream.ts`
- `src/pages/voiceprint/index.vue`（695 行）
  - 拆分为录音、波形、上传、结果等子组件与 composables。
- `src/pages/settings/index.vue`（642 行）
  - 按功能拆分为设置项卡片、账号安全、语言切换等子组件。
- `src/pages/device-config/components/ultrasonic-config.vue`（685 行）、`wifi-selector.vue`（568 行）
  - 提取公共逻辑到 composables，拆分子步骤组件。

#### 4.14 聊天性能重构
- 为每条消息分配稳定 ID（时间戳 + 随机后缀），避免用 index 做 key。
- 流式响应时复用同一条消息对象引用，减少 Vue 响应式数组的替换开销。
- `markdownToHtml` 结果使用 `WeakMap` 缓存，避免同一内容反复解析。
- `scrollToBottom` 使用节流/防抖，避免每字滚动。
- 超长聊天记录启用窗口渲染或限制最大保留消息数（如 200 条），旧消息折叠/分页加载。

#### 4.15 App.vue tabBar 国际化
- 将 `updateTabBarText` 中的硬编码中文改为从 `i18n` 读取：
  - `t('tabbar.nebula')`、`t('tabbar.chat')`、`t('tabbar.create')`、`t('tabbar.mine')`。
- 更新所有语言包，补充 tabbar 相关键值。

#### 4.16 网络请求缓存
- 对设备列表、配置信息等低频变更接口增加 `cacheFor` 或内存缓存 + TTL（5–10s）。
- `v2GetDevices` 当前 `cacheFor: { expire: 0 }`，改为合理的 TTL 或聚合接口。

### 阶段三：分包与可选增强（视阶段一二结果决定）

#### 4.17 非 tab 页面分包
- 目录：`src/pages-sub`
- 迁移页面：
  - `pages/login/privacy-policy-*`、`pages/login/user-agreement-*`
  - `pages/chat/chat`、`pages/chat-history/*`
  - `pages/create/create`
  - `pages/voiceprint/index`
  - `pages/device-config/*`
  - `pages/settings/*`、`pages/settings/privacy-permissions`
  - `pages/v2/device-detail/index`、`pages/v2/login/index`
- 保留在主包：4 个 tabbar 页面 + `pages/mine/mine`。
- 配置：`vite.config.ts` 的 `subPackages` 与 `pages.config.ts` 的 `preloadRule`。
- 配合 `@uni-ku/bundle-optimizer` 开启 `async-import` 与 `async-component`（已启用）。

#### 4.18 静态资源压缩
- `src/static/images/home/main-top-bg.png`（978 KB）压缩或转为 WebP/JPEG。
- App icons 按平台需求尺寸提供，避免 1024×1024 等大图原样打进小程序包。
- tabbar 图标压缩；可考虑使用 iconfont/组件库图标替代部分 PNG。

#### 4.19 大列表虚拟滚动（可选）
- 对聊天记录、任务日志等超长列表，使用 `scroll-view` + 窗口渲染或分页加载，限制同时渲染节点数。

## 5. 预期收益

| 优化项 | 预期收益 |
|---|---|
| 清理 stale dist + 旧页面 | 主包减少 30–80 KB |
| i18n 懒加载 | 首包减少 ~140 KB |
| wot-design-uni 按需 | 减少 50–100 KB |
| 移除未使用依赖 | 减少 30–60 KB |
| 非 tab 页面分包 | 主包再减 80–150 KB |
| 同步 storage → 内存/异步 | 启动、路由切换、请求更顺滑 |
| 聊天性能重构 | 长对话滚动与流式输出更流畅 |

**保守目标**：首包 JS 从 ~650 KB 降至 ~300–400 KB；构建产物总大小明显下降；启动与 tab 切换流畅度改善。

## 6. 影响范围

- `esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/src/` 下多个文件。
- 新增 `src/pages-sub/` 及分包配置。
- `vite.config.ts`、`pages.config.ts`、`package.json`。
- 静态资源压缩替换（`src/static/images/home/main-top-bg.png`、icons、tabbar）。
- 不涉及 LiMa 后端服务接口变更。

## 7. 验证计划

1. **构建验证**
   - `pnpm install` 成功。
   - `pnpm build:mp-weixin` 成功，产物无残留旧页面。
   - `pnpm type-check && pnpm lint` 通过。
2. **包体积验证**
   - 对比优化前后 `dist/build/mp-weixin` 总大小、主包 JS 大小、`common/vendor.js` 大小。
3. **功能回归**
   - 登录 / 退出 / token 失效跳转。
   - 设备列表、设备详情、聊天、创作、配网、语音、设置、语言切换。
   - tabbar 文案随语言切换更新。
   - 分包页面能正常跳转与预加载。
4. **性能验证**
   - 真机/开发者工具启动时间、长聊天记录滚动帧率、mine 页切换网络请求数。

## 8. 实施顺序

1. 阶段一速赢（1–2 轮提交）：清理产物、依赖卸载、日志清理、token/lang 内存缓存、v-for key、mine 并行、polyfill 移除、Pinia 去重。
2. 阶段二结构优化（2–3 轮提交）：拆分 utils、拆分超大页面、聊天性能重构、tabBar i18n。
3. 阶段三分包与资源（1 轮提交）：迁移分包、压缩静态资源、可选虚拟滚动。

每个阶段完成后执行构建验证与功能回归，再进入下一阶段。
