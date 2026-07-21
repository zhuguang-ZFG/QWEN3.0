# 工作区卫生

## Git / 主树

- `D:\QWEN3.0` 的 `main` 为集成台：并行写盘用独立 worktree（见 `AGENTS.md`）。
- 禁止无意义的 `git add .`；密钥不入库。

## 文档

1. **过期即删**：不设 `docs/archive/`。
2. **同步索引**：改状态时更新 `STATUS.md`、`PROJECT_STATUS_CN.md`、`docs/README.md`。
3. **编码**：中文 Markdown 必须 UTF-8；勿用默认系统编码重写文件。

## 本地忽略

- `.codex/`、本地缓存、技能会话状态继续 ignore。
