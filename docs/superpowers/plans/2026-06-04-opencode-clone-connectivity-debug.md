# OpenCode 克隆与 LiMa 联通调试 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 克隆 OpenCode 源码仓库，研究其 provider 连接层架构，配置 OpenCode 连接 LiMa Server，端到端验证连通性并修复发现的问题。

**Architecture:** 本地部署 LiMa Server (FastAPI, port 8080) + 源码级研读 OpenCode (Go) 的 `@ai-sdk/openai` provider 适配层 + 配置 `opencode.json` 指向 LiMa 的 OpenAI 兼容端点 → 端到端联通测试。

**Tech Stack:** Go (OpenCode 源码), Python 3.10 / FastAPI (LiMa), curl / httpie (调试), opencode CLI (v1.14.49 已安装)

**前置状态:**
- OpenCode CLI v1.14.49 已通过 npm 安装: `C:\Users\zhugu\AppData\Roaming\npm\opencode`
- LiMa OpenCode 集成代码已实现（`detect_ide()` 检测 → `IDE_SOURCES` → `routing_classifier` → feature flags）
- LiMa Server 当前未运行
- OpenCode 配置文件已存在: `%APPDATA%\opencode\opencode.json`（已有 RightCode provider）

---

### Task 1: 克隆 OpenCode 源码仓库

**Files:**
- Create: `d:\QWEN3.0\opencode-source\` (整个仓库)

**目标:** 将 OpenCode Go 源码克隆到 `opencode-source/` 目录，确认仓库结构。

- [ ] **Step 1: 克隆 OpenCode 仓库**

```powershell
git clone https://github.com/anomalyco/opencode.git d:\QWEN3.0\opencode-source
```

Expected: 克隆完成，无 fatal 错误。仓库约 100-200MB（含 Git 历史）。

- [ ] **Step 2: 确认仓库结构概览**

```powershell
Get-ChildItem d:\QWEN3.0\opencode-source -Depth 1 | Select-Object Name, PSIsContainer
```

Expected: 看到 Go 项目标准结构 — `go.mod`, `go.sum`, `main.go`, `cmd/`, `pkg/`, `internal/` 等目录。

- [ ] **Step 3: 确认 Go 版本和模块名**

```powershell
Get-Content d:\QWEN3.0\opencode-source\go.mod | Select-Object -First 5
```

Expected: 显示 `module github.com/anomalyco/opencode` 和 Go 版本号（预计 Go 1.23+）。

- [ ] **Step 4: 列出顶级包目录**

```powershell
Get-ChildItem d:\QWEN3.0\opencode-source -Directory | Select-Object Name
```

Expected: 对比 GitHub 页面了解核心模块划分。

---

### Task 2: 研读 OpenCode Provider 连接层架构

**Files:**
- Read: `d:\QWEN3.0\opencode-source\` 下 provider/AI SDK 相关文件

**目标:** 理解 OpenCode 如何通过 `@ai-sdk/openai` (NPM 包) 连接 OpenAI 兼容后端，找到关键配置解析和 HTTP 请求构造代码。

- [ ] **Step 1: 搜索 provider 相关代码**

```powershell
# 搜索 provider 配置结构体定义
Select-String -Path "d:\QWEN3.0\opencode-source\**\*.go" -Pattern "type.*Provider" -List | Select-Object Filename -First 15
```

Expected: 找到 `provider` 相关结构体定义文件（可能在 `pkg/provider/` 或 `internal/provider/`）。

- [ ] **Step 2: 搜索 openai-sdk 集成代码**

```powershell
# OpenCode 通过 @ai-sdk/openai NPM 包对接 OpenAI 兼容 API
# 搜索 Go 中与 JS SDK 桥接的代码
Select-String -Path "d:\QWEN3.0\opencode-source\**\*.go" -Pattern "ai-sdk|openai.*compatible|baseURL|BaseURL" -List | Select-Object Filename -First 20
```

Expected: 找到 `baseURL` 配置项的解析和使用代码。

- [ ] **Step 3: 搜索 API Key 认证头构造**

```powershell
Select-String -Path "d:\QWEN3.0\opencode-source\**\*.go" -Pattern "Authorization|apiKey|ApiKey|Bearer" -List | Select-Object Filename -First 20
```

Expected: 找到 HTTP 请求中 `Authorization: Bearer` 头的拼接逻辑。

- [ ] **Step 4: 搜索 /v1/chat/completions 端点调用**

```powershell
Select-String -Path "d:\QWEN3.0\opencode-source\**\*.go" -Pattern "chat/completions|/v1/models|/v1/chat" -List | Select-Object Filename -First 10
```

Expected: 确认 OpenCode 调用标准 OpenAI 端点。

- [ ] **Step 5: 搜索 user-agent 头构造**

```powershell
Select-String -Path "d:\QWEN3.0\opencode-source\**\*.go" -Pattern "user-agent|UserAgent|User-Agent|opencode" -CaseSensitive:$false -List | Select-Object Filename -First 10
```

Expected: 找到 OpenCode 发出的 User-Agent 字符串（将用于验证 LiMa 检测逻辑）。

- [ ] **Step 6: 记录关键发现到 findings.md**

```powershell
# 追加连通性研究发现
Add-Content -Path d:\QWEN3.0\findings.md -Value "`n## OpenCode Provider 架构发现 ($(Get-Date -Format 'yyyy-MM-dd'))`n`n- OpenCode 通过 @ai-sdk/openai NPM 包对接 OpenAI 兼容 API`n- baseURL 指向 /v1 端点`n- User-Agent: <待填充>`n"
```

Expected: findings.md 末尾新增记录。

---

### Task 3: 启动 LiMa Server 本地环境

**Files:**
- Read: `d:\QWEN3.0\.env` (验证配置)
- Run: `d:\QWEN3.0\server.py`

**目标:** 启动 LiMa Server 在 localhost:8080，验证 health 和 models 端点正常响应。

- [ ] **Step 1: 检查 .env 关键配置**

```powershell
Get-Content d:\QWEN3.0\.env | Select-String -Pattern "LIMA_API_KEY|LIMA_ADMIN|PORT|8080"
```

Expected: 确认 `LIMA_ADMIN_TOKEN` 和至少一个 API Key 已配置。

- [ ] **Step 2: 启动 LiMa Server（后台）**

```powershell
cd d:\QWEN3.0
.\.venv310\Scripts\python.exe server.py
```

在另一个终端启动，或以 Background 方式启动。Expected: 看到 `Uvicorn running on http://0.0.0.0:8080` 日志。

- [ ] **Step 3: 验证 /health 端点**

```powershell
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/health' -UseBasicParsing -TimeoutSec 5; Write-Host $r.StatusCode; Write-Host $r.Content } catch { Write-Host 'FAIL:' $_.Exception.Message }"
```

Expected: HTTP 200, body 包含 `{"status": "ok"}`。

- [ ] **Step 4: 验证 /v1/models 端点（需 API Key）**

从 `.env` 中获取 `LIMA_ADMIN_TOKEN`，然后：

```powershell
$token = "sk-XXXX"  # 替换为实际 LIMA_ADMIN_TOKEN
powershell -Command "$token='<TOKEN>'; try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/v1/models' -UseBasicParsing -Headers @{'Authorization'='Bearer '+$token} -TimeoutSec 10; $data = $r.Content | ConvertFrom-Json; Write-Host 'Model count:' $data.data.Count } catch { Write-Host 'FAIL:' $_.Exception.Message }"
```

Expected: HTTP 200, 返回模型列表（含 `lima-1.3`）。

- [ ] **Step 5: 验证 OpenCode UA 检测逻辑（模拟请求）**

```powershell
$token = "sk-XXXX"  # 替换为实际 LIMA_ADMIN_TOKEN
$body = '{"model":"lima-1.3","messages":[{"role":"user","content":"hello, what model are you?"}]}'
powershell -Command "$token='<TOKEN>'; $body='$body'; try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/v1/chat/completions' -Method POST -UseBasicParsing -Body $body -ContentType 'application/json' -Headers @{'Authorization'='Bearer '+$token;'User-Agent'='opencode/1.14.49'} -TimeoutSec 30; Write-Host $r.StatusCode; Write-Host $r.Content } catch { Write-Host 'FAIL:' $_.Exception.Message }"
```

Expected: HTTP 200，返回流式/非流式聊天响应。观察 LiMa Server 终端日志确认 `ide_source=OpenCode` 被正确识别。

---

### Task 4: 配置 OpenCode 连接 LiMa

**Files:**
- Modify: `%APPDATA%\opencode\opencode.json` (追加 lima provider)
- Ref: `d:\QWEN3.0\docs\opencode-integration.md` (配置参考)

**目标:** 在 OpenCode 配置中新增 `lima` provider，指向本地 LiMa Server。

- [ ] **Step 1: 备份当前 opencode.json**

```powershell
Copy-Item $env:APPDATA\opencode\opencode.json $env:APPDATA\opencode\opencode.json.bak
```

Expected: 备份成功。

- [ ] **Step 2: 读取当前配置确认结构**

```powershell
Get-Content $env:APPDATA\opencode\opencode.json
```

Expected: 看到现有 `provider` 对象（含 `rd` / RightCode）。

- [ ] **Step 3: 追加 lima provider 到 opencode.json**

在 `"provider"` 对象中添加 lima 配置。编辑 `%APPDATA%\opencode\opencode.json`，在 `"provider"` 内追加：

```json
"lima": {
  "name": "LiMa",
  "npm": "@ai-sdk/openai",
  "options": {
    "apiKey": "<LIMA_ADMIN_TOKEN>",
    "baseURL": "http://127.0.0.1:8080/v1"
  }
}
```

> **⚠️ 注意:** `<LIMA_ADMIN_TOKEN>` 替换为 `.env` 中 `LIMA_ADMIN_TOKEN` 的值（`sk-` 开头）。
> 生产环境应使用 `https://chat.donglicao.com/v1` 作为 baseURL。

- [ ] **Step 4: 验证 JSON 语法正确性**

```powershell
powershell -Command "try { Get-Content $env:APPDATA\opencode\opencode.json | ConvertFrom-Json | Out-Null; Write-Host 'JSON VALID' } catch { Write-Host 'JSON INVALID:' $_.Exception.Message }"
```

Expected: `JSON VALID`。

- [ ] **Step 5: 设置默认 model 指向 lima**

确认 `opencode.json` 顶层有（若无则添加）：

```json
"model": "lima/lima-1.3"
```

Expected: OpenCode 默认使用 LiMa provider。

---

### Task 5: 端到端联通测试（OpenCode → LiMa）

**目标:** 在终端运行 OpenCode，选择 LiMa provider 进行实际对话，验证全链路联通。

- [ ] **Step 1: 确保 LiMa Server 在后台运行**

```powershell
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/health' -UseBasicParsing -TimeoutSec 3; Write-Host 'SERVER OK' } catch { Write-Host 'SERVER DOWN - START IT FIRST' }"
```

Expected: `SERVER OK`。

- [ ] **Step 2: 启动 OpenCode（在 LiMa 项目目录）**

```bash
cd d:\QWEN3.0
opencode
```

Expected: OpenCode TUI 启动成功。进入后按 `Tab` 切换到 Build 模式。

- [ ] **Step 3: 运行 /connect 选择 lima provider**

在 OpenCode TUI 中：

```
/connect
```

选择 `lima` (LiMa) provider。Expected: 连接成功，提示已切换到 lima。

- [ ] **Step 4: 发送简单测试消息**

```
Hello, what backend model are you using right now?
```

Expected: LiMa 返回响应（通过自动路由选后端）。观察 LiMa Server 终端日志确认请求到达。

- [ ] **Step 5: 验证 OpenCode IDE 检测生效**

在 LiMa Server 终端日志中搜索 `OpenCode`:

```powershell
# 检查 LiMa 日志中 ide_source 是否为 OpenCode
Select-String -Path "d:\QWEN3.0\server.log" -Pattern "opencode|OpenCode|ide_source" -CaseSensitive:$false | Select-Object -Last 10
```

如果没有 server.log，直接在终端观察输出。Expected: 日志中 `ide_source=OpenCode`。

- [ ] **Step 6: 测试工具调用（可选 feature flag）**

首先在 `.env` 中启用工具直通模式：

```bash
LIMA_OPENCODE_TOOL_MODE=direct
```

然后重启 LiMa Server，在 OpenCode 中发送需要工具的请求：

```
List all files in the current directory
```

Expected: OpenCode 能正常接收 tool call 响应并执行。

---

### Task 6: 问题排查与修复

**目标:** 如果在 Task 5 中发现任何连通性问题，记录并修复。

- [ ] **Step 1: 检查 HTTP 层面连通性**

如果 OpenCode 连接 LiMa 失败，先用 curl 验证：

```powershell
$token = "sk-XXXX"
$body = '{"model":"lima-1.3","messages":[{"role":"user","content":"hi"}],"stream":true}'
powershell -Command "$token='<TOKEN>'; $body='$body'; try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/v1/chat/completions' -Method POST -UseBasicParsing -Body $body -ContentType 'application/json' -Headers @{'Authorization'='Bearer '+$token} -TimeoutSec 60; Write-Host $r.StatusCode } catch { Write-Host 'CURL FAIL:' $_.Exception.Message }"
```

Expected: HTTP 200。如果失败，检查：
- LiMa Server 是否正在运行
- token 是否正确（`.env` 中的 `LIMA_ADMIN_TOKEN`）
- 防火墙是否阻止 8080 端口

- [ ] **Step 2: 检查 OpenCode 的 baseURL 格式**

OpenCode + `@ai-sdk/openai` 的 `baseURL` 应指向 `/v1` 端点。如果配置了 `http://127.0.0.1:8080/v1`，SDK 会自动追加 `/chat/completions`，形成完整 URL `http://127.0.0.1:8080/v1/chat/completions`。

如果出现 404，检查 baseURL 是否多了一层 `/v1`（导致 `http://127.0.0.1:8080/v1/v1/chat/completions`）。

Expected: 端点路径正确。

- [ ] **Step 3: 检查 LiMa 认证中间件**

如果返回 401/403，确认 token 开头有 `Bearer ` 且 `access_guard.py` 的 `require_private_api_key` 认证通过：

```powershell
Get-Content d:\QWEN3.0\access_guard.py | Select-String -Pattern "LIMA_API_KEY|ADMIN_TOKEN"
```

Expected: 确认 token 匹配逻辑。

- [ ] **Step 4: 记录所有发现到 findings.md**

```powershell
Add-Content -Path d:\QWEN3.0\findings.md -Value "`n## OpenCode → LiMa 联通调试 ($(Get-Date -Format 'yyyy-MM-dd'))`n`n### 测试结果`n- [ ] /health 端点正常`n- [ ] /v1/models 端点正常`n- [ ] /v1/chat/completions 端点正常`n- [ ] OpenCode TUI 连接 LiMa 成功`n- [ ] IDE 检测 (OpenCode) 正确触发`n- [ ] 工具调用正常 (如果启用)`n`n### 发现的问题`n- (记录任何异常)`n`n### 修复措施`n- (记录修复动作)`n"
```

Expected: 记录完整的调试证据。

---

### Task 7: 清理与收尾

**目标:** 提交代码变更，更新文档。

- [ ] **Step 1: 检查是否有代码变更需要提交**

```powershell
git -C d:\QWEN3.0 status --short
```

Expected: 仅 `docs/superpowers/plans/2026-06-04-opencode-clone-connectivity-debug.md` 和可能的 `findings.md` 为新增/修改。

- [ ] **Step 2: 提交文档**

```powershell
git -C d:\QWEN3.0 add docs/superpowers/plans/2026-06-04-opencode-clone-connectivity-debug.md findings.md
git -C d:\QWEN3.0 commit -m "docs: OpenCode 克隆与LiMa联通调试计划及发现"
```

Expected: 提交成功。

- [ ] **Step 3: （可选）恢复 opencode.json 备份**

如果不再需要本地 lima 配置：

```powershell
Copy-Item $env:APPDATA\opencode\opencode.json.bak $env:APPDATA\opencode\opencode.json -Force
```

Expected: 配置恢复。

