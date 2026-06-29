# chat-web 控制台视觉打磨设计文档

> 日期：2026-06-29
> 状态：待审核
> 范围：`chat-web/` 目录下所有 HTML/CSS/JS 前端页面

## 1. 背景与目标

chat-web 是 LiMa 星云系统的浏览器控制台，包含 9 个 HTML 页面，由 FastAPI 静态文件服务直接托管。当前暗色星云主题已有较好的 CSS 变量基础，但多个页面视觉层次弱、缺少品牌感和微交互。

**目标：** 在不引入新依赖、不改变架构的前提下，增量提升视觉品质和交互体验。

**非目标：**
- 不迁移到前端框架（React/Vue）
- 不修改后端 API
- 不改动 donglicao-site-v2（独立 Next.js 项目）
- 不修改现有 CSS 变量值

## 2. 方案选择

| 方案 | 描述 | 优点 | 缺点 | 决定 |
|------|------|------|------|------|
| A 渐进式打磨 | 在现有 CSS/HTML 中增量添加视觉增强 | 改动小、可分批、风险低 | 内联样式继续增长 | ✅ 采用 |
| B 组件化重构 | 抽取 `.lima-card` 等组件类 | 长期维护好 | 改动面大、需全量回归 | ❌ 过度 |
| C 框架迁移 | 迁移到 React + Tailwind | 与官网统一 | 需构建管线、违背 YAGNI | ❌ 不合理 |

## 3. 设计规范

### 3.1 新增 CSS 变量

添加到 `styles.css` `:root` 块末尾，不修改现有变量：

```css
--glass-bg: rgba(10, 10, 20, 0.65);
--glass-border: rgba(255, 255, 255, 0.08);
--glass-blur: 20px;
--shimmer: linear-gradient(90deg, transparent, rgba(255,255,255,0.04), transparent);
--duration-fast: 0.15s;
--duration-normal: 0.25s;
--duration-slow: 0.4s;
```

### 3.2 新增样式区块

所有新增样式追加到 `styles.css` 底部，按区块注释分隔：

```
/* ─── AUTH PAGES ENHANCEMENT ─── */
/* ─── MICRO INTERACTIONS ─── */
/* ─── EMPTY STATES ─── */
/* ─── DEVICE PAGE ENHANCEMENT ─── */
/* ─── HANDWRITING PAGE ENHANCEMENT ─── */
/* ─── USAGE PAGE ENHANCEMENT ─── */
/* ─── KEYS PAGE ENHANCEMENT ─── */
```

## 4. 各页面改进细则

### 4.1 登录/注册页（P1 最高优先级）

**现状：** 纯边框卡片、无动态背景、无品牌感

**改进项：**

1. **星云粒子背景**：auth 页 `body::before` 添加与主页一致的 `ambientShift` 渐变动画
2. **玻璃拟态卡片**：`.auth-card` 添加 `backdrop-filter: blur(var(--glass-blur))` + `background: var(--glass-bg)` + `border: 1px solid var(--glass-border)`
3. **Logo 入场动画**：`.auth-logo svg` 添加 `@keyframes logoEnter`（`scale(0.8)→1` + `opacity:0→1`，0.4s `var(--ease-spring)`）
4. **输入框流光边框**：focus 时通过伪元素实现 `background: linear-gradient(90deg, var(--accent), var(--violet))` 渐变边框扫光动画（`@keyframes borderGlow`，2s 循环）
5. **按钮渐变光晕**：`.auth-btn` 改为 `background: linear-gradient(135deg, var(--accent), var(--violet))`，hover 时 `box-shadow: 0 0 24px var(--accent-glow), 0 0 48px var(--violet-glow)`
6. **错误提示动画**：`.auth-error` 添加 `@keyframes slideIn`（`translateX(-8px)→0`）+ 左侧 3px 红色指示条
7. **密码强度条**（仅注册页）：密码输入框下方添加 `.pw-strength` div，JS 实时计算强度（长度+字符类型），显示弱/中/强三段色条

**涉及文件：** `styles.css`、`login.html`、`register.html`

### 4.2 全局微交互（P1）

**4.2.1 按钮反馈**

所有可点击按钮添加 `active` 态缩放：

```css
.btn-primary:active, .auth-btn:active, .topbar-btn:active,
.new-chat-btn:active, .btn-danger:active, .btn-secondary:active {
  transform: scale(0.97);
  transition: transform var(--duration-fast) ease;
}
```

**4.2.2 Toast 通知升级**

在 `styles.css` 中增强 `.toast` 样式：
- 左侧 3px 色条（默认 `var(--accent)`，`.toast.error` 为 `var(--rose)`，`.toast.warning` 为 `var(--amber)`）
- 添加图标区域（通过 `::before` 伪元素 + Unicode 字符：✓/⚠/✕）
- 底部 2px 进度条动画（`@keyframes toastProgress`，3s 线性从 100%→0%）

在各页面 JS 中，`showToast()` 调用时支持 `{ error: true }` / `{ warning: true }` 选项。

**4.2.3 加载状态**

关键异步操作（设备列表加载、任务创建等）添加 shimmer 骨架屏：

```css
.skeleton {
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  overflow: hidden;
  position: relative;
}
.skeleton::after {
  content: '';
  position: absolute; inset: 0;
  background: var(--shimmer);
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
```

**4.2.4 页面过渡**

侧边栏导航切换时，主内容区添加淡入：

```css
main { animation: fadeIn var(--duration-normal) var(--ease-out); }
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
```

**涉及文件：** `styles.css`、各页面 JS（Toast 升级部分）

### 4.3 空状态插画（P2）

为以下场景添加内联 SVG 空状态插画 + 引导文案：

| 页面 | 空状态场景 | 插画主题 | 引导文案 |
|------|-----------|---------|---------|
| `devices.html` | 无已绑定设备 | 浮空绘图机轮廓 | "还没有绑定设备，点击右上角添加" |
| `index.html` | 无聊天历史 | 星云中的对话气泡 | "开始一段新的对话吧" |
| `keys.html` | 无 API Key | 钥匙+锁孔 | "创建一个 API Key 来访问 OpenAI 兼容接口" |
| `usage.html` | 无用量数据 | 空折线图 | "使用后这里会显示用量统计" |

实现方式：内联 SVG（约 20-30 行），放在各页面 `.empty` 元素内，配合 `@keyframes fadeFloat`（轻微上下浮动 + 呼吸透明度）动画。

**涉及文件：** `styles.css`、`devices.html`、`index.html`、`keys.html`、`usage.html`

### 4.4 设备管理页增强（P2）

1. **在线脉冲点**：在线设备卡片右上角添加绿色脉冲圆点（`@keyframes pulse`，1.5s 循环）
2. **运行中渐变边框**：`status.busy` 设备卡片添加 `border-image: linear-gradient(...)` 呼吸动画
3. **Drawer 分组**：详情区分三组（基础信息/网络状态/当前任务），每组间添加分割线 + 小标题（`<h3>` + `var(--text-faint)`）
4. **解绑确认弹窗**：添加设备名称 + 警告图标，确认按钮改为红色（`var(--rose)`）

**涉及文件：** `styles.css`、`devices.html`、`js/devices.js`

### 4.5 仿手写页增强（P3）

1. **表单控件统一**：textarea/select 添加 `--bg-input` 背景 + focus 流光边框（复用登录页的 `borderGlow` 动画）
2. **预览区装饰**：SVG 预览卡片添加微光边框 + 右上角"预览"标签（`position: absolute` + `var(--accent)` 背景）
3. **生成按钮**：改为渐变背景（`var(--accent)→var(--violet)`），加载时显示旋转 SVG 图标替代纯文字

**涉及文件：** `styles.css`、`handwriting.html`、`js/handwriting.js`

### 4.6 用量统计页增强（P3）

1. **统计卡片色条**：每个 `.summary-card` 左侧添加 3px 竖条（Token=青色、请求=紫色、费用=琥珀色），通过 `border-left` 实现
2. **图表卡片分割线**：`.chart-card h3` 下方添加 `1px solid var(--border)` + 渐变淡出效果

**涉及文件：** `styles.css`、`usage.html`

### 4.7 API Key 页增强（P3）

1. **Key 卡片化**：每个 Key 用卡片展示（而非纯列表行），包含名称、创建时间、最后使用时间
2. **Key 值遮罩**：默认显示 `sk-****...****`，点击眼睛图标切换显示/隐藏
3. **复制按钮**：点击后图标变为 ✓ 持续 2s，然后恢复

**涉及文件：** `styles.css`、`keys.html`、`js/keys.js`

### 4.8 不改动的部分

- `index.html` 聊天主页：已足够好，仅添加欢迎屏空状态插画
- `playground.html`：Monaco Editor 区域不改，仅微调面板分割线颜色
- `voice-call.html`：通话页布局不改，仅添加挂断按钮 `active` 缩放反馈
- 现有 CSS 变量值不修改

## 5. 实施计划

### 分批交付

| 批次 | 内容 | 涉及文件 | 预估改动量 |
|------|------|---------|-----------|
| P1 | 登录/注册页美化 + 全局微交互（按钮/Toast/骨架屏/页面过渡） | `styles.css`, `login.html`, `register.html`, `js/api.js` | ~200 行 CSS + ~50 行 JS |
| P2 | 空状态插画 + 设备页增强 | `styles.css`, `devices.html`, `index.html`, `keys.html`, `usage.html`, `js/devices.js` | ~150 行 CSS + ~80 行 SVG + ~30 行 JS |
| P3 | 仿手写页 + 用量页 + Key 页 | `styles.css`, `handwriting.html`, `usage.html`, `keys.html`, `js/handwriting.js`, `js/keys.js` | ~120 行 CSS + ~40 行 JS |
| P4 | 细节打磨 + 回归测试 | 各文件微调 | ~50 行 |

### 验证方式

每批完成后：
1. 本地 `python -m uvicorn server:app --host 0.0.0.0 --port 8080` 启动
2. 浏览器逐一访问各页面，检查视觉效果和交互
3. Chrome DevTools 移动端模拟器测试响应式
4. 确认无 JS 控制台错误

## 6. 风险与约束

- **不引入新依赖**：所有效果纯 CSS + 原生 JS 实现
- **不修改后端**：仅改前端静态文件
- **不破坏现有功能**：增量添加，不删除现有样式
- **CSP 兼容**：所有内联样式需符合现有 CSP 策略（`style-src 'self' 'unsafe-inline'`）
- **性能**：动画仅使用 `transform` 和 `opacity`，避免触发重排

## 7. 成功标准

- [ ] 登录/注册页具有品牌感（玻璃拟态 + 渐变 + 动画）
- [ ] 所有按钮有 `active` 缩放反馈
- [ ] Toast 通知有类型区分（成功/警告/错误）
- [ ] 4 个空状态场景有 SVG 插画 + 引导文案
- [ ] 设备在线状态有脉冲指示
- [ ] 仿手写页表单控件与全局主题统一
- [ ] 用量统计卡片有主题色竖条
- [ ] API Key 页支持遮罩/复制
- [ ] 无 JS 控制台错误
- [ ] 移动端响应式正常
