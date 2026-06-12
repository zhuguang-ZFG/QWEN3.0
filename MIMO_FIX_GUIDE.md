# MiMo Code + qwen2API 配置指南

**日期**: 2026-06-12
**状态**: ✅ 已修复

---

## ❌ **之前的错误**

```
Configuration is invalid at C:\Users\zhugu\.config\mimocode\mimocode.json
↳ Unrecognized keys: "providers", "defaultProvider"
```

**原因**: MiMo Code 不使用 `providers` 字段，而是使用：
- 环境变量（推荐）
- `auth.json` 凭据文件
- TUI 交互配置

---

## ✅ **正确配置方法**

### 方案 1: 环境变量（推荐）

**PowerShell**:
```powershell
# 运行配置脚本
. .\set_qwen_env.ps1

# 或手动设置
$env:OPENAI_API_KEY = "sk-qwen-local-2026"
$env:OPENAI_BASE_URL = "http://localhost:7862/v1"

# 启动 MiMo
mimo
```

**Bash**:
```bash
# 运行配置脚本
source ~/set_qwen_env.sh

# 或手动设置
export OPENAI_API_KEY="sk-qwen-local-2026"
export OPENAI_BASE_URL="http://localhost:7862/v1"

# 启动 MiMo
mimo
```

### 方案 2: 使用 MiMo providers 命令

```bash
# 登录自定义 provider（如果支持）
mimo providers login http://localhost:7862/v1

# 或者让 MiMo 使用环境变量中的 OpenAI 配置
# （它会自动读取 OPENAI_BASE_URL）
```

---

## 🚀 **快速开始**

### 1. 设置环境变量

**在 PowerShell 中**:
```powershell
cd D:\QWEN3.0
. .\set_qwen_env.ps1
```

### 2. 验证配置

```powershell
# 检查环境变量
echo $env:OPENAI_BASE_URL
echo $env:OPENAI_API_KEY
```

应该输出:
```
http://localhost:7862/v1
sk-qwen-local-2026
```

### 3. 启动 MiMo

```powershell
mimo
```

MiMo 会自动读取环境变量中的配置。

---

## 📊 **可用模型**

设置后，MiMo Code 可以使用 qwen2API 的所有 156 个模型：

**推荐模型**:
- `qwen3.7-plus` - 最新通用
- `qwen3.7-max` - 最强性能
- `qwen3-coder-plus` - 代码专用
- `qwen3.7-plus-thinking` - 复杂推理

**完整列表**: `SUPPORTED_MODELS.md`

---

## 🎯 **在 MiMo 中选择模型**

启动 MiMo 后：
1. 按 `/` 打开命令面板
2. 输入模型名称，如 `qwen3.7-plus`
3. 或者在设置中配置默认模型

---

## 🛠️ **持久化配置**

### Windows 系统环境变量（永久）

1. 右键"此电脑" → 属性 → 高级系统设置
2. 环境变量 → 用户变量 → 新建：
   - 名称: `OPENAI_API_KEY`
   - 值: `sk-qwen-local-2026`
3. 再新建：
   - 名称: `OPENAI_BASE_URL`
   - 值: `http://localhost:7862/v1`

### PowerShell Profile（自动加载）

编辑 `$PROFILE` 文件：
```powershell
notepad $PROFILE
```

添加：
```powershell
$env:OPENAI_API_KEY = "sk-qwen-local-2026"
$env:OPENAI_BASE_URL = "http://localhost:7862/v1"
```

保存后，每次启动 PowerShell 都会自动配置。

---

## 🔍 **故障排查**

### 问题 1: MiMo 报告 API 错误

**检查**:
```powershell
# 1. 确认环境变量已设置
echo $env:OPENAI_BASE_URL

# 2. 测试 qwen2API 是否运行
curl http://localhost:7862/healthz

# 3. 测试 API 调用
curl -X POST http://localhost:7862/v1/chat/completions `
  -H "Authorization: Bearer sk-qwen-local-2026" `
  -H "Content-Type: application/json" `
  -d '{"model":"qwen3.7-plus","messages":[{"role":"user","content":"test"}]}'
```

### 问题 2: MiMo 找不到模型

**解决**:
```powershell
# 列出可用模型
mimo models

# 如果为空，检查 BASE_URL 是否正确
echo $env:OPENAI_BASE_URL
```

---

## 📝 **配置文件位置**

MiMo Code 实际使用的配置文件：

| 文件 | 用途 | 位置 |
|------|------|------|
| `auth.json` | 凭据存储 | `~/.local/share/mimocode/auth.json` |
| `config.json` | 用户配置 | `~/.config/mimocode/config.json` |
| 环境变量 | API 配置 | PowerShell / 系统环境变量 |

**不要手动创建 `mimocode.json` - 这个文件不存在！**

---

## ✅ **验证配置成功**

运行这些命令应该都成功：

```powershell
# 1. 环境变量设置
. .\set_qwen_env.ps1

# 2. 查看 providers
mimo providers list

# 3. 启动 MiMo（应该能正常进入）
mimo

# 4. 在 MiMo 中测试（输入消息看是否有响应）
```

---

## 🎉 **总结**

**正确做法**:
- ✅ 使用环境变量 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`
- ✅ 运行 `set_qwen_env.ps1` 配置
- ✅ 直接运行 `mimo`

**错误做法**:
- ❌ 不要创建 `mimocode.json` 文件
- ❌ 不要使用 `providers` / `defaultProvider` 字段
- ❌ 不要手动编辑 `auth.json`

---

**配置完成！立即使用:**

```powershell
cd D:\QWEN3.0
. .\set_qwen_env.ps1
mimo
```
