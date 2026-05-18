# LiMa AI 开放平台 — 产品升级设计文档

> 版本: v1.0
> 日期: 2026-05-18
> 状态: 待确认
> 目标: 从"技术后台"升级为"产品级开放平台"

---

## 一、现状问题

| 问题 | 影响 |
|------|------|
| one-api 原版 UI 像管理后台 | 用户第一印象差，不像正式产品 |
| GitHub 地址暴露 | 暴露技术实现，不专业 |
| 无网页版聊天体验 | 用户无法免费试用，转化率低 |
| 文档只有一页 quickstart | 开发者无法深入了解 API |
| 无 Playground | 开发者无法在线调试 |

---

## 二、目标产品形态

参考竞品：DeepSeek 开放平台、智谱 AI 开放平台、月之暗面

```
┌─────────────────────────────────────────────────────┐
│  www.donglicao.com          — 品牌官网（已有）        │
├─────────────────────────────────────────────────────┤
│  chat.donglicao.com         — 免费网页聊天（新增）    │
├─────────────────────────────────────────────────────┤
│  api.donglicao.com          — API 控制台（升级）      │
├─────────────────────────────────────────────────────┤
│  docs.donglicao.com         — API 文档站（新增）      │
│  或 www.donglicao.com/docs                           │
└─────────────────────────────────────────────────────┘
```

---

## 三、模块设计

### 3.1 网页版聊天 (chat.donglicao.com)

**方案选型：NextChat (ChatGPT-Next-Web)**

| 项目 | 内容 |
|------|------|
| 仓库 | github.com/ChatGPTNextWeb/NextChat |
| Stars | 80K+ |
| 部署 | Docker 一键 |
| 内存 | ~100MB |
| 特点 | 美观、支持多模型、Markdown渲染、代码高亮 |

**配置要点：**
- API 地址指向 one-api：`https://api.donglicao.com`
- 预设 API Key（免费体验用）
- 自定义标题/Logo/主题色
- 隐藏设置入口（防止用户改配置）

**部署：**
```bash
docker run -d --name nextchat \
  -p 3002:3000 \
  -e OPENAI_API_KEY=sk-free-trial-key \
  -e BASE_URL=https://api.donglicao.com \
  -e CUSTOM_MODELS=-all,+lima-1.3 \
  -e DEFAULT_MODEL=lima-1.3 \
  -e SITE_TITLE="LiMa AI" \
  -e HIDE_USER_API_KEY=1 \
  -e DISABLE_GPT4=1 \
  yidadaa/chatgpt-next-web
```

**域名：** chat.donglicao.com → Nginx 反代 → localhost:3002

---

### 3.2 API 控制台升级

**方案 A：保留 one-api + CSS 注入（当前）**
- 优点：零迁移成本
- 缺点：UI 仍然是管理后台风格，定制有限

**方案 B：换 new-api（推荐）**
- 仓库：github.com/Calcium-Ion/new-api
- 优点：UI 更现代、自带文档页、支持在线聊天
- 缺点：需要迁移数据（用户/Key/渠道）
- 迁移方式：new-api 兼容 one-api 数据库，直接切换二进制

**方案 C：自研前端 + one-api 后端**
- 优点：完全自定义
- 缺点：开发量大，不符合 superpowers 原则

**决策：方案 B（new-api）**，理由：
1. 兼容 one-api 数据库，迁移成本极低
2. UI 现代化，自带暗色主题
3. 内置文档页和在线聊天
4. 社区活跃，持续更新

---

### 3.3 API 文档站

**方案：扩展官网 + VitePress**

| 页面 | 内容 |
|------|------|
| /docs | 文档首页 |
| /docs/quickstart | 快速开始（已有，迁移过来） |
| /docs/api-reference | API 接口参考 |
| /docs/models | 模型列表和能力说明 |
| /docs/pricing | 定价详情 |
| /docs/sdk | SDK 下载（Python/TS） |
| /docs/faq | 常见问题 |

**或者直接用 new-api 自带的文档功能**（更轻量）。

---

## 四、域名规划

| 域名 | 用途 | 部署方式 |
|------|------|----------|
| www.donglicao.com | 品牌官网 | 静态文件 (Next.js) |
| api.donglicao.com | API 控制台 | new-api (Docker) |
| chat.donglicao.com | 免费网页聊天 | NextChat (Docker) |
| docs.donglicao.com | API 文档 | new-api 内置 或 VitePress |

需要新增 DNS 记录：
- `chat` A 记录 → 47.112.162.80

---

## 五、用户体验流程

```
新用户首次访问:
  www.donglicao.com → 了解产品 → 点击"免费体验"
    │
    ├─→ chat.donglicao.com → 直接聊天（无需注册）
    │
    └─→ api.donglicao.com → 注册 → 获取 Key → 接入 IDE

开发者流程:
  www.donglicao.com/quickstart → 3分钟接入指南
    → api.donglicao.com → 注册获取 Key
    → 配置 IDE → 开始使用

付费用户:
  api.donglicao.com → 登录 → 充值 → 升级套餐
```

---

## 六、实施步骤

### Sprint 1：NextChat 部署（1小时）
```
1. 云端 docker pull nextchat
2. 配置环境变量（API地址、免费Key、品牌）
3. Nginx 配置 chat.donglicao.com 反代
4. DNS 添加 chat A 记录
5. 验证：访问 chat.donglicao.com 可以聊天
```

### Sprint 2：new-api 替换（2小时）
```
1. 备份当前 one-api 数据库
2. 下载 new-api 二进制
3. 用同一数据库启动 new-api
4. 验证：用户/Key/渠道数据完整
5. 切换 Nginx 指向 new-api 端口
6. 品牌定制（Logo/名称/主题色）
```

### Sprint 3：文档完善（半天）
```
1. 编写 API Reference（模型列表、参数说明、错误码）
2. 编写 SDK 使用指南
3. 编写 FAQ
4. 部署文档（new-api 内置 或 VitePress）
```

---

## 七、资源评估

| 资源 | 当前 | 新增 | 总计 |
|------|------|------|------|
| 内存 | one-api ~200MB | NextChat ~100MB, new-api ~250MB | ~550MB |
| 磁盘 | ~500MB | +200MB | ~700MB |
| CPU | 低 | 低 | 2vCPU 够用 |
| 端口 | 3001 | 3002(chat), 3003(new-api) | 3个 |

2GB 服务器可以承载，但比较紧张。如果同时跑 NextChat + new-api，建议：
- 关闭 one-api（被 new-api 替代）
- 或升级到 4GB 内存

---

## 八、验收标准

- [ ] chat.donglicao.com 可免费聊天，无需注册
- [ ] api.donglicao.com UI 现代化，无 GitHub 链接
- [ ] 文档页包含完整 API 参考
- [ ] 新用户注册到首次调用 < 3 分钟
- [ ] 移动端适配正常

---

## 九、风险与应对

| 风险 | 应对 |
|------|------|
| new-api 迁移数据丢失 | 先备份 SQLite 数据库 |
| 2GB 内存不够 | 先关 one-api，或升级服务器 |
| NextChat 免费 Key 被滥用 | 限制单 IP 调用频率 |
| chat 域名 SSL | Let's Encrypt 自动签发 |
| new-api 不兼容 | 保留 one-api 二进制作为回退 |
