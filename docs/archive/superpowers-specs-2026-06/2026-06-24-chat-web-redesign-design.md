# chat-web 按 taste-skill 重塑设计文档

日期：2026-06-24

## 背景

LiMa 官网 `donglicao-site/` 已按 `taste-skill` 完成重塑并部署。用户同意继续对 `chat-web/`（`chat.donglicao.com`）应用同一套设计语言，使聊天控制台与官网视觉一致。

## 目标

- 统一 `chat-web` 与官网的视觉系统：Geist 字体、暗色星云主题、单一 cyan 强调色。
- 保持现有功能不变：设备选择、聊天流、图片生成、API Key 设置、语音通话入口。
- 遵守 taste-skill 硬约束：零 em-dash、无 `window.addEventListener('scroll')`、无三列等卡、CTA 意图不重复。

## 范围

| 文件 | 处理方式 |
|------|----------|
| `chat-web/index.html` | 调整结构：引入 Geist 字体、统一标题/按钮文案、保持 DOM id 不变 |
| `chat-web/styles.css` | 重写视觉层：替换颜色 token、字体、圆角、阴影、卡片样式；保留布局骨架 |
| `chat-web/chat-ui.js` | 仅更新与 DOM 相关的文案/类名；逻辑不变 |
| `chat-web/chat-messages.js` | 不动逻辑；必要时调整类名以匹配新 CSS |
| `chat-web/chat-api.js` | 不改动 |
| `chat-web/voice-call.html` | 仅同步颜色和字体到 cyan/Geist；结构不变 |
| `chat-web/solar-system.js` | 仅调整星球/轨道颜色到 cyan/青色系 |
| `chat-web/icons.svg` | 不改动 |

## 设计决策

1. **颜色**：强调色从 `#3b82f6` 蓝色统一为 `#06b6d4` cyan，与官网一致；背景保持 `#07070f`。
2. **字体**：正文与标题统一使用 Geist Sans 可变字体，回退系统字体。
3. **Hero/欢迎屏**：保留居中欢迎画布，但文案简化为 taste-skill 风格，减少文本元素。
4. **快速操作卡**：从 4 卡 grid 改为 2x2 bento 风格，但功能点击不变。
5. **侧边栏**：保留设备列表和历史，视觉更精致（玻璃态、细边框、cyan 状态点）。
6. **背景**：保留 solar-system Canvas，但颜色从蓝色/紫色调整为 cyan/星云紫。
7. **语音通话页**：改为与控制台一致的颜色，避免用户在页面跳转时感到割裂。

## 风险与规避

- **功能回归风险**：`chat-api.js` 与 DOM id 绑定紧密，不改动 JS 可最大限度降低风险。
- **CSS 破坏风险**：保留原有布局骨架和 class 名，仅替换 token 和具体数值。
- **CSP 风险**：仍只使用 `self` 和已有 CDN/域名；新增 Geist 字体 CDN 需在 CSP 中放行 `font-src`。

## 验证

- 本地 `http.server` 检查 `index.html`、`voice-call.html` 可访问且控制台无报错。
- 部署到 VPS `/var/www/chat/` 后，`curl -I https://chat.donglicao.com` 返回 200。
- 页面文本命中新设计特征：Geist 字体加载、cyan 强调色类名。

## 后续可选项

- 若用户希望，`voice-call.html` 可进一步做结构重塑。
- 当前视觉素材为代码生成/SVG，无需替换占位图。
