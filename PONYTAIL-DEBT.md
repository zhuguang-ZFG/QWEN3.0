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
| `wakeword_runtime/runtime/frame_codec.py:3` | 3 | WebSocket 帧编解码纯函数模块；上限：仅实现 RFC6455 最小帧子集（无分片/RSV），覆盖唤醒词 runtime 实际用到的 text/ping/pong/close 帧 | 仅最小帧子集，不支持分片/RSV 压缩 | 需要分片/合规审计时换用 wsproto；首轮安全审计教训另见 findings.md F1 结项 |
| `wakeword_runtime/runtime/bridge_request_handler.py:3` | 3 | 桥接请求处理纯函数模块；上限：顶层 `save_wakeword_config: Any = None` 属性而非 from-import（避 importlib 无父包相对导入失败）；测试必须改本属性才生效 | 生产代码也走同一 `_resolve_save()` 通路；测试与生产等价 | bridge 内部状态机复杂化时改为依赖注入 |
| `wakeword_runtime/runtime/websocket_session.py:3` | 3 | WebSocket 会话主循环纯函数；上限：仅覆盖 greeting + 双向消息循环，未做 per-message 流控/背压/重试 | 单一无流控循环，性能足够唤醒词 runtime 低带宽场景 | 需更复杂流控或背压时换用 wsproto frame iterator + asyncio queue |
| `wakeword_runtime/runtime/http_server.py:35` | 35 | `accept_websocket_upgrade` RFC6455 握手协议接缝函数；上限：仅校验 Upgrade + Sec-WebSocket-Key，不校验 Sec-WebSocket-Version / Origin | 仅两步校验，不兼容未来 RFC6455 严合规或浏览器 origin 白名单需求 | 需版本协商/origin 校验时换用 wsproto handshake |
| `ruff.toml` | — | F401 已启用全局门禁（K2+L+M+N 批闭环） | ~6 个 fixture (d)/(e) 注入型态靠 `# noqa: F401` 自豁免，剩 routing_engine/http_caller/device_gateway.tasks/task_creation re-export 走 per-file-ignores | G1b 四型态 lesson learned → K2 第 (e) 型态「fixture 间接依赖链」 → L ruff --fix 删 86 测试侧 + M 删 17 生产侧 + exclude reference → CI 同时跑 ruff F401 gate。今后新增死 import 立即被本地 commit + CI 双门拒收 |

## 待处理项

（无）

## 已结清

- [x] 2026-07-03：I+J 深度瘦身——I 把 `_build_server` 内嵌 `TestRuntimeHandler` 闭包类抽到模块级 `build_handler_class` 工厂，并删 F2/G2/H1 抽离后残留的 7 个零调用方一行 delegator wrapper（`_build_wakeword_config_message`/`_handle_bridge_request`/`_save_wakeword_config`/`_receive_websocket_message`/`_read_exact`/`_send_websocket_text`/`_send_websocket_frame`，全仓 `self._<method>` 0 命中确认），frame_codec from-import 5 名收敛到 3 名（删 `read_exact`/`send_frame`）；附带补 2 个握手 BAD_REQUEST 特征化测试（无 Upgrade 头、无 Sec-WebSocket-Key 头），http_server 164→170，门禁 4427 passed（恰好 +2）。J 继续 I 的握手主线，把 `_handle_websocket` 紧耦合到 `SimpleHTTPRequestHandler` 实例 API 的 RFC6455 握手协议（Upgrade/Key 校验 → compute_accept → 101 + 3 响应头）抽到模块级 `accept_websocket_upgrade(handler) -> tuple[Any, Any] | None` 接缝函数（duck-typed 七实例 API 注入，无须新顶层属性 + lazy resolve 模式），`_handle_websocket` 收缩到 ~9 行「调 accept → 委托 session」，http_server 170→187；附带兑现 I 的 plan 遗留：补 Sec-WebSocket-Version 不校验契约特征化测试 `ws_handshake(include_version=False)`，门禁 4428 passed（恰好 +1）。新增 `ponytail:` 标记 http_server.py:35。
- [x] 2026-07-03：H1+H2 深度瘦身——H2 把 G1b 四型态 lesson learned（特别是 pytest fixture 字符串匹配 (d) 类对 ruff 完全不可见）固化为 pre-commit 安全门 `scripts/testside_f401_safety_gate.py`（tests/ 子树 staged 时触发 `pytest --collect-only`，`--baseline-skip-from` 豁免旧债，main 经 helper 拆分通过 check_code_size，集成入 `run_pre_commit_check.py`），10 个 gate 单测验证纯 helper 行为；H1 TDD 补 `tests/test_wakeword_session_integration.py`（5 个端到端集测 + 辅助 `tests/_wakeword_integration_support.py`，用 importlib + sys.modules alias package 让 hyphen 路径可导入，测试驱动 raw socket + http.client + 手写 RFC6455 client handshake 跑 /health、握手 Ready、set_wakeword_config round-trip、restart、unknown type fallback），再抽 `_handle_websocket` 内嵌事件循环到 `websocket_session.py`（99 行纯函数模块 `serve_websocket_session`），http_server 178→164，闭包依赖与握手不动，集测在抽离前后全过证明行为不变；pypinyin==0.55.0 pin 入 .venv310 使集测可跑。新增 `ponytail:` 标记条目 websocket_session.py:3。门禁全程绿：ruff/format/check_code_size PASS、pyright 0 errors、全量 pytest 4425 passed（较 G1+G2 +15 = H2 +10 + H1 +5）。
- [x] 2026-07-03：G1+G2 深度瘦身——G1a 台账销账 `check_code_size.py 残留 12 个 51-54 行函数`条目（AST 扫描确认实际 0 个超限函数）；G1b 测试侧 F401 精选清理（49 个 STYPE_CLEAN 文件 `ruff --fix` 移除 84 处 domain dead imports，保留 patch-target/fixture 等不动；修复 `motion_task_to_u1_commands` re-export 因 pytest sys.path 根基名引用模式漏检而误删；详见 findings.md G1b 结项 + F1 教训）；G2 TDD 抽离 wakeword `_handle_bridge_request` 到 `bridge_request_handler.py`（121 行纯函数模块，6 个新测试 RED→GREEN→REFACTOR，http_server 213→178，闭包依赖不动，关键解耦是 `save_wakeword_config` 改顶层属性 + `_resolve_save()` 兜底）。新增 `ponytail:` 标记条目 bridge_request_handler.py:3。门禁全程绿：ruff/format/check_code_size PASS、pyright 0 errors、全量 pytest 4410 passed（较 F1+F2 +6 = G2 新增 6 个 bridge_request 测试）。
- [x] 2026-07-03：G1a 台账销账——`check_code_size.py 残留 12 个 51-54 行函数`条目经独立 AST 扫描（51-55 行范围全仓非排除目录）确认实际已 **0 个超限函数**，条目陈旧，移除当前标记区，原始记入已结清。
- [x] 2026-07-03：F1+F2 深度瘦身——F1 生产路径 F401 死导入清理（精选策略 + 17 个 re-export 用 `# noqa: F401` 保留 + 别名感知两轮审计，详见 findings.md）；F2 TDD 抽离 wakeword WebSocket 帧编解码到 `data/digital-human/wakeword_runtime/runtime/frame_codec.py`（118 行纯函数模块，16 个新测试 RED→GREEN→REFACTOR，http_server 274→212，闭包依赖不动）；F3 test_jdcloud_push_probe.py 贴顶下移尝试后回退（fixture 反而增行），跳过保持 300 行现状。门禁全程绿：ruff/format/check_code_size PASS、pyright 0 errors、全量 pytest 4404 passed（较 E6-E9 +16 = F2 新增）。新增 `ponytail:` 标记条目 frame_codec.py:3 并更新 ruff.toml F401 条目说明。
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
