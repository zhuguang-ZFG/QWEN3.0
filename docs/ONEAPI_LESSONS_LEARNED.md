# one-api 集成经验教训

> 日期: 2026-05-20
> 作者: 自动生成
> 目的: 防止下次犯同样的错误

---

## 一、核心教训

### 1. one-api type=8 (Custom) 追加 `/v1/chat/completions`

**错误假设：** type=8 只追加 `/chat/completions`
**实际行为：** type=8 追加 `/v1/chat/completions`

**正确配置规则：**
```
最终 URL = base_url + /v1/chat/completions

所以 base_url 应该是去掉 /v1 的根路径：
  siliconflow: https://api.siliconflow.cn      (不是 /v1)
  groq:        https://api.groq.com/openai      (不是 /v1)
  deepseek:    https://api.deepseek.com         (不是 /v1)
  cerebras:    https://api.cerebras.ai          (不是 /v1)
  openrouter:  https://openrouter.ai/api        (不是 /v1)
```

**验证方法：** 用 echo server 捕获 one-api 实际发出的请求路径。

---

### 2. PUT 更新渠道会清空 Key

**错误操作：** GET 渠道列表 → 修改字段 → PUT 回去
**实际行为：** GET API 出于安全不返回 key 字段，PUT 时空 key 覆盖了原值

**正确做法：** 每次 PUT 更新渠道时，必须重新设置 key 字段：
```python
ch["key"] = os.environ.get("PROVIDER_API_KEY", "")
api_put("/api/channel/", ch)
```

---

### 3. 非标准路径的厂商无法用 type=8

**无法通过 one-api 的厂商（路径不兼容）：**
| 厂商 | 实际路径 | 问题 |
|------|----------|------|
| 智谱 | /api/paas/v4/chat/completions | type=8 拼出 /v1 而非 /v4 |
| GitHub Models | /chat/completions (无 /v1) | type=8 多加了 /v1 |
| 百度千帆 | 特殊认证 (bce-v3) | 非标准 Bearer token |

**解决方案：** 这些厂商保持直连 fallback，不走 one-api。

---

### 4. 验证 Key 有效性时必须走完整调用链

**错误做法：** 直接 curl 测试（不走代理、不走降级）
**正确做法：** 通过 smart_router.py 的 `call_api()` 测试

原因：
- 被墙端点需要 GFW 代理
- 某些端点需要特殊 header
- smart_router 有错误处理和降级逻辑

---

### 5. one-api 容器需要配置代理

被墙端点（Google, Mistral）需要在容器启动时配置代理：
```bash
podman run --name one-api -d \
  -e HTTP_PROXY=http://host.containers.internal:7897 \
  -e HTTPS_PROXY=http://host.containers.internal:7897 \
  -e NO_PROXY=localhost,127.0.0.1,国内域名... \
  ...
```

---

## 二、one-api 渠道配置速查表

### 能通过 one-api 的渠道 (type=8, base 去掉 /v1)

| 渠道 | base_url | 验证状态 |
|------|----------|----------|
| groq | `https://api.groq.com/openai` | ✅ 221ms |
| cerebras | `https://api.cerebras.ai` | ✅ 367ms |
| deepseek | `https://api.deepseek.com` | ✅ 607ms |
| chat-ubi | `https://ch.at` | ✅ 1850ms |
| pollinations | `https://text.pollinations.ai/openai` | ✅ 280ms |
| llm7 | `https://api.llm7.io` | ✅ 2467ms |
| siliconflow | `https://api.siliconflow.cn` | Key 余额不足 |
| openrouter | `https://openrouter.ai/api` | 限流 |
| nvidia | `https://integrate.api.nvidia.com` | GFW 超时 |
| aliyun | `https://dashscope.aliyuncs.com/compatible-mode` | 需 enable_thinking=false |
| tencent | `https://api.hunyuan.cloud.tencent.com` | 待验证 |
| chinamobile | `https://maas.gd.chinamobile.com:36007/ai/uifm/open` | 响应格式问题 |
| uncloseai-hermes | `https://hermes.ai.unturf.com` | 待验证 |
| uncloseai-qwen | `https://qwen.ai.unturf.com` | 待验证 |

### 无法通过 one-api 的渠道（仅直连 fallback）

| 渠道 | 原因 | 解决方案 |
|------|------|----------|
| zhipu | 路径 /v4 不兼容 type=8 的 /v1 | 直连 fallback |
| github | 路径无 /v1 前缀 | 直连 fallback |
| baidu | 特殊认证格式 (bce-v3) | 直连 fallback |
| longcat | Anthropic 格式 | 直连 fallback |
| google/mistral | GFW + 路径问题 | 直连 fallback + 代理 |

---

## 三、调试方法论

### 正确的调试顺序

1. **先验证 Key 有效性** — 通过 `smart_router.py` 的 `call_api()` 测试（走完整链路）
2. **再验证 one-api 路径** — 用 echo server 捕获实际请求
3. **最后调整配置** — 基于实际行为修改 type 和 base_url

### Echo Server 调试法

```python
# 1. 启动 echo server (scripts/echo_server.py)
# 2. 把渠道 base_url 指向 http://localhost:9999
# 3. 发请求，读 echo 日志看实际路径
# 4. 根据实际路径反推正确的 base_url
```

### 常见错误模式

| 错误 | 原因 | 修复 |
|------|------|------|
| HTTP 404 upstream | base_url 包含了 /v1，导致路径重复 | 去掉 /v1 |
| HTTP 403 | Key 过期或被封 | 重新获取 Key |
| HTTP 503 无可用渠道 | 模型名不在渠道注册列表 | 添加模型名到 models 字段 |
| Key 为空 (0 chars) | PUT 更新时未重新设置 key | 每次 PUT 必须带 key |
| 分组 default 无渠道 | Token 分组与渠道分组不匹配 | 所有渠道加 default 分组 |

---

## 四、部署检查清单

### 新增渠道时

- [ ] base_url 不包含 `/v1`（type=8 会自动追加）
- [ ] key 字段已正确设置
- [ ] models 字段包含所有要用的模型名
- [ ] group 字段包含 `default`
- [ ] 用 echo server 验证实际请求路径

### 更新渠道时

- [ ] PUT 请求中包含 key 字段（GET 不返回 key）
- [ ] 更新后立即测试验证

### 容器重建时

- [ ] 数据持久化在 `/opt/one-api-data`（不会丢失）
- [ ] 代理环境变量已配置（HTTP_PROXY/HTTPS_PROXY）
- [ ] NO_PROXY 包含所有国内域名

---

## 五、最终架构决策

```
smart_router.py (意图分类 <5ms)
    ├── one-api 路由 (6+ 渠道通过, 负载均衡)
    │   └── groq, cerebras, deepseek, chat-ubi, pollinations, llm7
    └── 直连 fallback (74 后端全部可用)
        ├── 国内直连: zhipu, baidu, aliyun, volcengine, tencent, chinamobile
        ├── 国际直连: nvidia, github, openrouter, longcat, uncloseai
        └── GFW 代理: google, mistral, cloudflare
```

**设计原则：** one-api 是增强层（负载均衡 + 监控），不是必须层。直连 fallback 保证 100% 可用性。
