# LiMa AI 开放平台修复计划

> 原则：文档先行 → 对比现状 → 逐步修复 → 验证每步

## 背景

api.donglicao.com 基于 New API (Calcium-Ion/new-api) 搭建，作为商业化 AI 模型市场。
当前状态：**平台不可用** — Channel 端口配置错误导致所有 API 调用失败。

## 当前架构

```
用户 → https://api.donglicao.com (nginx:443)
         → http://localhost:3003 (new-api podman 容器)
              → http://localhost:8080 (lima-router, FastAPI)
                   → 117 个 AI 后端
```

- 服务器: 47.112.162.80 (root / zhuguang110!)
- New API: /opt/new-api/ (Go 二进制 + SQLite)
- Lima Router: /opt/lima-router/ (systemd: lima-router)
- Nginx 配置: /etc/nginx/conf.d/donglicao.conf
- 管理 Token: lima-admin-token

---

## 审计发现

### P0 — 平台不可用（立即修复）

| # | 问题 | 影响 | 修复方案 |
|---|------|------|----------|
| 1 | Channel 端口错误 (8090/9090) | 所有 API 调用失败 | UPDATE channels SET base_url='http://localhost:8080' |
| 2 | lima-router 后端可能冷却 | 即使端口修正也可能 503 | 验证 lima-router 健康状态 |

### P1 — 商业化基础（本周）

| # | 问题 | 影响 | 修复方案 |
|---|------|------|----------|
| 3 | root 密码未知 | 无法登录管理后台 | sqlite3 重置 bcrypt hash |
| 4 | 首页内容为空 | 用户看到空白页 | 设置 HomePageContent (markdown) |
| 5 | docs_link → newapi.pro | 点文档跳到别人网站 | 清空或指向自有文档 |
| 6 | 无速率限制 | 可被恶意刷量 | 配置 global_api_rate_limit |
| 7 | 无邮箱验证 | 注册无门槛，易被滥用 | 配置 SMTP + email_verification |
| 8 | 品牌泄露 | passkey_display_name 等 | 数据库 UPDATE options |

### P2 — 商业运营（两周内）

| # | 问题 | 影响 | 修复方案 |
|---|------|------|----------|
| 9 | 无支付系统 | 无法收费 | 接入易支付/支付宝 |
| 10 | 无自有文档 | 用户不知道怎么用 | 写 API 使用指南 |
| 11 | 无数据库备份 | 数据丢失风险 | cron 定时 cp one-api.db |
| 12 | 无用户协议 | 法律风险 | 添加服务条款 |
| 13 | 无 OAuth | 注册体验差 | 接入 GitHub OAuth |
| 14 | 无订阅计划 | 无法按月收费 | 创建月卡/季卡 |

---

## 执行计划

### Phase 1: P0 修复（让平台能用）

#### Step 1.1: 修复 Channel 端口

操作前确认当前状态:
```bash
sqlite3 /opt/new-api/one-api.db "SELECT id,name,base_url,status FROM channels;"
```

修复:
```sql
sqlite3 /opt/new-api/one-api.db "UPDATE channels SET base_url='http://localhost:8080' WHERE id IN (1,2);"
```

验证修复后状态:
```bash
sqlite3 /opt/new-api/one-api.db "SELECT id,name,base_url FROM channels;"
# 预期: 所有 channel base_url = http://localhost:8080
```

#### Step 1.2: 确认 lima-router 健康
```bash
curl -s http://localhost:8080/health
curl -s -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test" \
  -d '{"model":"lima-1.3","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
```
预期: 返回 200 + AI 响应

#### Step 1.3: 重启 New API
```bash
podman restart new-api
sleep 5
podman ps | grep new-api
```

#### Step 1.4: 端到端验证（通过平台调用）
```bash
# 获取一个用户 token
TOKEN=$(sqlite3 /opt/new-api/one-api.db "SELECT key FROM tokens WHERE id=1;")
# 通过 New API 调用
curl -s -X POST http://localhost:3003/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"model":"lima-1.3","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
```
预期: 返回 AI 响应（非 do_request_failed）

#### Step 1.5: 外部验证
```bash
curl -s -X POST https://api.donglicao.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"model":"lima-1.3","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
```

---

### Phase 2: P1 修复（商业化基础）

#### Step 2.1: 重置 root 密码
```bash
# 生成 bcrypt hash (密码: zhuguang110!)
NEW_HASH=$(python3 -c "import bcrypt;print(bcrypt.hashpw(b'zhuguang110!',bcrypt.gensalt()).decode())")
sqlite3 /opt/new-api/one-api.db "UPDATE users SET password='$NEW_HASH' WHERE username='root';"
```
验证: 浏览器登录 api.donglicao.com，用 root / zhuguang110!

#### Step 2.2: 设置首页内容
```sql
UPDATE options SET value='# LiMa AI 开放平台

## 一个 Key，调用 13+ 顶级 AI 模型

支持 Claude、GPT-5、DeepSeek、Qwen、Gemini、Llama 等主流模型。
OpenAI 兼容 API，无缝接入 Cursor、Continue、VS Code 等 IDE。

### 快速开始
1. 注册账号获取 API Key
2. 设置 Base URL: `https://api.donglicao.com`
3. 选择模型开始调用

### 支持的模型
| 模型 | 供应商 | 特点 |
|------|--------|------|
| claude-opus-4-7 | Anthropic | 最强推理 |
| claude-sonnet-4 | Anthropic | 均衡性能 |
| gpt-5.4 | OpenAI | 最新旗舰 |
| deepseek-v4-pro | DeepSeek | 代码专家 |
| qwen3-coder | Qwen | 编程优化 |
| gemini-2.0-flash | Google | 极速响应 |
| llama-3.3-70b | Meta | 开源最强 |
| lima-1.3 | LiMa | 智能路由(自动选最优) |

### 定价
按 token 计费，注册即送免费额度。[查看详细定价](/pricing)
' WHERE key='HomePageContent';
```

#### Step 2.3: 修复品牌泄露
```sql
UPDATE options SET value='' WHERE key='docs_link';
UPDATE options SET value='LiMa AI' WHERE key='passkey_display_name';
UPDATE options SET value='LiMa AI 开放平台' WHERE key='SystemName';
UPDATE options SET value='https://www.donglicao.com/favicon.ico' WHERE key='Logo';
UPDATE options SET value='© 2025 动力巢科技 | LiMa AI 开放平台' WHERE key='Footer';
```

#### Step 2.4: 配置速率限制
```sql
UPDATE options SET value='60' WHERE key='global_api_rate_limit';
-- 每分钟 60 次请求上限
```

#### Step 2.5: 配置 Turnstile 验证码（防注册机器人）
需要 Cloudflare Turnstile site key + secret key:
```sql
UPDATE options SET value='true' WHERE key='TurnstileCheckEnabled';
UPDATE options SET value='SITE_KEY' WHERE key='TurnstileSiteKey';
UPDATE options SET value='SECRET_KEY' WHERE key='TurnstileSecretKey';
```

#### Step 2.6: 重启 New API 使配置生效
```bash
podman restart new-api
```

---

### Phase 3: P2 商业运营（后续）

#### Step 3.1: 数据库自动备份
```bash
# 添加 cron 任务，每天凌晨 3 点备份
echo "0 3 * * * cp /opt/new-api/one-api.db /opt/new-api/backups/one-api-\$(date +\%Y\%m\%d).db" | crontab -
mkdir -p /opt/new-api/backups
```

#### Step 3.2: 接入支付系统
- 选项 A: 易支付（国内，支持支付宝/微信）
- 选项 B: Stripe（国际）
- 需要在 options 中配置 PaymentProvider + 相关 Key

#### Step 3.3: 编写 API 文档
- 创建独立文档页面或使用 GitBook
- 内容: 认证方式、模型列表、请求格式、错误码、SDK 示例

#### Step 3.4: 订阅计划
```sql
INSERT INTO subscription_plans (name, price, quota, duration) VALUES
('基础版', 0, 500000, 0),
('专业版', 9900, 50000000, 30),
('企业版', 29900, 200000000, 30);
```

---

## 验收标准

| Phase | 验收条件 |
|-------|----------|
| P0 | 用户注册 → 获取 Key → 调用 API → 收到 AI 响应 |
| P1 | 首页有内容 + 管理员可登录 + 品牌无泄露 + 有限流 |
| P2 | 可充值 + 有文档 + 有备份 + 有订阅计划 |

---

## 风险与注意事项

1. **lima-router 后端冷却**: 修复端口后如果仍然 503，需要检查 /opt/lima-router/ 的环境变量
2. **New API 版本兼容**: 直接改 SQLite 可能与 Go 二进制的内存缓存不一致，改完必须重启
3. **支付系统**: 需要企业资质才能接入支付宝/微信商户
4. **SMTP**: 需要一个邮箱服务（如 Resend、SendGrid 或自建）
5. **数据安全**: one-api.db 包含用户密码和 API Key，备份需加密
