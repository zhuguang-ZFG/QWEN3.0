# Manager-Mobile 小程序 Phase 1 速赢优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 通过低风险改动降低首包体积、减少同步 storage 调用、清理死代码，使 `manager-mobile` 的构建与运行时性能明显改善。

**Architecture:** 以“构建产物清理 → 依赖瘦身 → 运行时缓存 → 列表 key 优化 → 网络请求并行化 → i18n 懒加载 → 构建白名单”为顺序推进；每个任务独立可测，全部完成后统一构建与回归。

**Tech Stack:** uni-app v3 + Vue 3 + Vite + TypeScript + pnpm + alova + pinia + wot-design-uni

---

## 文件结构变更

| 文件/目录 | 动作 | 职责 |
|---|---|---|
| `.gitignore` | 修改 | 忽略 `dist/` 构建产物 |
| `package.json` | 修改 | 移除未使用依赖、移除 `dayjs` |
| `pnpm-lock.yaml` | 修改 | 由 `pnpm install` 自动更新 |
| `src/main.ts` | 修改 | 移除 `@tanstack/vue-query` 插件注册 |
| `src/App.vue` | 修改 | 移除 `abortcontroller-polyfill` 全局引入 |
| `vite.config.ts` | 修改 | `dayjs` 替换为原生 Date；生产环境默认 drop console |
| `pages.config.ts` | 修改 | `wot-design-uni` 白名单 easycom；移除 `z-paging` |
| `src/http/request/alova.ts` | 修改 | 清理调试日志；使用内存缓存的 token/language |
| `src/utils/authCache.ts` | 新建 | 内存缓存 token 与当前语言 |
| `src/utils/index.ts` | 修改 | 缓存 `getEnvBaseUrl` / `getEnvBaseUploadUrl` 结果 |
| `src/store/index.ts` | 修改 | persistedstate 写入改为异步 storage |
| `src/store/lang.ts` | 修改 | 移除重复手动 storage 写入；同步语言缓存 |
| `src/store/user.ts` | 修改 | 退出登录时清空 token 内存缓存 |
| `src/pages/v2/login/index.vue` | 修改 | 登录成功后同步 token 内存缓存 |
| `src/pages/chat/chat.vue` | 修改 | 消息使用业务 key；滚动定位使用消息 id |
| `src/pages/chat-history/detail.vue` | 修改 | 消息/内容列表使用组合 key |
| `src/pages/v2/device-detail/index.vue` | 修改 | 日志列表使用组合 key |
| `src/pages/mine/mine.vue` | 修改 | 设备任务请求并行化 + 10s 内存缓存 |
| `src/i18n/index.ts` | 修改 | 默认中文同步加载，其他语言懒加载 |

---

### Task 1: 清理陈旧构建产物

**Files:**
- Modify: `.gitignore`
- Delete: `dist/build/mp-weixin`, `dist/dev/mp-weixin`

- [ ] **Step 1: 将 `dist` 加入 `.gitignore`**

```text
# 构建产物
dist
```

- [ ] **Step 2: 删除本地陈旧产物**

Run:
```bash
cd "D:/QWEN3.0/esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile"
rm -rf dist/build/mp-weixin dist/dev/mp-weixin
```

- [ ] **Step 3: 重新构建微信小程序产物**

Run:
```bash
pnpm install
pnpm build:mp-weixin
```

Expected: `dist/build/mp-weixin` 重新生成；`app.json` 的 `pages` 中不应再出现 `pages/agent`、`pages/login/index`、`pages/register`、`pages/forgot-password`。

- [ ] **Step 4: 提交变更**

```bash
git add .gitignore package.json pnpm-lock.yaml
# dist 已加入 .gitignore，无需 add dist
git commit -m "chore(manager-mobile): ignore and clean stale dist artifacts"
```

---

### Task 2: 移除未使用依赖

**Files:**
- Modify: `package.json`
- Modify: `src/main.ts`
- Modify: `pages.config.ts`

- [ ] **Step 1: 从 `package.json` 删除依赖**

移除以下三项：
- `@tanstack/vue-query`
- `js-cookie`
- `z-paging`

```json
// 删除前片段示例（不要保留）
"@tanstack/vue-query": "^5.62.16",
"js-cookie": "^3.0.5",
"z-paging": "2.8.7"
```

- [ ] **Step 2: 修改 `src/main.ts`**

```ts
import { createSSRApp } from 'vue'
import App from './App.vue'
import { routeInterceptor } from './router/interceptor'

import store from './store'
import '@/style/index.scss'
import 'virtual:uno.css'

// 导入国际化相关功能
import { initI18n } from './i18n'
import { useLangStore } from './store/lang'

export function createApp() {
  const app = createSSRApp(App)
  app.use(store)
  app.use(routeInterceptor)

  // 初始化国际化
  initI18n()

  return {
    app,
  }
}
```

- [ ] **Step 3: 修改 `pages.config.ts`**

```ts
import { defineUniPages } from '@uni-helper/vite-plugin-uni-pages'
import { tabBar } from './src/layouts/fg-tabbar/tabbarList'

export default defineUniPages({
  globalStyle: {
    navigationStyle: 'default',
    navigationBarTitleText: '小智',
    navigationBarBackgroundColor: '#f8f8f8',
    navigationBarTextStyle: 'black',
    backgroundColor: '#FFFFFF',
  },
  easycom: {
    autoscan: true,
    custom: {
      '^fg-(.*)': '@/components/fg-$1/fg-$1.vue',
      '^wd-(.*)': 'wot-design-uni/components/wd-$1/wd-$1.vue',
    },
  },
  tabBar: tabBar as any,
})
```

- [ ] **Step 4: 安装并验证**

Run:
```bash
pnpm install
pnpm type-check
pnpm build:mp-weixin
```

Expected: 无 `@tanstack/vue-query` / `js-cookie` / `z-paging` 相关残留；构建成功。

- [ ] **Step 5: 提交**

```bash
git add package.json pnpm-lock.yaml src/main.ts pages.config.ts
git commit -m "chore(manager-mobile): remove unused deps vue-query js-cookie z-paging"
```

---

### Task 3: 移除全局 polyfill 并将 `dayjs` 替换为原生 Date

**Files:**
- Modify: `src/App.vue`
- Modify: `vite.config.ts`
- Modify: `package.json`

- [ ] **Step 1: 修改 `src/App.vue`**

删除第 9 行：

```ts
import 'abortcontroller-polyfill/dist/abortcontroller-polyfill-only'
```

保留其余逻辑。

- [ ] **Step 2: 修改 `vite.config.ts`**

删除 `import dayjs from 'dayjs'`。

将 html-transform 插件替换为：

```ts
UNI_PLATFORM === 'h5' && {
  name: 'html-transform',
  transformIndexHtml(html) {
    const now = new Date()
    const pad = (n: number) => String(n).padStart(2, '0')
    const buildTime = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
    return html.replace('%BUILD_TIME%', buildTime)
  },
}
```

- [ ] **Step 3: 从 `package.json` 移除 `dayjs`**

```json
// 删除
"dayjs": "1.11.10",
```

- [ ] **Step 4: 安装并验证**

Run:
```bash
pnpm install
pnpm build:mp-weixin
pnpm build:h5
```

Expected: 两处构建均成功；H5 产物 HTML 中 `%BUILD_TIME%` 被替换为 `YYYY-MM-DD HH:mm:ss`。

- [ ] **Step 5: 提交**

```bash
git add src/App.vue vite.config.ts package.json pnpm-lock.yaml
git commit -m "chore(manager-mobile): drop abortcontroller-polyfill and dayjs"
```

---

### Task 4: 清理 alova 调试日志并默认生产环境 drop console

**Files:**
- Modify: `src/http/request/alova.ts`
- Modify: `vite.config.ts`

- [ ] **Step 1: 修改 `src/http/request/alova.ts`**

删除以下调试输出：

```ts
console.log('ignoreAuth===>', ignoreAuth)
```

```ts
console.log('当前域名', method.baseURL)
```

```ts
console.log(response)
```

保留业务错误 toast，将：

```ts
console.error('errorMessage===>', errorMessage)
toast.error(errorMessage)
```

改为仅：

```ts
toast.error(errorMessage)
```

- [ ] **Step 2: 修改 `vite.config.ts` 的 esbuild 配置**

```ts
esbuild: {
  drop: mode === 'production' || VITE_DELETE_CONSOLE === 'true'
    ? ['console', 'debugger']
    : ['debugger'],
}
```

- [ ] **Step 3: 验证**

Run:
```bash
pnpm build:mp-weixin
```

Expected: 构建成功；`dist/build/mp-weixin/common/vendor.js` 中不再出现上述 `console.log` 字符串。

- [ ] **Step 4: 提交**

```bash
git add src/http/request/alova.ts vite.config.ts
git commit -m "chore(manager-mobile): clean alova logs and drop console in production"
```

---

### Task 5: 建立 token / language 内存缓存

**Files:**
- Create: `src/utils/authCache.ts`
- Modify: `src/http/request/alova.ts`
- Modify: `src/pages/v2/login/index.vue`
- Modify: `src/store/user.ts`
- Modify: `src/store/lang.ts`

- [ ] **Step 1: 创建 `src/utils/authCache.ts`**

```ts
import type { Language } from '@/store/lang'

const langMap: Record<Language, string> = {
  zh_CN: 'zh-CN',
  en: 'en-US',
  zh_TW: 'zh-TW',
  de: 'de',
  vi: 'vi',
  pt_BR: 'pt-BR',
}

function parseToken(raw: string | null): { token?: string } | null {
  if (!raw)
    return null
  try {
    return JSON.parse(raw) as { token?: string }
  }
  catch {
    return { token: raw }
  }
}

let cachedTokenRaw: string | null = uni.getStorageSync('token') || null
let cachedAuthInfo: { token?: string } | null = parseToken(cachedTokenRaw)
let cachedLanguage: string = langMap[uni.getStorageSync('app_language') as Language || 'zh_CN']

export function getCachedAuthInfo(): { token?: string } | null {
  return cachedAuthInfo
}

export function setCachedToken(raw: string | null) {
  cachedTokenRaw = raw
  cachedAuthInfo = parseToken(raw)
}

export function clearCachedToken() {
  cachedTokenRaw = null
  cachedAuthInfo = null
}

export function getCachedLanguage(): string {
  return cachedLanguage
}

export function setCachedLanguage(lang: Language) {
  cachedLanguage = langMap[lang] || langMap.zh_CN
}
```

- [ ] **Step 2: 修改 `src/http/request/alova.ts`**

删除本地的 `langMap`。在文件顶部引入：

```ts
import { getCachedAuthInfo, getCachedLanguage, setCachedToken } from '@/utils/authCache'
```

在 `beforeRequest` 的认证段中，替换原来的 token 读取逻辑为：

```ts
if (!ignoreAuth) {
  const authInfo = getCachedAuthInfo()
  if (!authInfo?.token) {
    uni.reLaunch({ url: '/pages/v2/login/index' })
    throw new Error('[请求错误]：未登录')
  }
  method.config.headers.Authorization = `Bearer ${authInfo.token}`
}
```

在语言头设置处，替换为：

```ts
'Accept-language': getCachedLanguage(),
```

保留刷新 token 失败时的重定向逻辑，但可在失败处理器中调用 `clearCachedToken()`（可选，本次不强制）。

- [ ] **Step 3: 修改 `src/pages/v2/login/index.vue`**

登录成功后同步内存缓存：

```ts
import { setCachedToken } from '@/utils/authCache'

// 在 handleLogin 中，setStorageSync 之后添加：
uni.setStorageSync('token', JSON.stringify({ token: data.token, expire: data.expiresIn }))
setCachedToken(JSON.stringify({ token: data.token, expire: data.expiresIn }))
```

- [ ] **Step 4: 修改 `src/store/user.ts`**

```ts
import { clearCachedToken } from '@/utils/authCache'

const removeUserInfo = () => {
  userInfo.value = { ...userInfoState }
  uni.removeStorageSync('userInfo')
  uni.removeStorageSync('token')
  clearCachedToken()
}
```

- [ ] **Step 5: 修改 `src/store/lang.ts`**

```ts
import { setCachedLanguage } from '@/utils/authCache'

const changeLang = (lang: Language) => {
  currentLang.value = lang
  setCachedLanguage(lang)
  uni.setStorageSync('app_language', lang)
}
```

- [ ] **Step 6: 验证**

Run:
```bash
pnpm type-check
pnpm build:mp-weixin
```

Expected: 无类型错误；登录后请求正常携带 `Authorization`；切换语言后请求头 `Accept-language` 同步变化。

- [ ] **Step 7: 提交**

```bash
git add src/utils/authCache.ts src/http/request/alova.ts src/pages/v2/login/index.vue src/store/user.ts src/store/lang.ts
git commit -m "perf(manager-mobile): cache token and language in memory"
```

---

### Task 6: 移除重复 language storage 并让 Pinia 持久化写入异步化

**Files:**
- Modify: `src/store/lang.ts`
- Modify: `src/store/index.ts`

- [ ] **Step 1: 修改 `src/store/lang.ts`**

`changeLang` 中仅保留：

```ts
const changeLang = (lang: Language) => {
  currentLang.value = lang
  setCachedLanguage(lang)
}
```

`pinia-plugin-persistedstate` 会自动写入 storage。

- [ ] **Step 2: 修改 `src/store/index.ts`**

```ts
import { createPinia } from 'pinia'
import { createPersistedState } from 'pinia-plugin-persistedstate'

const store = createPinia()
store.use(
  createPersistedState({
    storage: {
      getItem: uni.getStorageSync,
      setItem: (key, value) => {
        uni.setStorage({ key, data: value })
      },
      removeItem: (key) => {
        uni.removeStorage({ key })
      },
    },
  }),
)

export default store

export * from './config'
export * from './user'
```

- [ ] **Step 3: 验证**

Run:
```bash
pnpm type-check
pnpm build:mp-weixin
```

Expected: 类型检查通过；切换语言后 storage 仍保存最新值，且不再重复写入。

- [ ] **Step 4: 提交**

```bash
git add src/store/lang.ts src/store/index.ts
git commit -m "perf(manager-mobile): dedupe lang storage and async pinia persist writes"
```

---

### Task 7: 缓存 baseURL / 上传 URL / 微信小程序环境版本

**Files:**
- Modify: `src/utils/index.ts`

- [ ] **Step 1: 在 `src/utils/index.ts` 顶部添加缓存变量**

```ts
import { isMpWeixin } from './platform'

function getWeixinEnvVersion(): string | undefined {
  if (!isMpWeixin)
    return undefined
  try {
    return uni.getAccountInfoSync().miniProgram.envVersion
  }
  catch {
    return undefined
  }
}

const cachedWxEnvVersion = getWeixinEnvVersion()
let cachedBaseUrl: string | null = null
let cachedUploadUrl: string | null = null
```

- [ ] **Step 2: 修改 `getEnvBaseUrl`**

```ts
export function getEnvBaseUrl() {
  if (cachedBaseUrl !== null)
    return cachedBaseUrl

  const override = getServerBaseUrlOverride()
  if (override) {
    cachedBaseUrl = override
    return cachedBaseUrl
  }

  let baseUrl = import.meta.env.VITE_SERVER_BASEURL
  const VITE_SERVER_BASEURL__WEIXIN_DEVELOP = 'https://chat.donglicao.com'
  const VITE_SERVER_BASEURL__WEIXIN_TRIAL = 'https://chat.donglicao.com'
  const VITE_SERVER_BASEURL__WEIXIN_RELEASE = 'https://chat.donglicao.com'

  if (isMpWeixin) {
    switch (cachedWxEnvVersion) {
      case 'develop':
        baseUrl = VITE_SERVER_BASEURL__WEIXIN_DEVELOP || baseUrl
        break
      case 'trial':
        baseUrl = VITE_SERVER_BASEURL__WEIXIN_TRIAL || baseUrl
        break
      case 'release':
        baseUrl = VITE_SERVER_BASEURL__WEIXIN_RELEASE || baseUrl
        break
    }
  }

  cachedBaseUrl = baseUrl
  return baseUrl
}
```

- [ ] **Step 3: 修改 `getEnvBaseUploadUrl`**

```ts
export function getEnvBaseUploadUrl() {
  if (cachedUploadUrl !== null)
    return cachedUploadUrl

  let baseUploadUrl = import.meta.env.VITE_UPLOAD_BASEURL
  const VITE_UPLOAD_BASEURL__WEIXIN_DEVELOP = 'https://chat.donglicao.com/upload'
  const VITE_UPLOAD_BASEURL__WEIXIN_TRIAL = 'https://chat.donglicao.com/upload'
  const VITE_UPLOAD_BASEURL__WEIXIN_RELEASE = 'https://chat.donglicao.com/upload'

  if (isMpWeixin) {
    switch (cachedWxEnvVersion) {
      case 'develop':
        baseUploadUrl = VITE_UPLOAD_BASEURL__WEIXIN_DEVELOP || baseUploadUrl
        break
      case 'trial':
        baseUploadUrl = VITE_UPLOAD_BASEURL__WEIXIN_TRIAL || baseUploadUrl
        break
      case 'release':
        baseUploadUrl = VITE_UPLOAD_BASEURL__WEIXIN_RELEASE || baseUploadUrl
        break
    }
  }

  cachedUploadUrl = baseUploadUrl
  return baseUploadUrl
}
```

- [ ] **Step 4: 验证**

Run:
```bash
pnpm type-check
pnpm build:mp-weixin
```

Expected: 类型检查通过；请求 baseURL 与首次一致。

- [ ] **Step 5: 提交**

```bash
git add src/utils/index.ts
git commit -m "perf(manager-mobile): cache baseURL and upload URL"
```

---

### Task 8: 给列表 `v-for` 换上业务 key

**Files:**
- Modify: `src/pages/chat/chat.vue`
- Modify: `src/pages/chat-history/detail.vue`
- Modify: `src/pages/v2/device-detail/index.vue`

- [ ] **Step 1: 修改 `src/pages/chat/chat.vue`**

为 `DisplayMessage` 增加 `id` 字段：

```ts
interface DisplayMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  time: string
  streaming?: boolean
}

function generateMessageId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}
```

所有创建消息的地方补充 `id`：

```ts
messages.value.push({
  id: generateMessageId(),
  role: 'user',
  content: text,
  time: formatTime(new Date()),
})
```

```ts
messages.value.push({
  id: generateMessageId(),
  role: 'assistant',
  content: '',
  time: formatTime(new Date()),
  streaming: true,
})
```

欢迎消息：

```ts
messages.value.push({
  id: generateMessageId(),
  role: 'assistant',
  content: t('chat.welcome'),
  time: formatTime(new Date()),
})
```

模板中使用业务 key 和基于 id 的滚动锚点：

```vue
<scroll-view
  class="chat-scroll"
  scroll-y
  :scroll-into-view="scrollToView"
  scroll-with-animation
  :scroll-animation-duration="200"
>
  <view class="chat-list">
    <view
      v-for="(msg) in messages"
      :id="`msg-${msg.id}`"
      :key="msg.id"
      class="msg-row"
      :class="msg.role"
      @longpress="onLongPressMessage(msg, messages.indexOf(msg))"
    >
      ...
    </view>
  </view>
  <view style="height: 40rpx;" />
</scroll-view>
```

`scrollToBottom` 改为：

```ts
function scrollToBottom() {
  nextTick(() => {
    const last = messages.value[messages.value.length - 1]
    if (!last) return
    const id = `msg-${last.id}`
    scrollToView.value = id
    setTimeout(() => {
      scrollToView.value = ''
      nextTick(() => {
        scrollToView.value = id
      })
    }, 50)
  })
}
```

- [ ] **Step 2: 修改 `src/pages/chat-history/detail.vue`**

外层消息 key：

```vue
<view
  v-for="(message, index) in messageList"
  :id="`message-${index}`"
  :key="`${message.createdAt}-${message.chatType}-${index}`"
  class="w-full flex"
  ...
>
```

内层内容 key：

```vue
<div
  v-for="(item, idx) in extractContentFromString(message.content)"
  :key="`${item.type}-${idx}-${item.text?.slice(0, 20)}`"
>
```

- [ ] **Step 3: 修改 `src/pages/v2/device-detail/index.vue`**

```vue
<wd-text
  v-for="(l, i) in logLines"
  :key="`${l}-${i}`"
  :text="l"
  size="20rpx"
  color="#666"
  custom-class="!leading-[36rpx]"
/>
```

- [ ] **Step 4: 验证**

Run:
```bash
pnpm type-check
pnpm build:mp-weixin
```

Expected: 无类型错误；构建成功。

- [ ] **Step 5: 提交**

```bash
git add src/pages/chat/chat.vue src/pages/chat-history/detail.vue src/pages/v2/device-detail/index.vue
git commit -m "perf(manager-mobile): use business keys for list rendering"
```

---

### Task 9: 并行化 Mine 页请求并加内存缓存

**Files:**
- Modify: `src/pages/mine/mine.vue`

- [ ] **Step 1: 在 `<script>` 顶部添加缓存变量**

```ts
import type { V2DeviceInfo } from '@/api/v2/types'

let deviceCache: { devices: V2DeviceInfo[]; ts: number } | null = null
const DEVICE_CACHE_TTL = 10_000
```

- [ ] **Step 2: 重写 `loadData` 函数**

```ts
async function loadData() {
  loading.value = true
  try {
    let rows: V2DeviceInfo[] = []

    if (deviceCache && Date.now() - deviceCache.ts < DEVICE_CACHE_TTL) {
      rows = deviceCache.devices
    }
    else {
      const res = await v2GetDevices()
      rows = res.rows || []
      deviceCache = { devices: rows, ts: Date.now() }
    }

    devices.value = rows
    onlineCount.value = rows.filter(d => d.status === 'online').length

    const taskResults = await Promise.all(
      rows.map(d =>
        v2ListTasks(d.deviceId, 'running', 100).catch(() => ({ count: 0 })),
      ),
    )
    taskCount.value = taskResults.reduce((sum, r) => sum + (r.count || 0), 0)
  }
  catch (e) {
    console.error(e)
  }
  finally {
    loading.value = false
  }
}
```

- [ ] **Step 3: 验证**

Run:
```bash
pnpm type-check
pnpm build:mp-weixin
```

Expected: 类型检查通过；Mine 页 `onShow` 在 10s 内不再重复请求设备列表；多设备任务请求并行发送。

- [ ] **Step 4: 提交**

```bash
git add src/pages/mine/mine.vue
git commit -m "perf(manager-mobile): parallelize mine tasks and cache device list"
```

---

### Task 10: i18n 语言包懒加载

**Files:**
- Modify: `src/i18n/index.ts`

- [ ] **Step 1: 重写 `src/i18n/index.ts`**

```ts
import { ref } from 'vue'
import { useLangStore } from '@/store/lang'
import type { Language } from '@/store/lang'
import zh_CN from './zh_CN'

const loaders: Record<Language, () => Promise<Record<string, string>>> = {
  zh_CN: () => Promise.resolve(zh_CN),
  en: () => import('./en').then(m => m.default),
  zh_TW: () => import('./zh_TW').then(m => m.default),
  de: () => import('./de').then(m => m.default),
  vi: () => import('./vi').then(m => m.default),
  pt_BR: () => import('./pt_BR').then(m => m.default),
}

const messages: Partial<Record<Language, Record<string, string>>> = {
  zh_CN,
}

const currentLang = ref<Language>('zh_CN')
let loadingLang: Language | null = null

async function loadLanguage(lang: Language) {
  if (messages[lang] || loadingLang === lang)
    return
  loadingLang = lang
  try {
    messages[lang] = await loaders[lang]()
  }
  finally {
    loadingLang = null
  }
}

export async function initI18n() {
  const langStore = useLangStore()
  currentLang.value = langStore.currentLang
  if (currentLang.value !== 'zh_CN')
    await loadLanguage(currentLang.value)
}

export async function changeLanguage(lang: Language) {
  await loadLanguage(lang)
  currentLang.value = lang
  const langStore = useLangStore()
  langStore.changeLang(lang)
}

export function t(key: string, params?: Record<string, string | number>): string {
  const langMessages = messages[currentLang.value] || messages.zh_CN

  if (langMessages && typeof langMessages === 'object' && key in langMessages) {
    let value = langMessages[key]
    if (typeof value === 'string') {
      if (params) {
        let result = value
        Object.entries(params).forEach(([paramKey, paramValue]) => {
          const regex = new RegExp(`\\{${paramKey}\\}`, 'g')
          result = result.replace(regex, String(paramValue))
        })
        return result
      }
      return value
    }
  }

  return key
}

export function getCurrentLanguage(): Language {
  return currentLang.value
}

export function getSupportedLanguages(): { code: Language, name: string }[] {
  return [
    { code: 'zh_CN', name: '简体中文' },
    { code: 'en', name: 'English' },
    { code: 'zh_TW', name: '繁體中文' },
    { code: 'de', name: 'Deutsch' },
    { code: 'vi', name: 'Tiếng Việt' },
    { code: 'pt_BR', name: 'Português (Brasil)' },
  ]
}
```

- [ ] **Step 2: 在 `src/main.ts` 中调用 `initI18n`**

保持 `createApp` 同步，启动时异步加载非默认语言：

```ts
export function createApp() {
  const app = createSSRApp(App)
  app.use(store)
  app.use(routeInterceptor)

  initI18n()

  return { app }
}
```

- [ ] **Step 3: 修改 `src/pages/settings/index.vue` 的语言切换处理**

将 `handleLanguageChange` 改为异步并等待语言包加载：

```ts
async function handleLanguageChange(lang: Language) {
  await changeLanguage(lang)
  showLanguageSheet.value = false
  currentLanguage.value = lang
  toast.success(t('settings.languageChanged'))
  updateTabBarText()
}
```

> 若 `updateTabBarText` 在 settings 页未定义，则只保留前三行；Phase 2 会统一处理 tabBar 国际化。

- [ ] **Step 4: 验证**

Run:
```bash
pnpm type-check
pnpm build:mp-weixin
```

Expected: 默认中文正常显示；切换英文/繁体等语言后界面更新；`dist/build/mp-weixin/i18n/` 下只生成默认语言对应的 js（若构建产物仍全部生成，检查是否其他文件同步 import 了语言包）。

- [ ] **Step 5: 提交**

```bash
git add src/i18n/index.ts src/main.ts
# 如有 settings 等调用方修改也一并 add
git commit -m "perf(manager-mobile): lazy-load i18n language packs"
```

---

### Task 11: `wot-design-uni` 组件白名单

**Files:**
- Modify: `pages.config.ts`

- [ ] **Step 1: 修改 `pages.config.ts` 的 easycom**

```ts
import { defineUniPages } from '@uni-helper/vite-plugin-uni-pages'
import { tabBar } from './src/layouts/fg-tabbar/tabbarList'

const usedWotComponents = [
  'config-provider',
  'toast',
  'message-box',
  'icon',
  'tabbar',
  'tabbar-item',
  'navbar',
  'button',
  'action-sheet',
  'loading',
  'swipe-action',
  'fab',
  'popup',
  'input',
  'tag',
  'text',
  'status-tip',
].join('|')

export default defineUniPages({
  globalStyle: {
    navigationStyle: 'default',
    navigationBarTitleText: '小智',
    navigationBarBackgroundColor: '#f8f8f8',
    navigationBarTextStyle: 'black',
    backgroundColor: '#FFFFFF',
  },
  easycom: {
    autoscan: true,
    custom: {
      '^fg-(.*)': '@/components/fg-$1/fg-$1.vue',
      [`^wd-(${usedWotComponents})$`]: 'wot-design-uni/components/wd-$1/wd-$1.vue',
    },
  },
  tabBar: tabBar as any,
})
```

- [ ] **Step 2: 验证**

Run:
```bash
pnpm build:mp-weixin
```

Expected: 构建成功；`dist/build/mp-weixin/node-modules/wot-design-uni/components/` 下仅保留白名单中的组件。

- [ ] **Step 3: 提交**

```bash
git add pages.config.ts
git commit -m "perf(manager-mobile): whitelist wot-design-uni components"
```

---

### Task 12: 最终构建与回归验证

- [ ] **Step 1: 全量检查**

Run:
```bash
cd "D:/QWEN3.0/esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile"
rm -rf dist/build/mp-weixin
pnpm install
pnpm lint
pnpm type-check
pnpm build:mp-weixin
```

Expected: `lint`、`type-check`、`build:mp-weixin` 均成功退出。

- [ ] **Step 2: 记录体积数据**

Run:
```bash
cd dist/build/mp-weixin
du -sh .
wc -c common/vendor.js
wc -c app.js
wc -c i18n/*.js 2>/dev/null | tail -1
find . -path './node-modules/wot-design-uni/components/*' -type f | wc -l
```

记录优化前后对比，写入 `docs/superpowers/plans/2026-06-21-miniprogram-phase1-evidence.md`（可选）。

- [ ] **Step 3: 功能回归清单（微信开发者工具）**

- [ ] 启动页无白屏/无 key 闪动。
- [ ] 登录成功后跳转到设备列表；请求头携带 `Authorization`。
- [ ] 切换语言（设置页）后 tabBar/页面文案更新，请求头 `Accept-language` 同步变化。
- [ ] 打开“我的”页：设备数、在线数、任务数正常显示；反复切换 tab 10s 内不重复请求设备列表。
- [ ] 进入聊天页：发送、停止、重新生成、清空历史正常；流式输出时列表不闪动。
- [ ] 进入聊天详情页：历史消息正常渲染，音频播放正常。
- [ ] 设备详情页 WebSocket 日志正常追加。
- [ ] 分包/页面跳转无 404（本次未迁移分包，仅验证当前页面）。

- [ ] **Step 4: 提交最终变更**

```bash
git add -A
git status
# 确认只包含本次优化相关文件，不包含 dist/
git commit -m "perf(manager-mobile): phase 1 quick wins (bundle, runtime, cache)"
```

---

## 自我审查

1. **Spec 覆盖**：本计划覆盖了设计文档 Phase 1 的“清理陈旧产物、移除未使用依赖、polyfill/dayjs、调试日志、token/lang 内存缓存、baseURL 缓存、Pinia 异步写入、列表 key、mine 并行缓存、i18n 懒加载、wot-design-uni 白名单”全部条目。
2. **Placeholder 检查**：无 TBD/TODO；每个代码步骤提供了完整可替换的代码或精确命令。
3. **类型一致性**：`authCache.ts` 与 `alova.ts`、`store/lang.ts`、`store/user.ts`、`pages/v2/login/index.vue` 使用同一套 `get/set/clear` 命名；`Language` 类型从 `@/store/lang` 导入。
4. **边界**：Phase 2/3（文件拆分、聊天重构、分包、静态资源压缩）不在本计划范围内，将另起计划。
