# codesearch MCP Setup (PE-B-1)

> **Status:** Active runbook | **Created:** 2026-05-26  
> **Upstream:** [flupkede/codesearch](https://github.com/flupkede/codesearch) (Rust, Apache-2.0)  
> **Scope:** 本地/参考仓 **离线**语义搜索；**不改** LiMa 路由热路径。

## 目标

为 LiMa Code / Cursor 提供比纯 `rg` 更强的跨文件语义检索（BM25 + vector + tree-sitter AST chunking），索引路径受 allowlist 约束，私有代码不出网。

## 与 LiMa 现有能力边界

| 能力 | codesearch MCP | LiMa 已有 |
|------|----------------|-----------|
| 本地关键词 | ✅ literal / regex | `rg`、dev-search |
| 本地语义 | ✅ hybrid RRF | `search_repo`（graph retrieval） |
| 公网文档 | ❌ 本阶段不做 | dev-search URL/GitHub |
| Chat 默认路由 | ❌ **禁止** | `routing_engine` 不变 |

**默认关：** `CODESEARCH_MCP_ENABLED=0`。仅在 LiMa Code 任务显式启用 MCP 时使用。

## 安装（Windows Operator）

1. 从 [Releases](https://github.com/flupkede/codesearch/releases) 下载 `codesearch-windows-x86_64.zip`
2. 解压并将 `codesearch.exe` 加入 PATH（建议 `%LOCALAPPDATA%\Programs\codesearch\`）
3. 首次索引（2–5 分钟）：

```powershell
codesearch index add D:\GIT --alias lima-git
codesearch index add D:\GIT\deepcode-cli --alias lima-code
codesearch doctor
```

索引数据默认在 `%USERPROFILE%\.codesearch\`；仓库注册表 `repos.json` 同目录。

## Allowlist

`.env` / LiMa Code 仅允许以下根路径（计划默认值）：

```env
CODESEARCH_MCP_ENABLED=0
CODESEARCH_INDEX_PATHS=D:/GIT,D:/GIT/deepcode-cli
```

**规则：**

- 仅索引 `CODESEARCH_INDEX_PATHS` 列出的目录
- 勿索引含密钥、`.env`、凭据备份的路径
- 可用 repo 根 `.codesearchignore`（gitignore 语法）排除 `venv/`、`node_modules/` 等

## MCP 接入

### 单仓（stdio，推荐起步）

LiMa Code `settings.json`：

```json
{
  "mcpServers": {
    "codesearch": {
      "command": "codesearch",
      "args": ["mcp", "--mode", "local"]
    }
  }
}
```

Cursor 同理：`mcp.json` 中添加同名 stdio 服务器。

### 多仓（serve + HTTP）

```powershell
codesearch serve
# 默认 http://127.0.0.1:39725/mcp
```

LiMa Code：

```json
{
  "mcpServers": {
    "codesearch": {
      "command": "codesearch",
      "args": ["mcp", "--mode", "client"]
    }
  }
}
```

## 主要 MCP 工具

| 工具 | 用途 |
|------|------|
| `search` | 语义 / 字面量检索（默认 semantic） |
| `find` | 定义 / 引用 / import |
| `explore` | 文件 outline / 相似块 |
| `get_chunk` | 按 chunk_id 取代码 |
| `status` | 索引状态 |

多仓模式下需传 `project` 或 `group`（见 upstream README）。

## 验收

```powershell
python scripts/smoke_codesearch_local.py
```

- [ ] `codesearch doctor` 通过（或 smoke 报告 `binary_missing` 并给出安装提示）
- [ ] allowlist 外路径拒绝（手动：对未注册路径 `codesearch index add` 不应出现在 repos.json）
- [ ] 3 条 fixture query：`rg` baseline 有输出；codesearch 安装后 `search` 有结果
- [ ] LiMa Code 任务可调用 `search`（read-only）

## Baseline fixture queries（B-1.4）

| # | Query | 预期命中区域 |
|---|-------|-------------|
| 1 | `routing_engine classify tier` | `routing_engine.py` / `router_v3.py` |
| 2 | `telegram webhook secret verify` | `routes/telegram.py` |
| 3 | `health_tracker record_failure degraded` | `health_recorder.py` |

## 参考

- [flupkede/codesearch README](https://github.com/flupkede/codesearch/blob/master/README.md)
- `docs/superpowers/plans/2026-05-26-lima-productivity-enhancement.md` — PE-B-1 任务表
- `docs/reference/MCP_CONNECTOR_CATALOG.md` — candidate 条目

## 回滚

```powershell
codesearch index rm D:\GIT
# 删除 mcpServers.codesearch 配置
# CODESEARCH_MCP_ENABLED=0
```

不影响 LiMa Server / VPS 生产路径。
