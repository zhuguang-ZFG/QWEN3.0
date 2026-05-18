# LiMa AI 平台 — 支付集成设计文档

> 版本: v1.0
> 日期: 2026-05-18
> 状态: 待确认
> 前置条件: 企业网商银行账户

---

## 一、目标

用户在 api.donglicao.com 自助扫码付款，系统自动充值 quota，无需管理员手动操作。

---

## 二、技术选型

### 支付宝当面付（扫码支付）

| 项目 | 内容 |
|------|------|
| 产品 | 支付宝开放平台 → 电脑网站支付 |
| 资质 | 企业网商银行对公账户 |
| 费率 | 0.6% |
| 到账 | T+1 到网商银行 |
| 接口 | alipay.trade.page.pay（PC扫码） |
| 回调 | 异步通知 notify_url |
| SDK | alipay-sdk-python 或直接 RSA2 签名 |

### 为什么不用其他方案

| 方案 | 不选原因 |
|------|----------|
| 虎皮椒 | 多一层中间商，费率高，到账慢 |
| 卡密 | 用户体验差，无法自助 |
| 微信支付 | 需要额外申请，先做支付宝 |
| Stripe | 国内用户不方便 |

---

## 三、架构设计

```
用户点击"充值"
  │
  ▼
┌─────────────────────────────────────────┐
│  one-api 前端（充值页面）                 │
│  选择套餐 → 生成订单号                    │
└────────────────┬────────────────────────┘
                 │ POST /api/topup/alipay
                 ▼
┌─────────────────────────────────────────┐
│  支付中间件 (pay_gateway.py)             │
│  ├─ 生成支付宝订单                       │
│  ├─ RSA2 签名                           │
│  └─ 返回支付页面 URL / 二维码             │
└────────────────┬────────────────────────┘
                 │ 用户扫码/网页支付
                 ▼
┌─────────────────────────────────────────┐
│  支付宝服务器                            │
│  ├─ 扣款成功                            │
│  └─ 异步通知 notify_url                  │
└────────────────┬────────────────────────┘
                 │ POST /api/topup/callback
                 ▼
┌─────────────────────────────────────────┐
│  回调处理 (pay_gateway.py)               │
│  ├─ 验签（RSA2 公钥验证）                │
│  ├─ 校验金额、订单状态                    │
│  ├─ 调用 one-api 充值接口                │
│  └─ 记录交易日志                         │
└─────────────────────────────────────────┘
```

---

## 四、套餐与 Quota 映射

| 套餐 | 价格 | 充值 Quota | 约等于 |
|------|------|-----------|--------|
| 体验包 | ¥9.9 | 1,000,000 | ~200次调用 |
| 基础月卡 | ¥29 | 5,000,000 | ~1000次/月 |
| 专业月卡 | ¥99 | 20,000,000 | ~4000次/月 |
| 充值100 | ¥100 | 25,000,000 | 自定义 |

Quota 换算规则: ¥1 = 250,000 quota（可调）

---

## 五、接口设计

### 5.1 创建支付订单

```
POST /api/topup/alipay
Headers: Authorization: Bearer <user_token>
Body: { "amount": 29, "package": "basic_monthly" }
Response: { "pay_url": "https://openapi.alipay.com/...", "order_id": "LM20260518..." }
```

### 5.2 支付宝异步回调

```
POST /api/topup/callback
Body: (支付宝标准异步通知参数)
Response: "success" (固定，告知支付宝已收到)
```

### 5.3 订单查询

```
GET /api/topup/orders
Headers: Authorization: Bearer <user_token>
Response: { "orders": [...] }
```

---

## 六、安全设计

| 风险 | 防护 |
|------|------|
| 回调伪造 | RSA2 验签，验证支付宝公钥 |
| 重复通知 | 订单号幂等，已处理的订单跳过 |
| 金额篡改 | 回调中校验金额与订单金额一致 |
| 并发充值 | 数据库事务 + 乐观锁 |
| 订单超时 | 15分钟未支付自动关闭 |

---

## 七、数据模型

```sql
CREATE TABLE topup_orders (
    id TEXT PRIMARY KEY,           -- 订单号 LM{timestamp}{random}
    user_id INTEGER NOT NULL,      -- one-api 用户ID
    amount REAL NOT NULL,          -- 支付金额（元）
    quota INTEGER NOT NULL,        -- 充值额度
    status TEXT DEFAULT 'pending', -- pending/paid/failed/expired
    trade_no TEXT,                 -- 支付宝交易号
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    paid_at DATETIME,
    notify_raw TEXT                -- 原始回调数据（审计用）
);
```

---

## 八、实现文件

| 文件 | 职责 |
|------|------|
| `D:/GIT/pay_gateway.py` | 支付网关主文件（FastAPI） |
| `D:/GIT/pay_config.py` | 支付宝配置（AppID、密钥路径） |
| `D:/GIT/pay_orders.db` | SQLite 订单数据库 |
| 云端 Nginx | 反代 /api/topup/* → pay_gateway |

---

## 九、部署方式

pay_gateway.py 运行在本地（与 server.py 同机），通过 frp 隧道暴露。

```
云端 Nginx → /api/topup/* → frp 隧道 → 本地 pay_gateway:8089
```

或者直接部署在云端（更稳定，支付回调不依赖隧道）：
```
云端 Nginx → /api/topup/* → 本地 pay_gateway:8089 (Docker)
```

**推荐方案：部署在云端**，因为支付宝回调需要稳定可达的 URL，不能依赖 frp 隧道。

---

## 十、开发步骤

```
Step 1: 支付宝开放平台注册 + 创建应用 + 获取密钥
Step 2: 编写 pay_gateway.py（创建订单 + 回调处理）
Step 3: 对接 one-api 充值 API（内部调用）
Step 4: 云端部署 + Nginx 配置
Step 5: 沙箱环境测试
Step 6: 正式环境上线
```

---

## 十一、前置准备（需要用户操作）

- [ ] 登录 open.alipay.com，用企业账号注册开发者
- [ ] 创建网页应用，获取 AppID
- [ ] 生成 RSA2 密钥对，上传公钥到支付宝
- [ ] 开通"电脑网站支付"能力
- [ ] 提供 AppID + 应用私钥文件路径

---

## 十二、验收标准

- [ ] 用户在 one-api 界面点击充值，跳转支付宝付款页
- [ ] 支付成功后 5 秒内 quota 自动到账
- [ ] 重复回调不会重复充值
- [ ] 订单记录可查询
- [ ] 支付失败有友好提示
