# MiMo Code 正确配置步骤（最终版）

**日期**: 2026-06-12
**状态**: ✅ 正确方案

---

## 🎯 **核心问题**

MiMo Code 需要通过**交互式界面**配置自定义 Provider，不能直接编辑配置文件。

---

## ✅ **正确配置步骤**

### 步骤 1: 设置环境变量

在 **PowerShell** 中运行：

```powershell
cd D:\QWEN3.0
. .\set_qwen_env.ps1
```

验证：
```powershell
echo $env:OPENAI_API_KEY
echo $env:OPENAI_BASE_URL
```

---

### 步骤 2: 配置 MiMo Provider

运行配置命令：
```powershell
mimo providers login
```

会出现交互界面，按以下步骤操作：

#### 2.1 选择服务商

```
┌ Add credential
│
◆ 选择服务商
│ ○ MiMo (推荐)
│ ○ MiMo Auto (free)
│ ● 其他 Provider    ← 选择这个（用方向键移动，回车确认）
└
```

**操作**:
- 用 **方向键** ↓ 移动到 "其他 Provider"
- 按 **回车** 确认

#### 2.2 选择 Provider 类型

```
◆ 选择 Provider 类型
│ ● OpenAI           ← 选择这个
│ ○ Anthropic
│ ○ Google
│ ○ Azure OpenAI
│ ○ 其他 OpenAI 兼容
└
```

**操作**: 选择 **OpenAI** 并回车

#### 2.3 输入 API 配置

```
◆ Base URL (可选，留空使用默认)
│ http://localhost:7862/v1    ← 输入这个
```

**操作**: 输入 `http://localhost:7862/v1` 并回车

```
◆ API Key
│ sk-qwen-local-2026          ← 输入这个
```

**操作**: 输入 `sk-qwen-local-2026` 并回车

#### 2.4 确认保存

```
◆ 确认保存配置？
│ ● 是
│ ○ 否
```

**操作**: 选择 **是** 并回车

---

### 步骤 3: 验证配置

```powershell
mimo providers list
```

应该看到：
```
┌ Credentials
│
● OpenAI api
│  Base URL: http://localhost:7862/v1
│
└ 1 credential
```

---

### 步骤 4: 启动 MiMo

```powershell
mimo
```

启动后：
1. 按 `Ctrl+P` 打开设置
2. 选择 Provider: **OpenAI**
3. 选择 Model: **qwen3.7-plus**

---

## 🔧 **替代方案：直接编辑 auth.json**

如果交互式配置失败，手动编辑凭据文件：

### 1. 找到文件位置

```powershell
notepad C:\Users\zhugu\.local\share\mimocode\auth.json
```

### 2. 添加配置

在文件中添加（注意 JSON 格式）：

```json
{
  "credentials": [
    {
      "id": "qwen-local",
      "provider": "openai",
      "name": "Qwen Local",
      "config": {
        "baseURL": "http://localhost:7862/v1",
        "apiKey": "sk-qwen-local-2026"
      },
      "createdAt": "2026-06-12T08:00:00.000Z"
    }
  ]
}
```

**注意**: 如果文件已有内容，需要合并到现有结构中。

---

## 🎯 **快速测试**

配置完成后，在 MiMo 中输入：

```
你好，请用一句话介绍你自己
```

如果返回通义千问的介绍，说明配置成功！

---

## 📊 **可用模型**

配置成功后，可以使用这些模型：

- `qwen3.7-plus` - 最新通用（推荐）
- `qwen3.7-max` - 最强性能
- `qwen3-coder-plus` - 代码专用
- `qwen3.7-plus-thinking` - 复杂推理
- `qwen3.5-plus` - 稳定版
- `qwen3.5-flash` - 快速响应

**完整列表**: 156 个模型，见 `SUPPORTED_MODELS.md`

---

## 🛠️ **故障排查**

### 问题 1: MiMo 仍提示登录

**原因**: 没有正确配置 Provider

**解决**: 重新运行 `mimo providers login`，仔细按步骤操作

### 问题 2: API 调用失败

**检查**:
```powershell
# 1. qwen2API 是否运行
curl http://localhost:7862/healthz

# 2. 环境变量是否设置
echo $env:OPENAI_BASE_URL

# 3. Provider 配置
mimo providers list
```

### 问题 3: 找不到模型

**解决**:
- 在 MiMo 中按 `/` 打开命令
- 输入 `/model qwen3.7-plus`
- 或在设置中手动选择模型

---

## 📝 **配置文件位置总结**

| 文件 | 路径 | 用途 |
|------|------|------|
| `auth.json` | `~/.local/share/mimocode/auth.json` | **Provider 凭据（关键）** |
| `config.json` | `~/.config/mimocode/config.json` | 用户偏好设置 |
| 环境变量 | PowerShell / 系统 | API Key 和 Base URL |

**重要**: 真正生效的是 `auth.json`，不是 `config.json`！

---

## ✅ **最终验证清单**

配置成功的标志：

- [ ] `mimo providers list` 显示 OpenAI provider
- [ ] Base URL 为 `http://localhost:7862/v1`
- [ ] MiMo 启动后不再提示登录
- [ ] 输入消息能得到响应
- [ ] 响应来自通义千问

---

## 🚀 **立即开始**

```powershell
# 1. 设置环境变量
cd D:\QWEN3.0
. .\set_qwen_env.ps1

# 2. 配置 Provider（交互式）
mimo providers login
# 选择: 其他 Provider → OpenAI
# Base URL: http://localhost:7862/v1
# API Key: sk-qwen-local-2026

# 3. 验证
mimo providers list

# 4. 启动
mimo
```

---

**按照这个步骤，MiMo Code 一定能正确配置！** 🎯
