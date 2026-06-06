# OpenCode / Cursor IDE 集成指南

> 如何在 OpenCode、Cursor 等 IDE 中集成 LiMa VPS 作为 AI 后端

## 概述

LiMa (力码) 是一个个人编码助手后端，提供 OpenAI 兼容的 API 接口。本文档说明如何在各种 IDE 中配置 LiMa 作为 AI 模型后端。

**VPS 地址**: `https://chat.donglicao.com/v1`  
**API Key**: 见 `.env` 文件中的 `LIMA_API_KEY`

---

## 快速开始

### 1. 获取 API Key

从 `.env` 文件或 VPS 配置中获取：

```bash
# 本地
grep LIMA_API_KEY .env

# VPS
ssh root@47.112.162.80 'grep LIMA_API_KEY /opt/lima-router/.env'
```

示例：
```
LIMA_API_KEY=xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw
```

### 2. 测试连接

```bash
curl -X POST https://chat.donglicao.com/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -H "User-Agent: curl/8.0.0" \
  -d '{"model":"openai/lima-1.3","messages":[{"role":"user","content":"Hello"}]}'
```

---

## IDE 集成

### OpenCode CLI

**文档**: https://docs.opencode.dev

#### 配置方式 1: 配置文件

**位置**:
- Windows: `%APPDATA%\opencode\opencode.json`
- macOS/Linux: `~/.config/opencode/opencode.json`

**配置**:
```json
{
  "model": "openai/lima-1.3",
  "provider": {
    "openai": {
      "baseURL": "https://chat.donglicao.com/v1",
      "apiKey": "YOUR_API_KEY",
      "timeout": 300000,
      "chunkTimeout": 30000
    }
  }
}
```

#### 配置方式 2: 环境变量

```bash
export OPENAI_BASE_URL="https://chat.donglicao.com/v1"
export OPENAI_API_KEY="YOUR_API_KEY"
```

#### 验证

```bash
opencode --version
opencode init
opencode chat "What is 2+2?"
```

---

### Cursor IDE

**文档**: https://cursor.sh/docs

#### 配置步骤

1. 打开 Cursor Settings (Ctrl+,)
2. 搜索 "AI Model"
3. 选择 "Custom OpenAI API"
4. 填写配置：
   - **Base URL**: `https://chat.donglicao.com/v1`
   - **API Key**: `YOUR_API_KEY`
   - **Model**: `openai/lima-1.3`

#### 验证

1. 打开任意代码文件
2. 按 Ctrl+K 打开 AI 面板
3. 输入: "Explain this code"

---

### Continue.dev (VS Code Extension)

**文档**: https://continue.dev/docs

#### 配置文件

**位置**: `~/.continue/config.json`

**配置**:
```json
{
  "models": [
    {
      "title": "LiMa",
      "provider": "openai",
      "model": "openai/lima-1.3",
      "apiBase": "https://chat.donglicao.com/v1",
      "apiKey": "YOUR_API_KEY"
    }
  ]
}
```

#### 验证

1. 在 VS Code 中打开 Continue 侧边栏
2. 选择 "LiMa" 模型
3. 输入: "Hello"

---

### Cline (VS Code Extension)

**文档**: https://github.com/cline/cline

#### 配置步骤

1. 安装 Cline 扩展
2. 打开 Cline 设置
3. 选择 "Custom OpenAI API"
4. 填写：
   - **API URL**: `https://chat.donglicao.com/v1/chat/completions`
   - **API Key**: `YOUR_API_KEY`
   - **Model**: `openai/lima-1.3`

---

## 使用 Python SDK

### ⚠️ 重要：Cloudflare WAF 问题

OpenAI Python SDK 会被 Cloudflare WAF 拦截（403）。推荐使用以下两种方式：

### 方式 1: 使用 requests 库（推荐）✅

```python
import requests

url = "https://chat.donglicao.com/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "User-Agent": "curl/8.0.0",
}
data = {
    "model": "openai/lima-1.3",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": False,
}

response = requests.post(url, headers=headers, json=data)
result = response.json()
print(result["choices"][0]["message"]["content"])
```

**完整示例**: 见 `scripts/opencode_e2e_requests.py`

### 方式 2: 使用 OpenAI SDK（需要自定义 HTTP 客户端）

```python
import httpx
from openai import OpenAI

# 使用 curl User-Agent 绕过 Cloudflare WAF
http_client = httpx.Client(
    headers={"User-Agent": "curl/8.0.0"}
)

client = OpenAI(
    base_url="https://chat.donglicao.com/v1",
    api_key=API_KEY,
    http_client=http_client,
)

response = client.chat.completions.create(
    model="openai/lima-1.3",
    messages=[{"role": "user", "content": "Hello"}],
)

print(response.choices[0].message.content)
```

---

## 功能支持

| 功能 | 支持 | 备注 |
|------|------|------|
| **Chat Completions** | ✅ | 标准 OpenAI 格式 |
| **Streaming** | ✅ | SSE 流式响应 |
| **Tool Calling** | ✅ | Function calling |
| **Vision** | ✅ | 图片输入 |
| **IDE Detection** | ✅ | User-Agent: OpenCode/1.0.0 |
| **Skill Injection** | ✅ | Backend-Aware 无重复 |
| **Embeddings** | ❌ | 未实现 |
| **Fine-tuning** | ❌ | 未实现 |

---

## 模型列表

| 模型 ID | 描述 | 用途 |
|---------|------|------|
| `openai/lima-1.3` | 默认模型 | 通用编码助手 |
| `anthropic/claude-sonnet-4` | Claude Sonnet | 高质量代码生成 |
| `deepseek/deepseek-chat` | DeepSeek | 推理优化 |

**完整列表**: `GET /v1/models`

---

## 高级配置

### 1. 自定义超时

```json
{
  "provider": {
    "openai": {
      "timeout": 300000,       // 5分钟总超时
      "chunkTimeout": 30000    // 30秒块超时
    }
  }
}
```

### 2. 启用记忆召回

LiMa 自动启用长期记忆功能，无需额外配置。

### 3. 使用特定后端

通过模型 ID 前缀指定：

```json
{
  "model": "anthropic/claude-sonnet-4"  // 使用 Anthropic Claude
}
```

---

## 故障排查

### 问题 1: 403 "Your request was blocked"

**原因**: Cloudflare WAF 拦截

**解决方案**:
1. 使用 `requests` 库代替 OpenAI SDK（见上文）
2. 设置 `User-Agent: curl/8.0.0`
3. 参考 `scripts/opencode_e2e_requests.py`

### 问题 2: 401 Unauthorized

**原因**: API Key 错误或未设置

**解决方案**:
```bash
# 检查 API Key
echo $OPENAI_API_KEY

# 测试连接
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://chat.donglicao.com/health
```

### 问题 3: 连接超时

**原因**: 网络问题或 VPS 不可达

**解决方案**:
```bash
# 检查 VPS 状态
curl https://chat.donglicao.com/health

# 检查 SSH 连接
ssh root@47.112.162.80 'systemctl status lima-router'
```

### 问题 4: 响应 "当前所有服务暂时不可用"

**原因**: 后端暂时不可用（fallback 响应）

**解决方案**:
1. 检查 VPS 日志: `journalctl -u lima-router -n 50`
2. 检查后端 API Keys 配置
3. 等待后端恢复或联系管理员

---

## 安全建议

### 1. API Key 保护

- ❌ **不要**将 API Key 提交到 Git
- ❌ **不要**在公共代码中硬编码
- ✅ **使用**环境变量或配置文件
- ✅ **添加** `.env` 到 `.gitignore`

### 2. 网络安全

- ✅ VPS 通过 Cloudflare CDN 访问（HTTPS）
- ✅ 支持 API Key 认证
- ⚠️ 8080 端口未对外开放（仅内部访问）

### 3. 使用限制

- LiMa 是**个人项目**，非商业化服务
- 请勿滥用或用于生产环境
- 建议自建 VPS 或使用官方 API

---

## 相关文档

- **测试脚本**: `scripts/opencode_e2e_requests.py`
- **测试报告**: `docs/OPENCODE_E2E_TEST_REPORT.md`
- **项目架构**: `AGENTS.md`
- **部署文档**: `docs/DEPLOY_AND_RELEASE_CONVENTION.md`

---

## 联系与支持

- **项目仓库**: https://github.com/zhuguang-ZFG/QWEN3.0
- **VPS 地址**: https://chat.donglicao.com
- **健康检查**: https://chat.donglicao.com/health

---

**最后更新**: 2026-06-07  
**测试状态**: ✅ 5/5 通过
