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

## 与 radar TG-S3 的关系

雷达 **TG-S3/K-Vault** 指把 Telegram 当 S3 兼容无限对象存储；v0.1 先做**文本归档**（零依赖），后续可选：

1. `sendDocument` 上传 `coding_backend_scores_full_*.json`
2. 专用私有 Channel + message_id 索引表（SQLite 只存 id→label，正文在 TG）
3. 与 R2 双写：TG 给人看，R2 给程序读

**推荐架构：SQLite/JSON 为权威源，Telegram 为 Operator 镜像与异地冷备份。**
