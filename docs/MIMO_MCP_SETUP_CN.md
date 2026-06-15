# MiMo MCP（Cursor stdio）

> 更新：2026-06-16
> 用途：在 Cursor 里把 **MiMo CLI** 当作审查 lane 调用，复用 `lima-multi-cli` 产物（`findings.json`）。
> **不**接入 LiMa 生产热路径（`server.py` / 设备网关）。

## 前置条件

1. 本机已安装 **MiMo CLI**（`mimo` 在 PATH 中）
2. Python 依赖（仅本机开发）：

```powershell
python -m pip install -r requirements_mcp_stdio.txt
```

3. 可选环境变量：

| 变量 | 默认 | 说明 |
|------|------|------|
| `LIMA_TIMEOUT` | `180` | MiMo lane 超时（秒） |
| `LIMA_MIMO_ARTIFACT_DIR` | `.omc/artifacts/lima-multi-cli` | 产物目录 |

## 注册到 Cursor

复制 [`mcp.json.example`](../mcp.json.example) 片段到 Cursor **Settings → MCP**，或合并进项目 `.mcp.json`：

```json
"lima-mimo": {
  "command": "python",
  "args": ["-m", "lima_mcp_stdio"],
  "cwd": "D:\\QWEN3.0",
  "env": { "LIMA_TIMEOUT": "180" }
}
```

保存后重启 MCP / Reload Window。

## 工具一览

| 工具 | 作用 |
|------|------|
| `lima_mimo_status` | 检查 `mimo` 是否可用；读取上次 `findings.json` 摘要 |
| `lima_mimo_review` | 对 `task` 跑单 lane MiMo 审查，返回结构化 findings |
| `lima_mimo_verify` | 修复后复跑，对比 `closed` / `still_open` / `new` |

## 产物路径

```
.omc/artifacts/lima-multi-cli/
├── review-brief.md
├── mimo.md
├── findings.json
├── synthesis.md
├── fix-pack.md
└── verify-delta.json
```

## 相关

- 编排内核：`.claude/skills/lima-multi-cli/driver.py`
- 实现：`lima_mcp_stdio/`
- 测试：`tests/test_mimo_mcp_runner.py`
