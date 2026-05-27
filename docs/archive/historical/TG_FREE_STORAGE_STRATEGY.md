# Telegram 免费存储策略（TG-S3 v0.1）

> **结论：可以作「冷归档 + Operator 可读日志」，不能替代 LiMa 主数据库。**

## 适合 Telegram 存什么

| 用途 | 说明 | LiMa 现状 |
|------|------|-----------|
| **Eval 排名快照** | 人类可读摘要，/chat 历史可搜索 | `/evalreport`、`/archiveeval` |
| **Webhook / 部署通知** |  append-only 运维流 | `telegram_notify`、push 摘要 |
| **MCP / 安全 gate 摘要** | 周期性 smoke 结果 | 可接 `archive_eval_to_telegram.py` |
| **小 JSON 镜像** | &lt;4KB 文本块或分片消息 | `telegram_archive.chunk_text` |

Telegram 对 Bot 侧消息**云端永久保存**、容量 practically 无限，适合个人 Operator **备份与检索**（按关键词搜聊天记录）。

## 不适合 Telegram 存什么

| 不适合 | 原因 | LiMa 应使用 |
|--------|------|-------------|
| 会话记忆 / 路由状态 | 无事务、无索引、无 JOIN | SQLite `session_memory` |
| 设备 Gateway 实时队列 | 低延迟 + 结构化 ACK | Redis / WSS |
| 密钥与 token | 聊天非加密 vault | env / VPS secret |
| 大文件 (&gt;50MB) | 需 Document API + 限流 | R2 / 本地 `data/` |
| 权威 eval JSON | 需程序 diff/CI 消费 | `data/*.json` + `CODING_BACKEND_RANKING.md` |

## v0.1 实现（P2-18）

- **`LIMA_TG_ARCHIVE=0`** 默认关
- `telegram_archive.py` — 分片、`[TG-ARCHIVE]` 标签
- `scripts/archive_eval_to_telegram.py` — 归档最新 eval 摘要
- Telegram **`/archiveeval`** / **`/archiveeval full`** — 写入当前 chat 历史（即免费冷存储）

## v0.3 实现（P2-23）

- **`eval_notify.py`** — 周期 eval 完成后 TG 摘要 + pool gate 行 + 可选自动归档
- **`/evalschedule`** — 查看 `LIMA_PERIODIC_CODING_EVAL` / notify / auto_archive 开关
- **Env**（均默认关，Operator 显式开启）：
  - `LIMA_PERIODIC_CODING_EVAL=1` — 后台周期 quick eval（默认 168h）
  - `LIMA_PERIODIC_CODING_EVAL_FULL=1` — 周期跑 full-11 而非 quick
  - `LIMA_PERIODIC_EVAL_NOTIFY_TG=1` — 周期完成后推 TG（periodic 开启时默认 1）
  - `LIMA_EVAL_AUTO_ARCHIVE_TG=1` — 完成后自动 `/archiveeval`（full 带 doc）

## v0.4 实现（P2-24）

- **`eval_status.py`** / **`eval_digest.py`** — `/evalstatus` 运维总览、`/evaldigest` quick+full 合并摘要
- **`/codesearch`** — codesearch MCP 状态与探针搜索（`CODESEARCH_MCP_ENABLED=0` 默认关）
- **`server_lifespan.py`** — 启动 `periodic_coding_eval.start()`（VPS 曾漏接导致周期 eval 未跑）
- 快捷菜单：📋 总览 / 📊 摘要 / 🔍 Code

## v0.2 实现（P2-19）

- `telegram_bot.send_document` + `telegram_archive.archive_file_async`
- Telegram **`/archiveeval full doc`** — 摘要 + JSON 文件
- **`/poolgate`** — 查看 eval 驱动的 coding pool 降级列表
- **`eval_pool_gate.py`** — avg&lt;1 的 backend 不进默认 coding pool（`LIMA_EVAL_POOL_GATE=1` 默认开）

雷达 **TG-S3/K-Vault** 指把 Telegram 当 S3 兼容无限对象存储；v0.1 先做**文本归档**（零依赖），后续可选：

1. `sendDocument` 上传 `coding_backend_scores_full_*.json`
2. 专用私有 Channel + message_id 索引表（SQLite 只存 id→label，正文在 TG）
3. 与 R2 双写：TG 给人看，R2 给程序读

**推荐架构：SQLite/JSON 为权威源，Telegram 为 Operator 镜像与异地冷备份。**
