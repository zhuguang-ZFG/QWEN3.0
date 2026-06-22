# Ponytail 技术债台账

> 记录代码中 `ponytail:` 标记的捷径、上限与升级触发条件。
> 原则：每个 `ponytail:` 注释必须说明「上限」和「升级路径」，否则标记为 `no-trigger`。

## 当前标记

| 文件 | 行 | 简化内容 | 上限 | 升级触发条件 |
|------|----|----------|------|--------------|
| `access_guard.py:14` | 14 | WS_QUERY_PARAM_TOKEN_WARNING：每次 legacy query-param auth 使用都记录日志 | 日志噪音 | query-param auth 使用量连续 7 天为 0 时删除该路径 |
| `capability_matrix.py:132` | 132 | ASCII token 使用单词边界避免误匹配 | 非 ASCII 品牌名可能误匹配 | 引入更精确的品牌 token 列表后替换 |
| `device_gateway/task_creation.py:32` | 32 | 在 pytest-asyncio / FastAPI loop 下线程卸载 | 线程上下文切换开销 | 全链路改为纯 async 后移除线程卸载 |
| `device_logic/activation.py:25` | 25 | `IF NOT EXISTS` + `_table_ready` 缓存 | 孤立测试 DB 可能失效 | 测试固定使用独立 DB 后改为显式建表 |
| `device_logic/activation.py:54` | 54 | 立即消费激活码（一次性使用） | TTL 内重放仍可能 | 引入幂等消费记录后移除 |
| `scripts/guardian_test_index.py:114` | 114 | 跳过裸顶层包键（如 `routes`） | 可能漏检大目录下的缺失测试 | 目录级覆盖分析更精确后移除 |

## 待处理项

- [ ] 扫描仓库中所有 `except ImportError: pass` 的静默降级，按 AGENTS.md 硬规则改为 `logger.warning`（2026-06-22 审计约 188 处）。
- [ ] 审查 `scripts/` 目录中 60 个脚本，删除明确不再使用的一次性脚本。
- [ ] 评估 `local_retrieval/` 是否可被 `sqlite3` FTS5 替代，减少自定义索引代码。

## 已结项

- [x] 2026-06-22：删除 `search_gateway/` 整包（零生产引用）。
- [x] 2026-06-22：`lima_mcp_stdio/` 移出生产部署路径。
- [x] 2026-06-22：合并 `estimate_tokens()` 重复实现。
