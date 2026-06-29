# LiMa 星云小程序 — 暗黑星云主题统一设计

> 日期: 2026-06-29
> 状态: Draft
> 范围: `esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/`

---

## 1. 背景与问题

### 1.1 当前状况

LiMa 星云小程序（uni-app Vue 3 + Vite + TypeScript + wot-design-uni）存在严重的**主题分裂**：

- `src/style/index.scss` 定义了完整的深空暗黑主题（30+ CSS 变量 + wot-design-uni 暗黑覆盖）
- 但只有 **3 个页面**（login / settings / device-config）使用了暗黑主题
- **10+ 个页面**使用亮色硬编码样式（`#f5f5f7` 背景、`#fff` 卡片、`#1d1d1f` 文字）
- 使用了 **3 种不同的蓝色主色**：`#3b82f6`（index.scss --accent）、`#336cff`（多数亮色页面）、`#667dea`（TabBar）
- `pages.json` 全局样式为亮色（`navigationBarBackgroundColor: "#f8f8f8"`），与 `App.vue` 设置的 `setBackgroundColor('#07070f')` 矛盾
- TabBar 为亮色（`backgroundColor: "#fff"`），与部分暗黑页面不协调
- 全局工具类 `.nebula-card` / `.nebula-btn` / `.nebula-bg` 已定义但**未被任何页面使用**

### 1.2 目标

将所有页面统一为深空暗黑星云主题，与 chat-web 保持品牌一致，消除颜色分裂和硬编码。

---

## 2. 方案选择

| 方案 | 描述 | 工作量 | 品牌一致性 |
|------|------|--------|-----------|
| **A: 全暗黑统一（选定）** | 迁移亮色页面到 index.scss 暗黑变量 | 中 | ✅ 与 chat-web 一致 |
| B: 全亮色统一 | 重写 index.scss 为亮色，改 3 个暗黑页面 | 大 | ❌ 与 chat-web 不一致 |
| C: 自适应主题 | 双主题 + 切换 | 最大 | ⚠️ 需额外 UI |

选择 A 的理由：
1. 暗黑主题基础设施已就绪（30+ 变量 + wot 覆盖）
2. 与 chat-web 星云主题品牌统一
3. 工作量最小——只需替换硬编码颜色为变量
4. 移动端 OLED 省电 + 夜间使用舒适

---

## 3. 主题系统统一

### 3.1 主色统一

| 旧值 | 新值 | 出现位置 |
|------|------|---------|
| `#336cff` | `var(--accent)` / `#3b82f6` | device-list, device-detail, chat, mine, agent, create, voiceprint |
| `#667dea` | `var(--accent)` / `#3b82f6` | TabBar selectedColor |
| `#5b8def` | `var(--accent2)` / `#60a5fa` | 渐变终点色 |

### 3.2 背景统一

| 旧值 | 新值 | 出现位置 |
|------|------|---------|
| `#f5f5f7` | `var(--bg)` / `#07070f` | device-list, device-detail, chat, mine, agent, create |
| `#f5f7fb` | `var(--bg)` / `#07070f` | voiceprint, chat-history, privacy-permissions |
| `#fbfbfb` | `var(--bg2)` / `#0a0a14` | voiceprint 卡片, chat-history 卡片 |
| `#fff` / `#ffffff` | `var(--surface)` / `rgba(255,255,255,0.03)` | 所有白色卡片 |

### 3.3 文字色统一

| 旧值 | 新值 | 语义 |
|------|------|------|
| `#1d1d1f` / `#232338` / `#222` | `var(--text)` / `#f0f4f8` | 主文字 |
| `#65686f` / `#4b5563` | `var(--muted)` / `#8b95a8` | 次要文字 |
| `#9d9ea3` / `#999` / `#c7c7cc` | `var(--dim)` / `#5a6372` | 辅助文字 |
| `#3a4252` | `var(--faint)` / `#3a4252` | 最淡文字 |

### 3.4 边框统一

| 旧值 | 新值 |
|------|------|
| `#eee` / `#eeeeee` / `#f0f0f0` | `var(--border)` / `rgba(255,255,255,0.04)` |

### 3.5 卡片样式统一

激活 `.nebula-card` 全局类，替换所有硬编码白色卡片：

```scss
// 现有定义（index.scss）
.nebula-card {
  background: var(--surface);
  border: 1rpx solid var(--border);
  border-radius: var(--r);        // 32rpx
  backdrop-filter: blur(24rpx);
  box-shadow: 0 4rpx 20rpx rgba(0,0,0,0.2);
  // ::before gradient overlay
}
```

当前亮色页面的 `.bento-card`：
```scss
// 旧（硬编码）
.bento-card {
  background: #ffffff;
  border-radius: 24rpx;
  padding: 28rpx;
  box-shadow: 0 2rpx 12rpx rgba(0,0,0,0.04);
}
```

替换为：
```scss
// 新（使用变量）
.bento-card {
  background: var(--surface);
  border: 1rpx solid var(--border);
  border-radius: var(--r);
  padding: 28rpx;
  box-shadow: 0 4rpx 20rpx rgba(0,0,0,0.2);
  backdrop-filter: blur(24rpx);
}
```

### 3.6 pages.json 全局样式

```json
"globalStyle": {
  "navigationBarBackgroundColor": "#07070f",
  "navigationBarTextStyle": "white",
  "backgroundColor": "#07070f",
  "backgroundTextStyle": "light"
}
```

### 3.7 TabBar 配置

```json
"tabBar": {
  "color": "#5a6372",
  "selectedColor": "#3b82f6",
  "backgroundColor": "#0a0a14",
  "borderStyle": "black"
}
```

---

## 4. 页面逐页改造

### 4.1 已暗黑页面（微调）

#### Login (`v2/login/index.vue`)
- ✅ 已使用暗黑主题
- 微调：将 `bg-[#05050a]` → `bg-[var(--bg)]`，确保用 CSS 变量
- 保留：星云背景、品牌框、渐变按钮、fade-in-up 动画

#### Settings (`settings/index.vue`)
- ✅ 已使用暗黑主题
- 微调：确认所有颜色使用 CSS 变量（当前已基本符合）

#### Device Config (`device-config/index.vue`)
- ✅ 已使用暗黑主题
- 微调：确认所有颜色使用 CSS 变量

### 4.2 亮色→暗黑迁移页面

#### Device List (`v2/device-list/index.vue`) — 首页
- 背景 `#f5f5f7` → `var(--bg)`
- 设备卡片 `#fff` → `var(--surface)` + nebula-card
- 文字 `#1d1d1f` → `var(--text)`，`#65686f` → `var(--muted)`
- 搜索框暗黑化
- 状态标签暗黑化
- `wd-config-provider theme-color` → `#3b82f6`
- 空状态插图暗黑适配

#### Device Detail (`v2/device-detail/index.vue`)
- 背景 `#f5f5f7` → `var(--bg)`
- 头部渐变 `#336cff → #5b8def` → `var(--accent) → var(--accent2)`
- `.bento-card` → nebula-card 变量
- 进度条轨道 `#edf1f7` → `rgba(255,255,255,0.06)`，填充 `#336cff` → `var(--accent)`
- 阶段色保留语义但适配暗黑：running `var(--accent)`，done `var(--green)`，failed `#ef4444`
- 7 个子组件同步迁移

#### Chat (`chat/chat.vue`)
- 背景 `#f5f5f7` → `var(--bg)`
- 用户气泡 `#336cff` → `var(--accent)` 渐变
- AI 气泡 `#fff` → `var(--surface)` 玻璃效果
- 输入栏暗黑化：背景 `var(--bg2)`，边框 `var(--border)`
- 发送按钮 `#336cff` → `var(--accent)`
- 代码块 `#1e1e2e` 保留（暗色在暗黑页面上更协调）
- 自定义 navbar 暗黑化

#### Mine (`mine/mine.vue`)
- 背景 `#f5f5f7` → `var(--bg)`
- 用户卡片渐变 `#336cff → #5b8def` → `var(--accent) → var(--accent2)`
- 统计数字色：`#336cff` → `var(--accent)`，`#07c160` → `var(--green)`，`#f59e0b` → `var(--amber)`
- 菜单卡片 `#fff` → `var(--surface)`
- 分割线 `#f0f0f0` → `var(--border)`
- 退出按钮暗黑化：`#ffd6d6` 边框 → `rgba(239,68,68,0.15)`，`#ff4d4f` → `#ef4444`

#### Agent Center (`index/index.vue`)
- 背景 `#f5f5f7` → `var(--bg)`
- Hero 渐变 `#336cff → #5b8def` → `var(--accent) → var(--accent2)`
- 能力网格卡片 `#fff` → `var(--surface)`
- 图标背景色适配暗黑（降低不透明度）
- 快捷操作卡片暗黑化

#### Voiceprint (`voiceprint/index.vue`)
- 背景 `#f5f7fb` → `var(--bg)`
- 卡片 `#fbfbfb` → `var(--surface)`
- 文字 `#232338` → `var(--text)`，`#65686f` → `var(--muted)`
- FAB 按钮暗黑化
- 录音状态 UI 暗黑化

#### Chat History (`chat-history/index.vue`)
- 背景 `#f5f7fb` → `var(--bg)`
- 卡片 `#fbfbfb` → `var(--surface)`
- 边框 `#eeeeee` → `var(--border)`

#### Create (`create/create.vue`)
- 背景 `#f5f5f7` → `var(--bg)`
- 模式标签：active `#eef3ff` → `rgba(59,130,246,0.1)`，border `#336cff` → `var(--accent)`
- 设备选择 chips 暗黑化
- 提交按钮 `#336cff` → `var(--accent)`

#### Privacy Permissions (`privacy-permissions.vue`)
- 背景 `#f5f7fb` → `var(--bg)`
- 卡片 `#fbfbfb` → `var(--surface)`
- 警告提示 `#fff8ed` → `rgba(245,158,11,0.06)`，border `#ffd6a6` → `rgba(245,158,11,0.15)`

---

## 5. 增强动效与微交互

### 5.1 卡片交互反馈

```scss
.nebula-card-interactive {
  transition: transform 0.15s ease;
  &:active {
    transform: scale(0.98);
  }
}
```

应用范围：设备卡片、聊天历史卡片、能力网格卡片、菜单项

### 5.2 页面入场动画

```scss
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
```

应用范围：所有页面根容器

### 5.3 按钮反馈

```scss
// 全局按钮 active 缩放
wd-button:active,
.nebula-btn:active {
  transform: scale(0.97);
  transition: transform 0.1s ease;
}
```

### 5.4 骨架屏

```scss
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
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

应用范围：设备列表加载态、聊天历史加载态、智能体列表加载态

### 5.5 状态脉冲增强

确认设备在线状态点在暗黑背景下有足够对比度，必要时增加 glow 效果：

```scss
.status-online::after {
  box-shadow: 0 0 8rpx rgba(34,197,94,0.6);
}
```

---

## 6. 新增/补充全局样式

在 `src/style/index.scss` 中补充：

```scss
// === 交互增强 ===
.nebula-card-interactive {
  background: var(--surface);
  border: 1rpx solid var(--border);
  border-radius: var(--r);
  backdrop-filter: blur(24rpx);
  box-shadow: 0 4rpx 20rpx rgba(0,0,0,0.2);
  transition: transform 0.15s ease;
  &:active { transform: scale(0.98); }
}

// === 页面入场 ===
.page-enter {
  animation: fade-in-up 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

// === 骨架屏 ===
.skeleton {
  background: linear-gradient(90deg, var(--surface) 25%, var(--surface-h) 50%, var(--surface) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--r-sm);
  overflow: hidden;
}

// === 暗黑输入框 ===
.dark-input {
  background: var(--bg2) !important;
  color: var(--text) !important;
  border: 1rpx solid var(--border) !important;
  border-radius: var(--r-sm) !important;
  &::placeholder { color: var(--dim) !important; }
  &:focus { border-color: var(--accent) !important; }
}

// === 暗黑标签 ===
.dark-tag {
  background: rgba(59,130,246,0.1);
  color: var(--accent);
  border: 1rpx solid rgba(59,130,246,0.15);
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
```

---

## 7. 不改动的部分

- **业务逻辑**：不修改任何 API 调用、状态管理、路由逻辑
- **wot-design-uni 组件源码**：只通过 CSS 变量覆盖，不 fork 组件
- **pages.json 路由**：页面路径和顺序不变
- **i18n**：不改动国际化文本
- **BluFi 配网逻辑**：只改视觉，不改 BLE 交互
- **语音录入逻辑**：只改 UI 外观，不改录音 API
- **Pinia stores**：不修改状态管理代码
- **API 层**：不修改 `src/api/` 和 `src/http/`

---

## 8. 实施分批

### P1: 主题基础 + 全局配置
1. 补充 `index.scss` 新增工具类
2. 更新 `pages.json` 全局样式和 TabBar 配置
3. 更新 `App.vue` 确认 `setBackgroundColor`
4. 统一 `wd-config-provider theme-color` 为 `#3b82f6`

### P2: 核心页面迁移
5. Device List（首页）→ 暗黑
6. Device Detail + 7 个子组件 → 暗黑
7. Chat → 暗黑
8. Mine → 暗黑

### P3: 次要页面迁移 + 微交互
9. Agent Center → 暗黑
10. Voiceprint → 暗黑
11. Chat History → 暗黑
12. Create → 暗黑
13. Privacy Permissions → 暗黑

### P4: 微交互 + 验证
14. 卡片交互反馈
15. 页面入场动画
16. 骨架屏
17. 按钮反馈
18. 状态脉冲增强
19. 全局回归验证

---

## 9. 成功标准

1. ✅ 所有页面背景统一为 `#07070f`，无 `#f5f5f7` / `#f5f7fb` / `#fff` 残留
2. ✅ 全局只使用一个主色 `#3b82f6`，无 `#336cff` / `#667dea` 残留
3. ✅ 所有卡片使用 `var(--surface)` 或 `.nebula-card`，无白色硬编码
4. ✅ TabBar 暗黑化，`backgroundColor: #0a0a14`，`selectedColor: #3b82f6`
5. ✅ `pages.json` 全局样式与暗黑主题匹配
6. ✅ 可交互卡片有 `active:scale` 反馈
7. ✅ 列表页有骨架屏加载态
8. ✅ 无 JS 控制台错误，无样式闪烁（FOUC）
9. ✅ 微信开发者工具 + 真机预览正常
10. ✅ 与 chat-web 星云主题品牌一致

---

## 10. 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| wot-design-uni 组件在暗黑下样式异常 | 已有完整 `--wot-*` 覆盖，逐组件验证 |
| 微信小程序 `backdrop-filter` 支持有限 | 基础库 2.25.0+ 支持，加 `@supports` 降级 |
| 页面切换闪烁（FOUC） | `App.vue` 全局 `setBackgroundColor` + 页面级 `style` 同步 |
| 暗黑下可读性差 | 严格使用 `--text` / `--muted` / `--dim` 层级，保证对比度 |
| TabBar 原生组件限制 | 原生 TabBar 颜色由 `pages.json` 控制，直接修改即可 |
