# Ponytail 技术债台账

> 记录代码中 `ponytail:` 标记的捷径、上限与升级触发条件。
> 原则：每个 `ponytail:` 注释必须说明「上限」和「升级路径」，否则标记为 `no-trigger`。

## 当前标记

| 文件 | 行 | 简化内容 | 上限 | 升级触发条件 |
|------|----|----------|------|--------------|
| `access_guard.py:14` | 14 | WS_QUERY_PARAM_TOKEN_WARNING：每次 legacy query-param auth 使用都记录日志 | 日志噪音 | query-param auth 使用量连续 7 天为 0 时删除该路径 |
| `capability_matrix.py:132` | 132 | ASCII token 使用单词边界避免误匹配 | 非 ASCII 品牌名可能误匹配 | 引入更精确的品牌 token 列表后替换 |
| `device_gateway/task_creation.py:32` | 32 | 用 pytest-asyncio / FastAPI loop 下线程卸载 | 线程上下文切换开销 | 全链路改为纯 async 后移除线程卸载 |
| `device_logic/activation.py:25` | 25 | `IF NOT EXISTS` + `_table_ready` 缓存 | 孤立测试 DB 可能失效 | 测试固定使用独立 DB 后改为显式建表 |
| `device_logic/activation.py:54` | 54 | 立即消费激活码（一次性使用） | TTL 内重放仍可能 | 引入幂等消费记录后移除 |
| `scripts/guardian_test_index.py:114` | 114 | 跳过裸顶层包键（如 `routes`） | 可能漏检大目录下的缺失测试 | 目录级覆盖分析更精确后移除 |
| `routes/device_ota_app.py::_ota_status_for_device` | — | `gradual.is_device_selected` 每请求重算 O(N log N) 排序 + N 次 SHA256 | 设备池 ~10^4 | 在 `GradualRollout` 缓存当前阶段选定集合（start/promote/rollback 时重算），暴露集合成员查询 |
| `donglicao-site-v2/app/{en/,}{privacy,terms}/page.tsx` | — | 法律正文按 locale 硬编码于 JSX，无 i18n 单一来源 | 2 语言 (zh/en) | 第 3 个 locale 落地时改为单一 JSON/MD 源 + 共享组件渲染 |

## 待处理项

（无）

## 已结清

- [x] 2026-06-22：删除 `search_gateway/` 整包（零生产引用）。
- [x] 2026-06-22：`lima_mcp_stdio/` 移出生产部署路径。
- [x] 2026-06-22：合并 `estimate_tokens()` 重复实现。
- [x] 2026-06-22：扫描 `except ImportError: pass` 静默降级 — 生产代码 0 处（全部已有处理逻辑）。
- [x] 2026-06-22：用 sqlite3 FTS5 替换 `local_retrieval/` 自定义索引（新建 `fts_index.py`，`production_index.py` 改用 FTS5）。
- [x] 2026-06-22：审查 `scripts/` 目录，删除 9 个未使用一次性脚本（~732 行）。
