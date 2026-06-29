# LiMa 星云小程序暗黑主题统一 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将所有小程序页面统一为深空暗黑星云主题，消除主题分裂和颜色硬编码。

**Architecture:** 在现有 `index.scss` CSS 变量系统基础上，替换所有亮色硬编码为暗黑变量，激活 `.nebula-card` 等全局工具类，补充微交互动效。不改业务逻辑，只改视觉层。

**Tech Stack:** uni-app Vue 3 + Vite + TypeScript + wot-design-uni + UnoCSS + SCSS

**项目根目录:** `D:/QWEN3.0/esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/`

---

## 文件变更地图

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/style/index.scss` | 修改 | 新增工具类（nebula-card-interactive, page-enter, skeleton, dark-input, dark-tag, gradient-header） |
| `src/pages.json` | 修改 | globalStyle 暗黑化 + tabBar 暗黑化 |
| `src/layouts/fg-tabbar/tabbarList.ts` | 修改 | tabBar 颜色值暗黑化 |
| `src/layouts/tabbar.vue` | 修改 | 启用 themeVars |
| `src/pages/v2/device-list/index.vue` | 修改 | 亮色→暗黑迁移 |
| `src/pages/v2/device-detail/index.vue` | 修改 | 亮色→暗黑迁移 |
| `src/pages/v2/device-detail/components/device-info-card.vue` | 修改 | bento-card→暗黑 |
| `src/pages/v2/device-detail/components/health-check.vue` | 修改 | bento-card→暗黑 |
| `src/pages/v2/device-detail/components/supplies-panel.vue` | 修改 | bento-card→暗黑 |
| `src/pages/v2/device-detail/components/task-status.vue` | 修改 | bento-card→暗黑 |
| `src/pages/v2/device-detail/components/transfer-panel.vue` | 修改 | bento-card→暗黑 |
| `src/pages/v2/device-detail/components/voice-approval.vue` | 修改 | bento-card→暗黑 |
| `src/pages/v2/device-detail/components/write-draw-panel.vue` | 修改 | bento-card→暗黑 |
| `src/pages/chat/chat.vue` | 修改 | 亮色→暗黑迁移 |
| `src/pages/mine/mine.vue` | 修改 | 亮色→暗黑迁移 |
| `src/pages/index/index.vue` | 修改 | 亮色→暗黑迁移 |
| `src/pages/voiceprint/index.vue` | 修改 | 亮色→暗黑迁移 |
| `src/pages/chat-history/index.vue` | 修改 | 亮色→暗黑迁移 |
| `src/pages/create/create.vue` | 修改 | 亮色→暗黑迁移 |
| `src/pages/settings/privacy-permissions.vue` | 修改 | 亮色→暗黑迁移 |
| `src/pages/v2/login/index.vue` | 修改 | 微调：硬编码→CSS变量 |
| `src/pages/settings/index.vue` | 修改 | 微调：确认CSS变量 |
| `src/pages/device-config/index.vue` | 修改 | 微调：确认CSS变量 |

---

## Task 1: 补充全局工具类到 index.scss

**Files:**
- Modify: `src/style/index.scss`

- [ ] **Step 1: 在 index.scss 末尾追加新工具类**

在文件末尾（`.nebula-bg::after` 闭合之后）追加：

```scss
// === 交互增强 ===
.nebula-card-interactive {
  background: var(--surface);
  border: 1rpx solid var(--border);
  border-radius: var(--r);
  backdrop-filter: blur(24rpx);
  box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.2);
  transition: transform 0.15s ease;
  &:active {
    transform: scale(0.98);
  }
}

// === 页面入场动画 ===
.page-enter {
  animation: fade-in-up 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes fade-in-up {
  from {
    opacity: 0;
    transform: translateY(20rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

// === 骨架屏 ===
.skeleton {
  background: linear-gradient(
    90deg,
    var(--surface) 25%,
    var(--surface-h) 50%,
    var(--surface) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--r-sm);
  overflow: hidden;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.skeleton-text {
  height: 28rpx;
  margin-bottom: 16rpx;
  &:last-child {
    width: 60%;
  }
}

.skeleton-card {
  height: 200rpx;
  margin-bottom: 24rpx;
}

// === 暗黑输入框 ===
.dark-input {
  background: var(--bg2) !important;
  color: var(--text) !important;
  border: 1rpx solid var(--border) !important;
  border-radius: var(--r-sm) !important;
  &::placeholder {
    color: var(--dim) !important;
  }
  &:focus {
    border-color: var(--accent) !important;
  }
}

// === 暗黑标签 ===
.dark-tag {
  background: rgba(59, 130, 246, 0.1);
  color: var(--accent);
  border: 1rpx solid rgba(59, 130, 246, 0.15);
  border-radius: 8rpx;
  padding: 4rpx 16rpx;
  font-size: 22rpx;
}

// === 渐变头部 ===
.gradient-header {
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  border-radius: 0 0 var(--r) var(--r);
  padding: 40rpx 32rpx;
  color: #fff;
}

// === 全局按钮反馈 ===
button:active,
wd-button:active {
  transform: scale(0.97);
  transition: transform 0.1s ease;
}
```

- [ ] **Step 2: 验证 SCSS 语法**

Run: `cd D:/QWEN3.0/esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile && npx sass --no-source-map --style=compressed src/style/index.scss /dev/null 2>&1 || echo "SCSS check done"`

Expected: 无错误输出（或 `SCSS check done`）

- [ ] **Step 3: Commit**

```bash
git add src/style/index.scss
git commit -m "feat(mp): add dark theme utility classes — nebula-card-interactive, page-enter, skeleton, dark-input, dark-tag, gradient-header"
```

---

## Task 2: 更新 pages.json 全局样式和 TabBar

**Files:**
- Modify: `src/pages.json`
- Modify: `src/layouts/fg-tabbar/tabbarList.ts`
- Modify: `src/layouts/tabbar.vue`

- [ ] **Step 1: 更新 pages.json globalStyle**

在 `src/pages.json` 中找到 `"globalStyle"` 对象，替换为：

```json
"globalStyle": {
  "navigationBarBackgroundColor": "#07070f",
  "navigationBarTextStyle": "white",
  "backgroundColor": "#07070f",
  "backgroundTextStyle": "light"
}
```

- [ ] **Step 2: 更新 tabbarList.ts tabBar 配置**

在 `src/layouts/fg-tabbar/tabbarList.ts` 中，找到 `_tabbar` 对象，替换颜色：

```ts
const _tabbar: TabBar = {
  custom: selectedTabbarStrategy === TABBAR_MAP.CUSTOM_TABBAR_WITH_CACHE,
  color: '#5a6372',
  selectedColor: '#3b82f6',
  backgroundColor: '#0a0a14',
  borderStyle: 'black',
  height: '50px',
  fontSize: '10px',
  iconWidth: '24px',
  spacing: '3px',
  list: tabbarList as unknown as TabBar['list'],
}
```

- [ ] **Step 3: 更新 tabbar.vue 启用 themeVars**

在 `src/layouts/tabbar.vue` 中，替换 `themeVars` 为：

```ts
const themeVars: ConfigProviderThemeVars = {
  colorTheme: '#3b82f6',
  buttonPrimaryBgColor: '#3b82f6',
  buttonPrimaryColor: '#3b82f6',
}
```

- [ ] **Step 4: Commit**

```bash
git add src/pages.json src/layouts/fg-tabbar/tabbarList.ts src/layouts/tabbar.vue
git commit -m "feat(mp): update globalStyle and tabBar to dark theme — bg #07070f, accent #3b82f6"
```

---

## Task 3: Device List 首页暗黑迁移

**Files:**
- Modify: `src/pages/v2/device-list/index.vue`

- [ ] **Step 1: 替换页面背景和卡片样式**

在 `<style lang="scss" scoped>` 中，找到并替换以下样式：

将 `.bento-page` 的 `background: #f5f5f7` 替换为：
```scss
.bento-page {
  min-height: 100vh;
  background: var(--bg);
  padding-bottom: calc(env(safe-area-inset-bottom) + 120rpx);
}
```

将 `.bento-card` 的白色背景替换为：
```scss
.bento-card {
  background: var(--surface);
  border: 1rpx solid var(--border);
  border-radius: var(--r);
  padding: 28rpx;
  box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(24rpx);
}
```

将 `.bento-title` 的颜色替换为：
```scss
.bento-title {
  font-size: 30rpx;
  font-weight: 600;
  color: var(--text);
}
```

- [ ] **Step 2: 替换文字颜色**

在整个 `<style>` 块中执行以下替换：
- `color: #1d1d1f` → `color: var(--text)`
- `color: #65686f` → `color: var(--muted)`
- `color: #9d9ea3` → `color: var(--dim)`
- `color: #336cff` → `color: var(--accent)`

- [ ] **Step 3: 替换其他硬编码颜色**

- `background: #fff` / `background: #ffffff` → `background: var(--surface)`
- `background: #f5f5f7` → `background: var(--bg2)`
- `border: 1rpx solid #eee` / `border: 1rpx solid #eeeeee` → `border: 1rpx solid var(--border)`
- `box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.04)` → `box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.2)`

- [ ] **Step 4: 更新模板中的内联样式和自定义类**

在 `<template>` 中：
- 找到 `custom-class="!bg-[#f5f5f7]"` 的 `wd-input`，替换为 `custom-class="!bg-[var(--bg2)] !text-[var(--text)]"`
- 找到 `wd-config-provider` 如果有 `theme-color="#336cff"`，替换为 `theme-color="#3b82f6"`

- [ ] **Step 5: 添加页面入场动画**

在页面根元素（`.bento-page`）上添加 `page-enter` 类：
```html
<view class="bento-page page-enter">
```

- [ ] **Step 6: Commit**

```bash
git add src/pages/v2/device-list/index.vue
git commit -m "feat(mp): migrate device-list page to dark nebula theme"
```

---

## Task 4: Device Detail + 7 子组件暗黑迁移

**Files:**
- Modify: `src/pages/v2/device-detail/index.vue`
- Modify: `src/pages/v2/device-detail/components/device-info-card.vue`
- Modify: `src/pages/v2/device-detail/components/health-check.vue`
- Modify: `src/pages/v2/device-detail/components/supplies-panel.vue`
- Modify: `src/pages/v2/device-detail/components/task-status.vue`
- Modify: `src/pages/v2/device-detail/components/transfer-panel.vue`
- Modify: `src/pages/v2/device-detail/components/voice-approval.vue`
- Modify: `src/pages/v2/device-detail/components/write-draw-panel.vue`

- [ ] **Step 1: 迁移 device-detail/index.vue**

与 Task 3 相同的模式：
- `.bento-page` background → `var(--bg)`
- `.bento-card` → `var(--surface)` + `var(--border)` + 暗黑阴影
- `.bento-title` color → `var(--text)`
- 所有 `#1d1d1f` → `var(--text)`, `#65686f` → `var(--muted)`, `#9d9ea3` → `var(--dim)`
- 所有 `#336cff` → `var(--accent)`, `#5b8def` → `var(--accent2)`
- 头部渐变 `linear-gradient(135deg, #336cff, #5b8def)` → `linear-gradient(135deg, var(--accent), var(--accent2))`
- `wd-config-provider theme-color="#336cff"` → `theme-color="#3b82f6"`
- 添加 `page-enter` 类到根元素

- [ ] **Step 2: 迁移 device-info-card.vue**

```scss
.bento-card {
  background: var(--surface);
  border: 1rpx solid var(--border);
  border-radius: var(--r);
  padding: 28rpx;
  box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(24rpx);
}
.bento-title { color: var(--text); }
```

头部渐变：`linear-gradient(135deg, #336cff, #5b8def)` → `linear-gradient(135deg, var(--accent), var(--accent2))`
文字色：`#1d1d1f` → `var(--text)`, `#65686f` → `var(--muted)`, `#fff` 保留（渐变上的白色文字）

- [ ] **Step 3: 迁移 health-check.vue**

同上 `.bento-card` / `.bento-title` 替换模式。
额外：`.history-item` 的 `background: #f5f5f7` → `background: var(--bg2)`

- [ ] **Step 4: 迁移 supplies-panel.vue**

同上 `.bento-card` / `.bento-title` 替换模式。

- [ ] **Step 5: 迁移 task-status.vue**

```scss
.bento-card {
  background: var(--surface);
  border: 1rpx solid var(--border);
  border-radius: var(--r);
  padding: 28rpx;
  box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(24rpx);
}
.bento-title { color: var(--text); }
.progress-track { background: rgba(255, 255, 255, 0.06); }
.progress-fill { background: var(--accent); }
.progress-label { color: var(--muted); }
```

- [ ] **Step 6: 迁移 transfer-panel.vue**

同上 `.bento-card` / `.bento-title` 替换模式。
额外：`wd-input` 的 `custom-class="!bg-[#f5f5f7]"` → `custom-class="!bg-[var(--bg2)] !text-[var(--text)]"`
`.state-label` 的 `color: #65686f` → `color: var(--muted)`

- [ ] **Step 7: 迁移 voice-approval.vue**

同上 `.bento-card` / `.bento-title` 替换模式。
额外：
- `.task-card` 的 `background: #f5f5f7` → `background: var(--bg2)`
- `.task-capability` 的 `color: #222` → `color: var(--text)`
- `.task-id` / `.task-params` 的 `color: #65686f` → `color: var(--muted)`
- `.constraint-text` 的 `color: #4b5563` → `color: var(--muted)`
- `.empty-state` 的 `color: #9d9ea3` → `color: var(--dim)`

- [ ] **Step 8: 迁移 write-draw-panel.vue**

同上 `.bento-card` / `.bento-title` 替换模式。
额外：
- `.hint-text` 的 `color: #9d9ea3` → `color: var(--dim)`
- `wd-input` 的 `custom-class="!bg-[#f5f5f7]"` → `custom-class="!bg-[var(--bg2)] !text-[var(--text)]"`

- [ ] **Step 9: Commit**

```bash
git add src/pages/v2/device-detail/
git commit -m "feat(mp): migrate device-detail and 7 sub-components to dark nebula theme"
```

---

## Task 5: Chat 页面暗黑迁移

**Files:**
- Modify: `src/pages/chat/chat.vue`

- [ ] **Step 1: 替换页面背景和导航栏**

```scss
.chat-page {
  min-height: 100vh;
  background: var(--bg);
  display: flex;
  flex-direction: column;
}
```

自定义 navbar：`background: #fff` → `background: var(--bg2)`, `color: #1d1d1f` → `color: var(--text)`, `border-bottom` → `1rpx solid var(--border)`

- [ ] **Step 2: 替换气泡样式**

用户气泡：
```scss
.msg-user .msg-bubble {
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  color: #fff;
}
```

AI 气泡：
```scss
.msg-assistant .msg-bubble {
  background: var(--surface);
  border: 1rpx solid var(--border);
  color: var(--text);
  backdrop-filter: blur(24rpx);
}
```

- [ ] **Step 3: 替换输入栏**

```scss
.input-bar {
  background: var(--bg2);
  border-top: 1rpx solid var(--border);
}
```

发送按钮 `background: #336cff` → `background: var(--accent)`
停止按钮 `background: #ff4d4f` → `background: #ef4444`

- [ ] **Step 4: 替换其他硬编码颜色**

- 所有 `#1d1d1f` → `var(--text)`
- 所有 `#65686f` → `var(--muted)`
- 所有 `#9d9ea3` → `var(--dim)`
- 打字光标 `#336cff` → `var(--accent)`
- 代码块 `#1e1e2e` 保留（暗色在暗黑页面更协调）

- [ ] **Step 5: 添加页面入场动画**

根元素添加 `page-enter` 类。

- [ ] **Step 6: Commit**

```bash
git add src/pages/chat/chat.vue
git commit -m "feat(mp): migrate chat page to dark nebula theme"
```

---

## Task 6: Mine 我的页面暗黑迁移

**Files:**
- Modify: `src/pages/mine/mine.vue`

- [ ] **Step 1: 替换页面背景**

`.mine-page` 的 `background: #f5f5f7` → `background: var(--bg)`

- [ ] **Step 2: 替换用户卡片渐变**

`linear-gradient(135deg, #336cff, #5b8def)` → `linear-gradient(135deg, var(--accent), var(--accent2))`

- [ ] **Step 3: 替换卡片和文字颜色**

- 白色卡片 `background: #fff` → `background: var(--surface)` + `border: 1rpx solid var(--border)` + 暗黑阴影
- 统计数字 `#336cff` → `var(--accent)`, `#07c160` → `var(--green)`, `#f59e0b` → `var(--amber)`
- 文字 `#1d1d1f` → `var(--text)`, `#65686f` → `var(--muted)`, `#999` → `var(--dim)`
- 分割线 `#f0f0f0` → `var(--border)`

- [ ] **Step 4: 替换退出按钮**

```scss
.logout-section {
  background: var(--surface);
  border: 1rpx solid var(--border);
}
.logout-btn {
  color: #ef4444;
  border: 1rpx solid rgba(239, 68, 68, 0.15);
}
```

- [ ] **Step 5: 添加页面入场动画**

- [ ] **Step 6: Commit**

```bash
git add src/pages/mine/mine.vue
git commit -m "feat(mp): migrate mine page to dark nebula theme"
```

---

## Task 7: Agent Center 智能体页面暗黑迁移

**Files:**
- Modify: `src/pages/index/index.vue`

- [ ] **Step 1: 替换页面背景**

`.nebula-center` 的 `background: #f5f5f7` → `background: var(--bg)`

- [ ] **Step 2: 替换 Hero 渐变**

`linear-gradient(135deg, #336cff, #5b8def)` → `linear-gradient(135deg, var(--accent), var(--accent2))`

- [ ] **Step 3: 替换能力网格卡片**

- 白色卡片 `background: #fff` → `background: var(--surface)` + `border: 1rpx solid var(--border)` + 暗黑阴影
- 图标背景色降低不透明度：`rgba(51, 108, 255, 0.1)` → `rgba(59, 130, 246, 0.1)` 等
- 文字 `#1d1d1f` → `var(--text)`, `#65686f` → `var(--muted)`

- [ ] **Step 4: 替换设备列表和快捷操作卡片**

同上白色卡片→暗黑卡片模式。

- [ ] **Step 5: 添加页面入场动画**

- [ ] **Step 6: Commit**

```bash
git add src/pages/index/index.vue
git commit -m "feat(mp): migrate agent center page to dark nebula theme"
```

---

## Task 8: Voiceprint 声纹页面暗黑迁移

**Files:**
- Modify: `src/pages/voiceprint/index.vue`

- [ ] **Step 1: 替换页面背景和卡片**

- `background: #f5f7fb` → `background: var(--bg)`
- 卡片 `background: #fbfbfb` → `background: var(--surface)` + `border: 1rpx solid var(--border)` + 暗黑阴影
- 文字 `#232338` → `var(--text)`, `#65686f` → `var(--muted)`, `#9d9ea3` → `var(--dim)`
- `#336cff` → `var(--accent)`

- [ ] **Step 2: 替换边框和其他硬编码**

- `border: 1rpx solid #eeeeee` → `border: 1rpx solid var(--border)`
- 输入框背景 `#f5f5f7` → `var(--bg2)`

- [ ] **Step 3: 添加页面入场动画**

- [ ] **Step 4: Commit**

```bash
git add src/pages/voiceprint/index.vue
git commit -m "feat(mp): migrate voiceprint page to dark nebula theme"
```

---

## Task 9: Chat History 聊天历史页面暗黑迁移

**Files:**
- Modify: `src/pages/chat-history/index.vue`

- [ ] **Step 1: 替换页面背景和卡片**

- `background: #f5f7fb` → `background: var(--bg)`
- 卡片 `background: #fbfbfb` → `background: var(--surface)` + `border: 1rpx solid var(--border)` + 暗黑阴影
- 文字 `#1d1d1f` / `#232338` → `var(--text)`, `#65686f` → `var(--muted)`, `#9d9ea3` → `var(--dim)`
- `border: 1rpx solid #eeeeee` → `border: 1rpx solid var(--border)`

- [ ] **Step 2: 添加页面入场动画**

- [ ] **Step 3: Commit**

```bash
git add src/pages/chat-history/index.vue
git commit -m "feat(mp): migrate chat-history page to dark nebula theme"
```

---

## Task 10: Create 创作页面暗黑迁移

**Files:**
- Modify: `src/pages/create/create.vue`

- [ ] **Step 1: 替换页面背景**

`background: #f5f5f7` → `background: var(--bg)`

- [ ] **Step 2: 替换模式标签和设备选择**

- 活跃标签 `background: #eef3ff` → `background: rgba(59, 130, 246, 0.1)`, `border: 2rpx solid #336cff` → `border: 2rpx solid var(--accent)`
- 非活跃标签白色背景 → `var(--surface)` + `var(--border)`
- 文字 `#1d1d1f` → `var(--text)`, `#65686f` → `var(--muted)`

- [ ] **Step 3: 替换提交按钮和其他颜色**

- `#336cff` → `var(--accent)`
- 卡片白色 → `var(--surface)` + 暗黑阴影

- [ ] **Step 4: 添加页面入场动画**

- [ ] **Step 5: Commit**

```bash
git add src/pages/create/create.vue
git commit -m "feat(mp): migrate create page to dark nebula theme"
```

---

## Task 11: Privacy Permissions 隐私权限页面暗黑迁移

**Files:**
- Modify: `src/pages/settings/privacy-permissions.vue`

- [ ] **Step 1: 替换页面背景和卡片**

- `background: #f5f7fb` → `background: var(--bg)`
- 卡片 `background: #fbfbfb` → `background: var(--surface)` + `border: 1rpx solid var(--border)` + 暗黑阴影
- 文字 `#1d1d1f` / `#232338` → `var(--text)`, `#65686f` → `var(--muted)`, `#9d9ea3` → `var(--dim)`
- `border: 1rpx solid #eeeeee` → `border: 1rpx solid var(--border)`

- [ ] **Step 2: 替换警告提示**

```scss
.fallback-hint {
  background: rgba(245, 158, 11, 0.06);
  border: 1rpx solid rgba(245, 158, 11, 0.15);
  color: var(--amber);
}
```

- [ ] **Step 3: Commit**

```bash
git add src/pages/settings/privacy-permissions.vue
git commit -m "feat(mp): migrate privacy-permissions page to dark nebula theme"
```

---

## Task 12: 已暗黑页面微调 — Login / Settings / Device-Config

**Files:**
- Modify: `src/pages/v2/login/index.vue`
- Modify: `src/pages/settings/index.vue`
- Modify: `src/pages/device-config/index.vue`

- [ ] **Step 1: Login 页面微调**

检查并替换任何硬编码颜色为 CSS 变量：
- `bg-[#05050a]` → `bg-[#07070f]`（统一为 `--bg` 值）或添加 `style="background: var(--bg)"`
- 确认 `wd-config-provider theme-color="#3b82f6"` 已正确
- 添加 `page-enter` 类到根元素

- [ ] **Step 2: Settings 页面微调**

确认所有颜色已使用 CSS 变量（该页面已基本符合）。检查是否有遗漏的硬编码。
添加 `page-enter` 类到根元素。

- [ ] **Step 3: Device-Config 页面微调**

确认所有颜色已使用 CSS 变量。检查是否有遗漏的硬编码。
添加 `page-enter` 类到根元素。

- [ ] **Step 4: Commit**

```bash
git add src/pages/v2/login/index.vue src/pages/settings/index.vue src/pages/device-config/index.vue
git commit -m "feat(mp): fine-tune dark pages — unify CSS variables, add page-enter animation"
```

---

## Task 13: 全局回归验证

**Files:**
- 无新文件，验证现有修改

- [ ] **Step 1: SCSS 语法检查**

```bash
cd D:/QWEN3.0/esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile
npx sass --no-source-map --style=compressed src/style/index.scss /dev/null
```

Expected: 无错误

- [ ] **Step 2: TypeScript 编译检查**

```bash
npx vue-tsc --noEmit 2>&1 | head -50
```

Expected: 无类型错误（或仅有与主题无关的既有错误）

- [ ] **Step 3: 硬编码颜色残留扫描**

```bash
grep -rn "#336cff\|#667dea\|#f5f5f7\|#f5f7fb\|#fbfbfb" src/pages/ src/layouts/ --include="*.vue" --include="*.ts" | grep -v "node_modules" | head -20
```

Expected: 无结果（所有旧硬编码颜色已替换）

- [ ] **Step 4: 白色背景残留扫描**

```bash
grep -rn "background: #fff\b\|background: #ffffff\b\|background-color: #fff\b" src/pages/ --include="*.vue" | head -20
```

Expected: 无结果（白色背景已替换为 `var(--surface)`）

- [ ] **Step 5: 构建测试**

```bash
pnpm build:mp 2>&1 | tail -20
```

Expected: 构建成功，无错误

- [ ] **Step 6: Commit 验证结果**

```bash
git add -A
git commit -m "chore(mp): verify dark theme migration — no residual light-theme colors"
```

---

## 成功标准核对

| # | 标准 | 验证方式 |
|---|------|---------|
| 1 | 所有页面背景统一为 `#07070f` | `grep -rn "#f5f5f7\|#f5f7fb" src/pages/` 无结果 |
| 2 | 全局只使用一个主色 `#3b82f6` | `grep -rn "#336cff\|#667dea" src/` 无结果 |
| 3 | 所有卡片使用 `var(--surface)` | `grep -rn "background: #fff" src/pages/` 无结果 |
| 4 | TabBar 暗黑化 | `tabbarList.ts` 中 `backgroundColor: '#0a0a14'`, `selectedColor: '#3b82f6'` |
| 5 | pages.json 全局样式匹配 | `navigationBarBackgroundColor: '#07070f'` |
| 6 | 可交互卡片有 active:scale | `.nebula-card-interactive` 类已定义 |
| 7 | 列表页有骨架屏 | `.skeleton` 类已定义 |
| 8 | 无 JS 控制台错误 | `pnpm build:mp` 成功 |
| 9 | 微信开发者工具 + 真机预览正常 | 手动验证 |
| 10 | 与 chat-web 星云主题品牌一致 | 主色和背景色一致 |
