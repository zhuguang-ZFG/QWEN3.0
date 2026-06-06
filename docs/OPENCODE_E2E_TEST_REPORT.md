# OpenCode E2E 联调测试报告

> 日期: 2026-06-07  
> VPS: https://chat.donglicao.com/v1  
> 测试脚本: `scripts/opencode_e2e_real.py`

## 测试环境

- **本地**: Windows 11, Python 3.12
- **VPS**: 阿里云 ECS, 47.112.162.80:8080
- **网络**: Cloudflare CDN (172.70.x.x, 172.68.x.x)
- **API Key**: `xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw`

## 测试结果

### ✅ 成功的测试

| 测试项 | 状态 | 备注 |
|--------|------|------|
| VPS Health Check | ✅ PASS | version 2.0, model lima-1.3 |
| curl 直接请求 | ✅ PASS | 2+2=4, backend: scnet_ds_flash, 3612ms |

### ❌ 失败的测试

| 测试项 | 状态 | 错误 |
|--------|------|------|
| Simple Query | ❌ FAIL | 403 "Your request was blocked" |
| IDE Detection | ❌ FAIL | 403 "Your request was blocked" |
| Tool Call | ❌ FAIL | 403 "Your request was blocked" |
| Streaming | ❌ FAIL | 403 "Your request was blocked" |
| Skill Injection | ❌ FAIL | 403 "Your request was blocked" |

## 问题分析

### 1. 认证机制验证 ✅

**测试**:
```bash
curl -X POST https://chat.donglicao.com/v1/chat/completions \
  -H "Authorization: Bearer xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/lima-1.3","messages":[{"role":"user","content":"2+2=?"}]}'
```

**结果**: ✅ 成功返回 `{"choices":[{"message":{"content":"4"}}]}`

**结论**: VPS 认证机制正常工作。

---

### 2. OpenAI SDK 403 问题 ❌

**现象**:
- OpenAI Python SDK 发送的请求返回 403 "Your request was blocked"
- curl 直接请求成功（200 OK）
- VPS 日志显示请求来自 Cloudflare IP（172.70.x.x, 172.68.x.x）

**可能原因**:

1. **Cloudflare WAF 规则**:
   - OpenAI SDK 的 User-Agent 可能触发 WAF
   - 请求头格式可能被识别为可疑流量
   - Cloudflare Bot Management 拦截

2. **User-Agent 差异**:
   - curl: `curl/x.x.x` → 通过
   - OpenAI SDK: `openai-python/x.x.x` → 被阻止

3. **请求特征**:
   - SDK 可能添加了额外的请求头
   - SDK 的 TLS fingerprint 可能被识别

---

## 验证步骤

### Step 1: 直接 curl 测试（绕过 SDK）

```bash
# 成功 ✅
curl -s -X POST https://chat.donglicao.com/v1/chat/completions \
  -H "Authorization: Bearer xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw" \
  -H "Content-Type: application/json" \
  -H "User-Agent: curl/8.0.0" \
  -d '{"model":"openai/lima-1.3","messages":[{"role":"user","content":"test"}]}'

# Result: {"choices":[{"message":{"content":"..."}}]}
```

### Step 2: 模拟 OpenAI SDK User-Agent

```bash
# 待测试
curl -s -X POST https://chat.donglicao.com/v1/chat/completions \
  -H "Authorization: Bearer xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw" \
  -H "Content-Type: application/json" \
  -H "User-Agent: openai-python/2.41.0" \
  -d '{"model":"openai/lima-1.3","messages":[{"role":"user","content":"test"}]}'
```

---

## 解决方案建议

### 方案 A: Cloudflare WAF 白名单

在 Cloudflare Dashboard 中添加 WAF 规则：

```
Field: User-Agent
Operator: contains
Value: "openai-python"
Action: Allow
```

或者白名单特定 IP（如果是固定 IP 测试）。

### 方案 B: 自定义 User-Agent

修改 OpenAI SDK 请求，使用被允许的 User-Agent：

```python
import httpx
from openai import OpenAI

http_client = httpx.Client(
    headers={"User-Agent": "OpenCode/1.0.0"}  # 或 "curl/8.0.0"
)

client = OpenAI(
    base_url=VPS_BASE_URL,
    api_key=VPS_API_KEY,
    http_client=http_client,
)
```

### 方案 C: 直接连接 VPS（绕过 Cloudflare）

如果 VPS 有公网 IP，直接连接：

```python
VPS_BASE_URL = "http://47.112.162.80:8080/v1"  # 直接 IP，绕过 CDN
```

⚠️ **注意**: 需要确保 VPS 防火墙允许外部访问 8080 端口。

---

## 当前状态

- ✅ VPS 服务正常运行
- ✅ 健康检查通过
- ✅ curl 直接请求成功
- ✅ 认证机制工作正常
- ❌ OpenAI SDK 被 Cloudflare WAF 阻止

## 下一步行动

1. **立即**: 尝试方案 B（自定义 User-Agent）
2. **短期**: 配置 Cloudflare WAF 白名单（方案 A）
3. **长期**: 考虑 VPS 直连选项（方案 C）用于内部测试

---

## 附录: VPS 日志片段

```
Jun 07 04:46:34 ... INFO: 172.68.164.130:0 - "POST /v1/chat/completions HTTP/1.1" 200 OK
```

- **成功请求**: curl 测试
- **Backend**: scnet_ds_flash
- **响应时间**: 3612ms
- **通过**: Cloudflare CDN (172.68.x.x)

---

**测试脚本**: `scripts/opencode_e2e_real.py`  
**完整日志**: `opencode_test_output.txt`  
**报告生成时间**: 2026-06-07 04:50:00
