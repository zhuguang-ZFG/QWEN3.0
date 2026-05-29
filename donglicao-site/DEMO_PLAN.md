# 官网交互式 Demo 改造方案 — Superpowers 原则

## 目标

将 www.donglicao.com 主页的静态服务展示改为**可交互的 Live Demo**，
用户 30 秒内即可体验 AI 能力。所有生成内容带 DongLiCao 品牌水印。

## 可行性分析

| 能力 | 免费 API | 水印方案 | 可行性 |
|------|----------|----------|--------|
| AI 图片生成 | Pollinations.ai（无需 key，无限制） | Canvas 叠加半透明水印 | ✅ 完全可行 |
| AI 对话 | 自有 api.donglicao.com | 回答区底部品牌标识 | ✅ 完全可行 |
| AI 视频生成 | 无免费稳定 API | 方案 B：图片序列动画 | ⚠️ 替代方案 |

### 视频生成替代方案

免费视频生成 API 现状：不存在类似 Pollinations 的免费无限视频生成服务。
替代方案（按推荐度排序）：

1. **图片动画化**：生成 4 张连续图片，用 CSS 动画串成"伪视频"效果
2. **图片 + Ken Burns**：生成 1 张图，用缩放/平移动画模拟视频感
3. **标记为"即将上线"**：保留 UI 但显示 Coming Soon

推荐方案 1 — 用户感知上接近视频，实际是 4 张图的幻灯片动画。

## 技术实现

### 架构

```
nginx sub_filter 注入 → lima-demo.js
                         ├── 图片生成 Demo（Pollinations.ai + Canvas 水印）
                         ├── 对话 Demo（自有 LiMa API）
                         └── 视频 Demo（4 图序列动画 + 水印）
```

### 水印实现

```javascript
// Canvas 水印叠加（图片/视频帧）
function addWatermark(imgElement) {
  const canvas = document.createElement('canvas');
  canvas.width = imgElement.naturalWidth;
  canvas.height = imgElement.naturalHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(imgElement, 0, 0);

  // 右下角品牌水印
  ctx.font = 'bold 20px system-ui';
  ctx.fillStyle = 'rgba(255,255,255,0.6)';
  ctx.textAlign = 'right';
  ctx.fillText('DongLiCao.com', canvas.width - 20, canvas.height - 20);

  // 左下角 Logo 文字
  ctx.font = '14px system-ui';
  ctx.fillStyle = 'rgba(99,102,241,0.7)';
  ctx.textAlign = 'left';
  ctx.fillText('Powered by LiMa AI', 20, canvas.height - 20);

  return canvas.toDataURL('image/png');
}
```

### Demo 组件设计

#### 1. 图片生成 Demo

**UI 设计**：
- 毛玻璃卡片，圆角 16px，紫色边框发光
- 输入框 + "生成" 按钮 + 预设标签（太空猫/赛博朋克/山水画/机器人）
- 生成后全屏展示，右下角 "DongLiCao.com" 水印 + 左下角 "Powered by LiMa AI"
- 支持下载（带水印）

**API**：`https://image.pollinations.ai/prompt/{desc}?width=1024&height=1024&nologo=true`

**水印**：Canvas 叠加，不可去除（嵌入像素层）

#### 2. 对话 Demo

**UI 设计**：
- 迷你聊天窗口（3 条消息可见），底部输入框
- 消息气泡：用户右侧蓝色，AI 左侧紫色渐变
- 底部固定 "Powered by LiMa AI | DongLiCao.com"
- 预设问题按钮：写代码 / 解释概念 / 翻译

**API**：`POST https://api.donglicao.com/v1/chat/completions`
- model: "lima"
- 限制 max_tokens: 200（Demo 用，节省配额）
- 需要一个公开的 Demo API Key

#### 3. 视频 Demo（图片序列动画）

**UI 设计**：
- 输入描述 → 生成 4 张连续场景图片
- 用 CSS transition 做淡入淡出幻灯片（每张 2 秒）
- 右下角水印 "DongLiCao.com"
- 标注 "AI 动态图像 · Beta"

**实现**：
- 生成 4 张图：原始描述 + "frame 1/2/3/4, cinematic sequence"
- 并行请求 Pollinations.ai
- 每张图 Canvas 加水印后播放

---

## 注入方式

通过 nginx sub_filter 注入 `lima-demo.js`（与 contact-fix.js 同理）：

```nginx
sub_filter '</body>' '<script src="/lima-demo.js"></script></body>';
```

`lima-demo.js` 负责：
1. 检测页面中的服务展示区域（#how-to-use 或 service 图片附近）
2. 在其下方插入 3 个 Demo 卡片
3. 所有交互逻辑自包含

---

## 视觉风格

- 背景：#0E0C15（与官网一致）
- 卡片：backdrop-filter: blur(20px)，border: 1px solid rgba(99,102,241,0.2)
- 按钮：渐变紫 #6366f1 → #818cf8
- 文字：#e2e8f0（主）/ #94a3b8（次）
- 动画：Intersection Observer 触发 fadeInUp
- 响应式：移动端单列，桌面端三列

---

## 水印规格

```
┌─────────────────────────────────────┐
│                                     │
│         [生成的图片/视频帧]          │
│                                     │
│  Powered by LiMa AI    DongLiCao.com│
└─────────────────────────────────────┘
```

- 字体：bold 18px system-ui
- 颜色：rgba(255,255,255,0.6)（白色半透明）
- 位置：右下角 + 左下角
- 不可通过 CSS 隐藏（嵌入 Canvas 像素）

---

## 实施步骤

1. 创建 `lima-demo.js`（~300 行）
2. 修改 nginx 配置注入脚本
3. 创建 Demo 专用 API Key（限流：10 次/分钟）
4. 部署并验证
5. 移动端适配测试

---

## 依赖

- Pollinations.ai — 图片生成（免费，无限制，稳定 2 年+）
- 自有 LiMa API — 对话（已有）
- Web Speech API — 语音（浏览器原生）
- 无外部 JS 库依赖
