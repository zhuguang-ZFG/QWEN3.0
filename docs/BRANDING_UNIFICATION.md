# 全平台品牌统一方案

> 日期: 2026-05-18
> 目标: chat/api/docs 全部统一为动力巢/LiMa 品牌
> 原则: 先文档后落地，superpowers 推进

---

## 一、当前问题清单

| 平台 | 问题 | 优先级 |
|------|------|--------|
| chat.donglicao.com | 默认 NextChat 标题/Logo，未定制 | P0 |
| chat.donglicao.com | 未验证是否能正常对话 | P0 |
| api.donglicao.com | new-api 默认品牌，需定制 | P1 |
| api.donglicao.com | 文档/教程需改为 LiMa 内容 | P1 |
| www.donglicao.com | quickstart 教程可能过时 | P2 |

---

## 二、chat.donglicao.com 修复

### 2.1 品牌定制（环境变量）

```bash
podman run -d --name nextchat \
  --restart=always -p 3002:3000 \
  -e OPENAI_API_KEY=sk-xxx \
  -e BASE_URL=http://127.0.0.1:3003 \
  -e CUSTOM_MODELS=-all,+lima-1.3,+deepseek-chat \
  -e DEFAULT_MODEL=lima-1.3 \
  -e NEXT_PUBLIC_DEFAULT_MODEL=lima-1.3 \
  -e HIDE_USER_API_KEY=1 \
  -e DISABLE_GPT4=1 \
  -e HIDE_BALANCE_QUERY=1 \
  -e SITE_TITLE="LiMa AI - 动力巢智能助手" \
  -e SITE_DESCRIPTION="由深圳市动力巢科技有限公司提供的免费AI编程助手" \
  yidadaa/chatgpt-next-web:latest
```

### 2.2 验证对话功能

```bash
# 测试 API 是否能正常响应
curl -X POST http://127.0.0.1:3003/v1/chat/completions \
  -H "Authorization: Bearer sk-xxx" \
  -H "Content-Type: application/json" \
  -d '{"model":"lima-1.3","messages":[{"role":"user","content":"你好"}]}'
```

---

## 三、api.donglicao.com 品牌定制

### 3.1 new-api 系统设置

通过 API 修改系统配置：
- 系统名称: "LiMa AI 开放平台"
- 页脚: "深圳市动力巢科技有限公司"
- Logo: 使用 LiMa 品牌 Logo
- 主题色: #6366f1 (紫色)
- 隐藏 GitHub 链接
- 首页公告: 欢迎使用 LiMa AI

### 3.2 渠道配置

确保 new-api 有可用渠道：
- 渠道名: LiMa Router
- 类型: OpenAI 兼容
- 地址: 本地路由 (http://本机:8000)
- 模型: lima-1.3

---

## 四、实施步骤

```
Step 1: 重建 NextChat 容器（加品牌环境变量）
Step 2: 验证 chat 对话功能
Step 3: new-api 品牌设置（系统名/Logo/公告）
Step 4: new-api 渠道配置（确保 API 可用）
Step 5: 验证全链路（chat → new-api → 后端模型）
```

---

## 五、验收标准

- [ ] chat.donglicao.com 标题显示 "LiMa AI"
- [ ] chat.donglicao.com 能正常对话
- [ ] api.donglicao.com 显示 "LiMa AI 开放平台"
- [ ] api.donglicao.com 无 GitHub/new-api 原始品牌
- [ ] 全链路对话测试通过
