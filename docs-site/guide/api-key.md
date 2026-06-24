# 获取 API Key

LiMa 使用 Bearer Token 对请求进行鉴权。API Key 分为两类：

| 类型 | 用途 | 获取方式 |
|------|------|----------|
| 公开 API Key | 调用 `/v1/chat/completions` 等公开端点 | 管理后台 / 用户中心 |
| 私有 API Key | 调用设备、运维、后端管理等敏感端点 | 服务器环境变量 `LIMA_API_KEYS` |

## 从管理后台创建

1. 打开 LiMa 管理面板：`https://chat.donglicao.com/admin`
2. 使用 `LIMA_ADMIN_TOKEN` 登录
3. 进入 **客户端密钥** → **新增密钥**
4. 复制生成的 Key，妥善保存（只显示一次）

## 环境变量配置

开发时建议将 Key 写入环境变量，避免硬编码：

```bash
# Linux / macOS
export LIMA_API_KEY="lima-xxxxxxxx"

# Windows PowerShell
$env:LIMA_API_KEY="lima-xxxxxxxx"
```

## 使用方式

所有请求在 HTTP Header 中携带：

```http
Authorization: Bearer <LIMA_API_KEY>
```

## 安全提示

- 不要把 Key 提交到 Git 仓库
- 不要在浏览器前端直接暴露私有 API Key
- 定期在管理后台轮换密钥
