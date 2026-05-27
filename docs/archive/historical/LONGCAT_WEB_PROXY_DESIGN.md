# LongCat 网页版逆向代理设计

## 概述

将 LongCat 网页版 (longcat.chat) 的免费 AI 聊天接口逆向为 OpenAI 兼容 API，接入 LiMa 路由系统。

## 逆向分析结果

### 核心端点

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/v1/session-create` | POST | 创建新会话 |
| `/api/v1/chat-completion-V2` | POST | 聊天补全（SSE流式） |
| `/api/v1/chat-reconnect` | POST | 重连断开的流 |
| `/api/v1/chat-regenerate-V2` | POST | 重新生成回复 |
| `/api/v1/configList` | GET | 获取模型配置 |
| `/api/v1/session-list` | POST | 会话列表 |
| `/api/v1/session-delete` | GET | 删除会话 |
| `/api/v1/query-route` | POST | 查询路由 |

### 请求格式

```json
// POST /api/v1/chat-completion-V2
{
  "query": "用户消息内容",
  "parentId": "",
  "conversationId": "会话ID"
}
```

### SSE 响应格式

事件类型 (vD enum):
- `CONTENT` — 正文内容（增量）
- `REASON` / `THINK` — 推理/思考过程
- `SEARCH` / `GENERAL_SEARCH` / `BROWSE_SEARCH` — 搜索结果
- `CODE` / `CODE_STATUS` — 代码执行
- `FINISH` — 完成标记
- `EVENT_ERROR` — 错误

事件状态 ($P enum):
- `PROCESSING` — 生成中
- `FINISHED` — 完成

聊天类型 (vo enum):
- 普通聊天（默认）
- `agent` — Agent 模式
- `heavy` — 深度思考
- `deep_research` — 深度研究
- `image` — 图片生成
- `video` — 视频生成

### 认证机制

1. **Cookie**: 美团 Passport 登录后的 session cookie
2. **H5guard**: `mtgsig` 签名头，由前端 JS SDK 生成
3. **Headers**: `X-Requested-With: XMLHttpRequest`, `X-Client-Language: zh`

## 架构设计

```
┌─────────────────────────────────────────────────┐
│  LiMa Router (routing_engine.py)                │
│  ↓ call_fn                                      │
├─────────────────────────────────────────────────┤
│  longcat_web_proxy.py (本地代理 :4505)           │
│  ┌───────────────────────────────────────────┐  │
│  │ OpenAI API → LongCat Web API 转换         │  │
│  │ Cookie 管理 + 自动刷新                     │  │
│  │ SSE 解析 → OpenAI 流式格式                 │  │
│  └───────────────────────────────────────────┘  │
├─────────────────────────────────────────────────┤
│  longcat.chat (美团 LongCat 网页版)             │
└─────────────────────────────────────────────────┘
```

## 实现方案

### 1. Cookie 中转代理（主路径）

- 用户从浏览器 DevTools 复制 Cookie
- 存储在环境变量 `LONGCAT_WEB_COOKIE` 或文件 `~/.longcat_cookie`
- 代理带 Cookie 转发请求

### 2. Playwright 自动刷新（备用）

- Cookie 失效时（401）自动启动 Playwright
- 用已保存的登录态刷新 Cookie
- 更新本地 Cookie 存储

### 3. H5guard 绕过策略

- 方案A: 直接发请求不带 mtgsig（测试是否严格校验）
- 方案B: 从浏览器 session 中提取完整 headers
- 方案C: Playwright 中执行请求（自动带签名）

## 模型映射

| 网页版功能 | 对应 chatType | LiMa 后端名 |
|-----------|--------------|-------------|
| 普通聊天 | (default) | `longcat_web` |
| 深度思考 | `heavy` | `longcat_web_think` |
| 深度研究 | `deep_research` | `longcat_web_research` |

## 文件结构

```
D:/GIT/
├── longcat_web_proxy.py    # 主代理服务 (FastAPI, port 4505)
├── longcat_cookie_mgr.py   # Cookie 管理 + Playwright 刷新
└── docs/LONGCAT_WEB_PROXY_DESIGN.md  # 本文档
```

## 接入 backends.py

```python
'longcat_web': {
    'url': 'http://localhost:4505/v1/chat/completions',
    'key': 'local',
    'model': 'longcat-web',
    'fmt': 'openai',
    'timeout': 60
},
'longcat_web_think': {
    'url': 'http://localhost:4505/v1/chat/completions',
    'key': 'local',
    'model': 'longcat-web-think',
    'fmt': 'openai',
    'timeout': 120
},
```

## 风险与限制

1. Cookie 有效期未知（可能数小时到数天）
2. H5guard 可能升级导致请求被拒
3. 美团可能检测异常流量并封号
4. 网页版可能有每日对话次数限制
