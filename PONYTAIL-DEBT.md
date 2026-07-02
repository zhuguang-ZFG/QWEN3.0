# Ponytail 技术债台账

> 记录代码中 `ponytail:` 标记的捷径、上限与升级触发条件。
> 原则：每个 `ponytail:` 注释必须说明「上限」和「升级路径」，否则标记为 `no-trigger`。

## 当前标记

| 文件 | 行 | 简化内容 | 上限 | 升级触发条件 |
|------|----|----------|------|--------------|
| `access_guard.py:14` | 14 | WS_QUERY_PARAM_TOKEN_WARNING：每次 legacy query-param auth 使用都记录日志 | 日志噪音 | query-param auth 使用量连续 7 天为 0 时删除该路径 |
| `device_logic/activation.py:26` | 26 | `IF NOT EXISTS` + `_table_ready` 缓存 | 孤立测试 DB 可能失效 | 测试固定使用独立 DB 后改为显式建表 |
| `device_logic/activation.py:55` | 55 | 立即消费激活码（一次性使用） | TTL 内重放仍可能 | 引入幂等消费记录后移除 |
| `scripts/guardian_test_index.py:114` | 114 | 跳过裸顶层包键（如 `routes`） | 可能漏检大目录下的缺失测试 | 目录级覆盖分析更精确后移除 |
| `donglicao-site-v2/app/{en/,}{privacy,terms}/page.tsx` | — | 法律正文按 locale 硬编码于 JSX，无 i18n 单一来源 | 2 语言 (zh/en) | 第 3 个 locale 落地时改为单一 JSON/MD 源 + 共享组件渲染 |
| `device_gateway/tasks.py:33` | 33 | `routes.device_gateway_dispatch` 改为 lazy import 避免模块加载循环依赖 | 运行时反向依赖仍存在（device_gateway → routes） | 引入 `TaskDispatcher` 协议抽象后消除 |
| `wakeword_runtime/runtime/wakeword_config.py:3` | 3 | 配置读/写/拼音转换抽离为无 socket 单测模块；上限：pypinyin 依赖 | 拼音转换依赖 pypinyin 外部库 | 换用更轻量拼音方案或上游统一 i18n 时重评 |
| `ruff.toml` | — | F401 未加入全局门禁，仅豁免已知 re-export 文件 | ~115 个生产 F401 残留为整洁度噪音 | 引入 `pyright --verifytypes` 或逐文件清理后启用 F401 门禁 |
| `check_code_size.py` 残留 | — | 12 个 51-54 行函数未拆分（scripts/tests/MCP/xiaozhi） | 单函数轻微超标 1-4 行，非核心生产路径 | 触发下一个生产函数超 50 行时一并清理 |

## 待处理项

（无）

## 已结清

- [x] 2026-07-02：E6-E9 深度瘦身——E6-1 提取 `lima_codegraph_tools` 3 个长函数子辅助（298 行）；E6-2 device_app_misc provision 端点抽到 `device_app_provision.py`（misc 296→199）；E6-3/E6-4/E6-5 经核验已在行限额内（profiles 295 / routing_intent 294 / lima_feature_planner 293，函数 ≤41）跳过；E7 删除 DEPRECATED `routes/eval_internal.py`（410 Gone 桩）+ 路由注册 + 退役测试；E8 从 wakeword `http_server.py` 抽 `wakeword_config.py`（http_server 347→274，配置读/写/拼音无 socket 依赖，新增 `ponytail:` 标记）；E9 同步本台账行号，删除 6 个已在源码中移除的失效标记条目（capability_matrix:132 / task_creation:32 / task_events:182 / mqtt_client:81 / quota:33 / chat-web config.js:9），修正 3 个偏移行号（activation 25→26、54→55；tasks 31→33）。
- [x] 2026-06-26：极致瘦身——删除 19 个 DEPRECATED v3.0 退役 shim（orchestrate*、eval_*、context_pipeline/{code_scanner,semantic_code_retrieval,code_context_injection,graph_retrieval,reranking} 等）+ 4 测试；本地磁盘清理 ~2.1GB（.worktrees + reference + donglicao-site-backup）；冗余 IDE 配置删除（.codex/.qoder/.trae/.roo）；部署排除清单补全（donglicao-site*、docs-site、chat-web）。Python 文件 2471→1177(-52%)，行数 273827→130913(-52%)。
- [x] 2026-06-26：impeccable 设计系统安装 + 官网设计基线（PRODUCT.md + DESIGN.md + .impeccable/live/config.json）+ AI slop 修复（gradient-text、broken-image）+ CI 集成。
- [x] 2026-06-26：PD-001 `GradualRollout.is_device_selected` 缓存——在 `_load`/`start`/`promote`/`rollback` 重建 `_selected_cache: set[str]`，热路径从 O(N log N) + N SHA256 降为 O(1) 集合成员查询；`routes/device_ota_app.py` 的 ponytail 注释移除。
- [x] 2026-06-22：删除 `search_gateway/` 整包（零生产引用）。
- [x] 2026-06-22：`lima_mcp_stdio/` 移出生产部署路径。
- [x] 2026-06-22：合并 `estimate_tokens()` 重复实现。
- [x] 2026-06-22：扫描 `except ImportError: pass` 静默降级 — 生产代码 0 处（全部已有处理逻辑）。
- [x] 2026-06-22：用 sqlite3 FTS5 替换 `local_retrieval/` 自定义索引（新建 `fts_index.py`，`production_index.py` 改用 FTS5）。
- [x] 2026-06-22：审查 `scripts/` 目录，删除 9 个未使用一次性脚本（~732 行）。
