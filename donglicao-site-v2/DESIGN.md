# Design

> 视觉系统文档，遵循 [Google Stitch DESIGN.md format](https://stitch.withgoogle.com/docs/design-md/format/)。
> 每个 impeccable 命令在执行前都会读取本文件与 PRODUCT.md。

## Register

brand — 设计本身是产品。访客的印象就是被制造的东西。

## Aesthetic Lane

**深空技术诗意（Deep-space technical poetics）**

参考系：Vercel 纯黑克制 × Klim 几何线条 × NASA 数据可视化。不是 Stripe 紫白、不是 Linear 渐变、不是编辑杂志衬线风。LiMa 的品牌锚点是「量子星云」——深色为宇宙底，cyan/紫为星光，几何线条为轨道路径。

一句话竞品描述测试：「又一个深色科技 SaaS 官网」——如果不做差异化就会落入这个模态。差异化锚点：**设备实拍 + 物理隐喻几何 + 单色高光克制**。

## Color

### 策略：Committed（承诺色）

cyan 是 LiMa 的品牌色，不是点缀。它在 hero、CTA、focus、selection、active 状态中承担引导职责。但 committed 不等于 drenched——不做全屏 cyan 渐变，cyan 只在「需要引导视线」的触点出现。

### Palette

```
/* 语义色 */
--background: #07070f        /* 深空底色，非纯黑，带微蓝 */
--foreground: #e2e8f0        /* slate-200，主文本 */
--accent: #06b6d4            /* cyan-500，品牌高光 */

/* 扩展色阶（Tailwind 原生，已在使用） */
--cyan-400: #22d3ee          /* hover/active 高光 */
--cyan-500: #06b6d4          /* 主 accent */
--slate-50: #f8fafc          /* 标题极亮 */
--slate-200: #e2e8f0         /* 正文 */
--slate-300: #cbd5e1         /* 次要文本 */
--slate-400: #94a3b8         /* 辅助文本 */
--slate-900: #0f172a         /* 卡片底 */
--purple-500: #8b5cf6        /* 第二高光，仅 SVG 装饰 */

/* 语义状态 */
--success: #10b981           /* emerald-500 */
--warning: #f59e0b           /* amber-500 */
--error: #ef4444             /* red-500 */
```

### 对比度

- slate-200 (#e2e8f0) on #07070f：对比度 ~13:1，远超 WCAG AAA 7:1。
- cyan-400 (#22d3ee) on #07070f：对比度 ~9:1，满足 AAA。
- slate-400 (#94a3b8) on #07070f：对比度 ~6:1，满足 AA 大文本，仅用于辅助文本。

### 禁忌

- 紫蓝渐变按钮（AI slop 头号特征）。
- 灰字压彩底（slate-400 on cyan tint）——可读性差。
- 纯黑 #000 背景——太死板，#07070f 有微蓝呼吸感。

## Typography

### Font

当前：`system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`

**决策**：保留 system-ui 作为 UI 字体（性能零成本、跨平台一致）。品牌展示字待定——不强行引入 Inter/DM Sans 等 reflex-reject 字体。如未来需要展示字，从 Pangram Pangram / Future Fonts / Velvetyne 寻找有「技术诗意」气质的几何无衬线或等宽字体。

### Scale

```
/* 流体标题，clamp() 响应式 */
--text-hero: clamp(2.25rem, 5vw, 3.75rem)     /* h1, 36-60px */
--text-h2: clamp(1.875rem, 3.5vw, 2.5rem)     /* h2, 30-40px */
--text-h3: clamp(1.5rem, 2.5vw, 1.875rem)     /* h3, 24-30px */
--text-body: 1.125rem                          /* 18px, 正文 */
--text-small: 0.875rem                         /* 14px, 辅助 */

/* 比率 ~1.25-1.33，brand register 推荐的鲜明对比 */
```

### 行高

深色背景 + 浅色文字：line-height 加 0.05-0.1。正文 1.75，标题 1.2-1.3。

## Components

### 按钮

```
/* 主 CTA：实心 cyan，深色文字 */
.btn-primary: bg-cyan-500 text-slate-950 rounded-full px-6 py-3
  hover: bg-cyan-400
  focus-visible: outline 2px cyan-400 offset 2px

/* 次 CTA：描边，hover 转 cyan */
.btn-secondary: border border-white/10 text-slate-200 rounded-full px-6 py-3
  hover: border-cyan-500/50 text-cyan-400

/* 禁止：紫蓝渐变、阴影发光、emoji icon */
```

### 卡片

```
/* 产品卡 / 技术卡 */
.card: bg-slate-900/50 border border-white/10 rounded-2xl
  hover: border-cyan-500/30 (微高光，不发光)

/* 禁止：卡片套卡片、灰底压灰底 */
```

### 标签（Tag）

```
/* 技术标签 */
.tag: rounded-full border border-white/10 bg-white/5 px-3 py-1 text-sm text-slate-300
```

### 装饰几何

SVG 同心圆虚线（量子轨道意象）——当前 Hero 已使用，保持。用于 hero/section 分隔，不铺满全页。

## Layout

### 间距

```
--space-section: clamp(5rem, 10vw, 8rem)    /* section 间距 */
--space-block: clamp(2rem, 4vw, 3rem)       /* 区块内间距 */
max-width: 7xl (1280px)                       /* 内容容器 */
```

### 网格

- Hero：`lg:grid-cols-2`（文案 + 可视化）。
- Products：`grid md:grid-cols-3`（三产品并列）。
- Pricing：`grid md:grid-cols-3`（三档套餐）。
- 卡片网格用 `repeat(auto-fit, minmax(280px, 1fr))` 实现无断点响应。

### 禁忌

- 三栏等高 feature 卡 + emoji icon（AI slop）。
- 居中堆叠一切（缺乏不对称张力）。

## Motion

### 原则

- `prefers-reduced-motion` 全局尊重（globals.css 已实现）。
- Reveal 组件：IntersectionObserver 触发 fade-up，duration 400ms ease-out。
- Hover 过渡：150-200ms。
- 禁止：入场编排序列、装饰性粒子动画、无限循环霓虹。

## Imagery

### 原则（brand register 硬要求）

- **设备实拍是核心**：绘图机在画、写字机在写、数字人在动——每页都应有真实设备图片或运行可视化。
- Hero 已有 `hero.webp`（量子星云可视化），保留。
- 产品页（product-draw/product-write/product-human）必须有设备实拍或运行截图。
- 禁止：用纯色 div 替代图片、用抽象图标替代设备、零图片页面。

## AI Slop 检测清单（impeccable 44 条简化版）

- [ ] 无 Inter 字体铺满
- [ ] 无紫蓝渐变按钮
- [ ] 无卡片套卡片
- [ ] 无灰字压彩底
- [ ] 无圆角图标方块当 feature icon
- [ ] 无 emoji 当 icon
- [ ] 无三栏等高 feature 卡 + 居中堆叠
- [ ] 无装饰性粒子动画
- [ ] 有真实设备图片
- [ ] 有不对称构图张力
- [ ] focus-visible 样式定义
- [ ] prefers-reduced-motion 尊重
- [ ] 对比度 ≥ 4.5:1
