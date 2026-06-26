# 工作区卫生

LiMa 主仓库 (`D:\QWEN3.0`) 只保留 Server、设备子模块、评测 fixture 与文档。
参考克隆、本地数据库、部署包和一次性脚本统一放在仓库外：

```text
D:\LIMA-external\
  reference-repos/     开源参考克隆
  hardware-vendor/     inkscape / bCNC / llama.cpp 等
  third-party-apps/    与 Server 无直接耦合的应用树
  ops-tools/frp/       FRP 工具（运行中时可暂留 D:\GIT\frp 副本）
  local-runtime/data/  SQLite、deploy tar、本地 smoke JSON
  scratch/             根目录散落脚本与 context-construction 笔记
  scratch/superpowers-plans/  未纳入 Git 的 superpowers 计划草稿
  archives/            压缩包
  cursor-local/        .claude / 本地代理配置
```

## 保留在仓库内

- LiMa Python 核心、`routes/`、`tests/`、`docs/`（已 tracked 的 superpowers plans）
- Git 子模块：`esp32S_XYZ`
- `requirements_server.txt` and deliberate test fixtures stay tracked; mutable
  runtime JSON under `data/` stays ignored and must not be re-added
- `donglicao-site-v2/`（Next.js 官网，tracked）；旧 `donglicao-site/` 归档后可移除
- Agent Worker 本地运行状态使用 `.lima-worker/dev/`，不得重新引入 `.lima-code/`
  或 `deepcode-cli` 作为当前验证路径。

## FRP 仍在仓库内时

`frpc.exe` 若被进程占用，无法整目录搬走。可停止 FRP 后再迁移，或使用 junction：

```powershell
cmd /c mklink /J D:\QWEN3.0\frp D:\LIMA-external\ops-tools\frp
```

## 被锁定的本地 DB

`data/agent_tasks.db` 等在服务运行时无法移动。
已在 `.gitignore` 忽略；停服后可手动移到 `D:\LIMA-external\local-runtime\data\`。
## Codex `.codex/` 边界

- `.codex/config.toml` 可以提交，用来放项目级 Codex 默认配置。
- `.codex/agents/*.toml` 可以提交，用来定义项目级 custom agents。
- 其他 `.codex/` 本地缓存、技能、会话状态继续忽略，不要把整目录放开。

## 文档归档卫生

归档 `docs/` 下的文档时遵循以下规则，避免索引死链和协作者困惑：

1. **移到 `docs/archive/`**：归档文件统一放 `docs/archive/`，不散落到子目录。
2. **同步更新 `docs/README.md`**：归档后立即从活跃表格移除或改为 `archive/` 路径，更新索引日期。
3. **标注归档原因**：在文件头部或 commit message 说明归档原因（被取代、过时、已完成等）。
4. **检查 VitePress 侧边栏**：`docs-site/.vitepress/config.ts` 仅引用 `docs-site/` 内文件，与 `docs/` 独立，一般无需同步；但若 docs-site 内有对应内容则一并清理。
