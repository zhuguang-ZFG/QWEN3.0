# Chat 功能完善方案

> 创建: 2026-05-22
> 前端: /var/www/chat/ (vanilla JS SPA, ~500行 app.js)
> 后端: lima-router (FastAPI, /v1/chat/completions)

---

## 功能 1: 多模型切换

### 现状
- state.mode = 'fast' 已存在但无 UI
- state.deepThinking = false 已存在但无 UI
- 后端通过 x-lima-mode header 或 model 字段区分

### 实现
前端 input-panel 上方加模式选择条:

```
[⚡快速] [🧠深度思考] [💻代码]
```

- 快速: model="lima-1.3" (默认，走 chat_fast 池)
- 深度思考: model="lima-1.3-thinking" (走 thinking 后端)
- 代码: model="lima-1.3-code" (走 code 池)

后端 server.py 已支持 model 字段路由，无需改动。

### 改动
- index.html: 在 .tool-buttons 中加 3 个 mode tab
- app.js: sendMessage() 中根据 state.mode 设置 model 字段

---

## 功能 2: 对话导出

### 实现
侧边栏对话项右键菜单或长按菜单加"导出"按钮。
点击后生成 Markdown 文件并触发下载。

格式:
```markdown
# 对话标题
> 导出时间: 2026-05-22 12:00

## User
消息内容

## Assistant
回复内容
```

### 改动
- app.js: 新增 exportConversation(id) 函数
- index.html: 对话项加导出按钮 (或 header 加导出按钮)

---

## 功能 3: 生图接入

### 现状
- smart_router.detect_image_intent() 存在
- generate_image() 已在瘦身中删除
- Pollinations 后端可用 (pollinations_openai 等)
- 前端无图片渲染逻辑（只有上传）

### 实现方案
不恢复 generate_image()，改用更简单的方式:
- 后端: 当 detect_image_intent() 为 True 时，直接返回 Pollinations 图片 URL
- 前端: 响应中的 markdown 图片语法 `![](url)` 自动渲染为 `<img>`

实际上 marked.js 已经支持渲染 `![alt](url)` 为 `<img>`。
所以只需要后端在检测到生图意图时，调用 Pollinations API 并返回 markdown 图片。

### 后端改动
server.py 或 routing_engine.py: 检测到 image intent 时，
调用 `https://image.pollinations.ai/prompt/{encoded_prompt}` 返回图片 URL。

### 前端改动
无需改动 — marked.js 已渲染图片。只需确认 CSP 允许 pollinations.ai 图片。

---

## 执行顺序

1. 多模型切换 (纯前端, 10min)
2. 对话导出 (纯前端, 10min)
3. 生图接入 (后端+验证, 20min)
