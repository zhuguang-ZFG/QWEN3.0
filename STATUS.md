# LiMa Status

> **项目定位**: AI 智能设备统一云端服务（2026-06-09 战略转型完成）
> **技术栈**: Python 3.10 + FastAPI + SQLite + Redis
> **公网端点**: chat.donglicao.com, api.donglicao.com
> **部署**: Alibaba Cloud VPS + JDCloud 备用

> Updated: 2026-06-17
> Branch: `main`
> Scale: 约 1021 个 Python 文件 / 全仓 630 文件已格式化
> Tests: 全量 1662 passed / 23 skipped / 0 failed；ruff check clean；ruff format clean
> pyright 权威文件（server.py / routing_engine.py / routes/chat_endpoints.py）0 errors
> VPS smoke：`https://chat.donglicao.com/health` 200；`/device/v1/health` 200（`auth_configured=true`）；沿用 2026-06-17 记录。

## 当前项目状态

### 最近完成（2026-06-17）G4 启动/部署不确定性降低 + VPS 验证

- **实现**：`server_lifespan.py` 拆分为 `server_lifespan_state.py`、`server_lifespan_phases.py`、`server_lifespan.py`（99 行）；启动阶段分为 critical（阻塞 ready）与 warm（后台异步预热），warm 失败不阻塞服务。
- **/health 语义**：新增 `starting` / `warming` / `ready` / `error`，响应包含 `pending_warm` 与 `errors`。
- **STARTUP_PHASES 顺序修复**：`PhaseTimer` 在阶段启动时立即追加记录，退出时仅更新耗时/状态，确保并发 warm 阶段仍按启动顺序展示（而非完成顺序）。
- **VPS 验证**：
  - 部署到 `47.112.162.80`，`/opt/lima-router/server_lifespan_state.py` 已更新。
  - `https://chat.donglicao.com/health` → HTTP 200，`status=ok`，`startup.status=ready`，13 个 phase 按启动顺序返回（含 `observability.prometheus.start` 126.3ms 置尾）。
  - `https://chat.donglicao.com/device/v1/health` → HTTP 200，`auth_configured=true`。
- **验证**：`pytest` 全量 1662 passed / 23 skipped；`ruff check` / pyright clean；`tests/test_system_endpoints.py` 6 passed。

### 最近完成（2026-06-17）G3 小批冷区清理

- **删除文件**：`search_gateway/dev_tools.py`（279 行）、`session_memory/hooks.py`（61 行）、`tool_gateway/executor.py`（136 行）、`infra/g4f_server.py`（18 行），合计 494 行。
- **验证**：ripgrep 确认无引用；`pytest` 全量 1662 passed / 23 skipped；`ruff check` clean。
- **文档**：更新 `docs/CODEBASE_SUBSYSTEM_TIER_CN.md`。

### 最近完成（2026-06-17）G2 设备模型准入复跑

- **复跑命令**：`python scripts/eval_device_model_role.py --all --markdown`
- **结果**：8 个角色与 `DEVICE_ROLE_PREFERENCES` 对齐；意图解析器/文本规划器/恢复解释器/路由策略契约 100% admit；图像生成器条件准入；矢量化器 `opencv_contour_detect` 因本地 `cv2` 已安装从 fail 修正为 **12/12 通过**；提示增强器/视觉分析器 defer。
- **脚本修复**：`scripts/eval_device_model_role.py` 增加 `sys.stdout.reconfigure(encoding="utf-8")`，解决 Windows 重定向 UTF-8 乱码。
- **文档**：更新 `docs/model_admission/2026-06-17-device-drawing-writing-evidence.md` 与完整报告。

### 最近完成（2026-06-17）代码质量门禁整改 + AI→Motion 发布门回归证据

- **P0 静默异常治理**：生产路径约 38 处 `except ImportError/Exception: pass` 或仅 `logger.debug` 的关键依赖降级升级为 `logger.warning`，符合 AGENTS.md Hard Rule 1。
- **P1 模块拆分**：`device_voice/voiceprint.py` 587→112 行、`routes/device_gateway_ws_handlers.py` 468→260 行、`session_memory/store_db.py` 361→129 行；新增 7 个职责单一子模块。
- **P2 死代码清理**：删除 `backends.py`、`device_intelligence/profile_store.py`、`device_intelligence/planner.py`、`session_memory/shadow_mode.py` 及对应测试。
- **P3 CI 强化**：`.github/workflows/test.yml` 增加 `ruff format --check` 与 `pyright` 权威文件类型检查。
- **P4 全仓格式化**：`ruff format .` 统一 412 个文件风格。
- **验证**：
  - 全量 `pytest` → **1662 passed, 23 skipped, 0 failed**；
  - AI→Motion 发布门聚焦测试 → **173 passed, 3 skipped**；
  - `ruff check .`、`ruff format --check`、pyright 权威文件均 clean；
  - 证据文档 `docs/release_evidence/2026-06-17-M13-code-quality-gate-evidence.md`。
- **提交**：`4d5ef77`、`41b9389`、`9dce12a`、`297fba4`、`cd5edca` 已 push 到 `origin main`。

### 最近完成（2026-06-16）拆分四个热路径 oversized 函数

- **实现**：
  - `routing_selector.py::select` 拆为池解析、初始筛选、guard 过滤、评分、ML boost、排序、pin 等私有 helper。
  - `server_lifespan.py::lifespan` 拆为 `_run_startup_phases` / `_run_shutdown_phases`。
  - `routes/chat_stream.py::stream_response` 拆为图片/thinking/编排/speculative/fallback helper。
  - `device_gateway/device_draw_handler.py::handle_device_draw` 拆为响应构造、预设图形、图片生成、SVG 转换优化 helper。
- **验证**：
  - 路由相关：`tests/test_routing_engine.py tests/test_routing_guard.py tests/test_routing_weights.py` → 35 passed。
  - 系统/聊天：`tests/test_system_endpoints.py tests/test_chat_handler.py` → 15 passed；`server_lifespan` import ok。
  - 设备绘图：`tests/test_draw_prompt_enhancer.py tests/test_device_gateway_model_routing.py` → 43 passed。
  - `ruff check .` clean；`scripts/check_code_size.py` 不再报告上述 4 个文件/函数超标。
- **提交**：`7e029e5` refactor + `710d26f` fixup 已 push 到 `origin main`。

### 核心功能
- **设备网关**: ESP32 绘图机/写字机云端控制
- **AI 路由**: 170+ 后端智能路由（设备任务 + 聊天/编码）
- **任务管理**: 任务创建、派发、执行、监控、恢复
- **设备策略**: 安全策略、固件兼容性、路径验证、route_policy/backend 字段贯通

### 当前开发文档入口（2026-06-16）

- **设备开发入口**：[`docs/DEVICE_DEVELOPER_GUIDE_CN.md`](docs/DEVICE_DEVELOPER_GUIDE_CN.md) 汇总设备联调、常用测试、证据要求和最小闭环。
- **下一阶段计划**：[`docs/superpowers/plans/2026-06-16-lima-author-intent-and-next-plan.md`](docs/superpowers/plans/2026-06-16-lima-author-intent-and-next-plan.md) 明确 G1–G4：AI→Motion 发布门、模型准入复跑、证据边界瘦身、启动/部署不确定性降低。
- **协议开发闭环**：[`docs/device_protocol_alignment.md`](docs/device_protocol_alignment.md) 已补充 `hello` → `task_dispatch` → `motion_event` → 终态证据的调试路径，并明确 `route_policy` 为下行任务硬契约。
- **ECC 工程流程**：[`docs/ECC_WORKFLOW_CN.md`](docs/ECC_WORKFLOW_CN.md) 定义项目采用的 Plan First / TDD / Code Review / 提交规范，以及 `.kimi-code/rules/ecc-workflow.md` 本地 rule。
- **Ponytail 精简顾问**：[`docs/AGENTS_PONYTAIL.md`](docs/AGENTS_PONYTAIL.md) 引入 lazy senior dev 决策阶梯，LiMa 硬规则优先。

### 最近完成（2026-06-17）生成 G1/G2 证据文档（步骤 4）

- **G1**：`docs/release_evidence/2026-06-17-M13-AI-to-Motion-regression.md` 记录热路径拆分/覆盖率提升后的端到端回归证据。
- **G2**：`docs/model_admission/2026-06-17-device-drawing-writing-evidence.md` 记录模型准入复跑结果。
- **验证**：`pytest tests/test_fake_u1_cloud_loop.py tests/test_device_draw_handler.py tests/test_motion.py -q` → **28 passed**。
- **提交**：`7806247` 已 push 到 `origin main`。

### 最近完成（2026-06-17）提升 device_gateway 测试覆盖率（步骤 3）

- **新增**：`tests/test_device_draw_handler.py`（11 cases）、`tests/test_motion.py`（13 cases）。
- **验证**：`pytest` 聚焦 35 passed；`device_gateway` 覆盖率从 65.7% 提升至 **71.1%**。
- **提交**：`7f4c93b` 已 push 到 `origin main`。

### 最近完成（2026-06-17）拆分热路径大函数 + 清理死代码（步骤 1-2）

- **拆分**：`routing_selector.select` → 21 行；`server_lifespan.lifespan` → 8 行；`routes/chat_stream.stream_response` → 47 行；`device_gateway/device_draw_handler.handle_device_draw` → 45 行。
- **死代码清理**：删除 `webhook_activity_buffer.py`（109 行）；`context_pipeline` lazy import 模块按 `CODEBASE_COLD_PRUNE_PRIORITY_CN.md` 保留。
- **基线更新**：`scripts/check_code_size.py` → 23 个 >300 行文件、99 个 >50 行函数。
- **验证**：路由/系统/聊天/设备绘图聚焦测试 87 passed；`ruff check .` clean。
- **提交**：`7e029e5`、`710d26f`、`a89790d`、`f583784` 已 push 到 `origin main`。

### 最近完成（2026-06-17）接入 Ponytail「lazy senior dev」顾问规则

- **实现**：
  - 克隆 [Ponytail](https://github.com/DietrichGebert/ponytail) 到 `reference/ponytail/`。
  - Cursor：`.cursor/rules/ponytail.mdc` + 全局 `~/.cursor/rules/ponytail.mdc`。
  - Kimi：`.kimi-code/rules/ponytail.md` + 全局 `~/.kimi-code/rules/ponytail.md`。
  - OpenCode / Claude / Codex：通过 `AGENTS.md` / `CLAUDE.md` / `docs/AGENTS_PONYTAIL.md` + 全局 AGENTS 条件章节引入。
  - 所有 Ponytail 规则前置 LiMa 覆盖声明：安全、验证、测试门禁、文档同步不可简化。
- **验证**：`ruff check .` clean；`AGENTS.md` 265 行、`CLAUDE.md` 162 行（均 ≤300）。
- **提交**：`3f6d046`、`3ddee70` 已 push 到 `origin main`。

### 最近完成（2026-06-17）按 ECC 开发流程重新整理 LiMa（阶段 1-3 完成）

- **流程文档**：更新 `AGENTS.md` 新增 ECC 章节；新增 `docs/ECC_WORKFLOW_CN.md`；新增 `.kimi-code/rules/ecc-workflow.md` 本地 rule。
- **度量门禁**：安装 `pytest-cov` 并配置覆盖率；新增 `scripts/check_code_size.py`（检查 >300 行文件、>50 行函数）；更新 `scripts/run_pre_commit_check.py` 集成尺寸检查作为 warning；记录基线到 `findings.md`。
- **Top 3 生产文件拆分**：
  - `device_gateway/protocol.py` → `protocol_core/validators/frames/lifecycle.py`（接口兼容，原文件改为 facade）。
  - `device_gateway/path_pipeline.py` → `path_data/text_renderer/svg_parser/preview_svg.py`（接口兼容，原文件改为 facade）。
  - `routes/device_gateway_ws_handlers.py` → `routes/ws_lifecycle_helpers.py` + `routes/ws_task_helpers.py`。
- **验证**：受影响模块回归 81 passed；`ruff check .` clean；`pyright` 改动文件 0 errors；尺寸检查从 26 个 >300 行文件降至 23 个。
- **提交**：`027217b`、`021fb6b`、`7423cfd`、`c378d00` 已 push 到 `origin main`。

### 最近完成（2026-06-17）AI 绘画 prompt 优化 + Wanx 模型更新

- **新增**：`device_gateway/draw_prompt_enhancer.py`，将用户描述包装为笔绘机约束 prompt。
- **修改**：`device_gateway/device_draw_handler.py` 调用增强 prompt；默认模型从 `wanx-v1` 改为 `wanx2.1-t2i-turbo`（`wanx-v1` 已不可用）。
- **新增测试**：`tests/test_draw_prompt_enhancer.py`（11 cases）。
- **验证**：聚焦测试 75 passed；ruff clean；VPS `ALIYUN_API_KEY` live 生成「一只猫」成功。
- **规模**：`python_files=656`，`python_lines=77,584`。

### 最近完成（2026-06-17）可选 P5 余项：`lima_mcp/` HTTP 路由退役

- **删除**：`lima_mcp/` 目录（13 个文件，~1.2k 行）；`tests/test_mcp_access_plane.py`、`tests/test_hypothesis_fs_allowlist.py`。
- **更新**：`routes/route_registry.py` 移除 `lima_mcp.server` 注册；`pyrightconfig.json` 移除 `"lima_mcp/"`；`docs/CODEBASE_COLD_PRUNE_PRIORITY_CN.md` 更新 P5 状态。
- **保留**：`lima_mcp_stdio/` 作为独立 stdio MCP 入口（`lima-mimo-mcp` CLI）。
- **验证**：聚焦门 77 passed；`ruff check .` clean。
- **规模**：`python_files=654`，`python_lines=77,460`。

### 最近完成（2026-06-17）可选 P5：GitHub/Gitee webhook 路由退役

- **删除**：`routes/github_webhook.py`、`routes/gitee_webhook.py`；`github_webhook/`、`gitee_webhook/` 包目录；`tests/test_github_webhook.py`、`tests/test_gitee_webhook.py`。
- **更新**：`routes/route_registry.py` 移除两个注册块；`scripts/check_vps_environment.py` 移除 webhook secret 检查；`tests/test_vps_environment_check.py` 改用 `LIMA_ADMIN_TOKEN` 示例；`.env.example` 移除 `GITHUB_WEBHOOK_*` / `GITEE_WEBHOOK_*`；`docs/CODEBASE_COLD_PRUNE_PRIORITY_CN.md` 更新 P5 状态。
- **验证**：聚焦门 `pytest tests/test_retrieval_injection.py tests/test_routing_engine.py tests/test_device_gateway_model_routing.py tests/test_provider_automation_admission.py -q` → **77 passed**；`ruff check .` clean。
- **规模**：`python_files=670`，`python_lines=79,447`。

### 最近完成（2026-06-17）G1 后续：假 U1 运动执行闭环证据

- **新增测试**：`tests/test_fake_u1_cloud_loop.py`（4 cases）
  - 云端 `home` / `write hi` / `svg M0,0 L10,0 L10,10`（`draw_generated`）命令经 `/device/v1/tasks` → WebSocket `task_dispatch` → `fake_device_server` → fake U1 TCP 执行 → `/device/v1/events` 终态 `done`。
  - 校验 `motion_task` 到 Edge-D 命令序列的转换契约。
- **验证**：`pytest tests/test_fake_u1_cloud_loop.py -v` → **4 passed**；`ruff check` clean。
- **证据更新**：`docs/release_evidence/2026-06-16-M13-AI-to-Motion-release-gate.md` 门 B「假 U1 运动执行」状态改为 ✅。

### 最近完成（2026-06-17）阶段 1 步骤 3：Edge-C 产品端 motion_task 示例

- **新增示例**：`esp32S_XYZ/docs/schemas/edge_c/examples/`
  - `motion_task.write_text.downlink.json`：`route_role=device_write`，`backend=scnet_ds`，`source_capability=write_text`。
  - `motion_task.draw_generated.downlink.json`：`route_role=device_draw`，`backend=dashscope_wanx`，`source_capability=draw_generated`。
  - 现有 `motion_task.downlink.json`（home / device_control）与 `motion_task.run_path.downlink.json`（device_vector）已覆盖其余两种 route_role。
- **验证**：`python esp32S_XYZ/tools/validate_schemas.py` → **64 passed**；子模块 `esp32S_XYZ @ fac1eec` 已 push；LiMa 主仓库子模块指针已更新。

### 最近完成（2026-06-17）G4 启动与部署不确定性降低

- **目标**：降低启动和部署不确定性，把耗时任务拆分为 ready 必须完成与 warming 可后台完成。
- **发现**：
  - 通过 `server_lifespan.py` 阶段日志定位到真正瓶颈：**`context_pipeline.auto_indexer` 在事件循环中运行，ChromaDB/ONNX 模型下载/解压阻塞了主事件循环**，导致 `/health` 长时间无法 ready。
  - 次要瓶颈：`channel_retirement.telegram` 同步调用 Telegram API 耗时约 1.7s。
- **修复**：
  - `context_pipeline/auto_indexer.py`：把 `_indexer_loop` 从 asyncio task 改为 daemon thread，扫描（含 ChromaDB 初始化）不再阻塞事件循环。
  - `server_lifespan.py`：把 `retire_telegram_webhook_from_env()` 改为 `asyncio.create_task` 后台执行。
- **结果**：
  - VPS 启动从约 **7 分钟** 降至约 **8 秒**（systemctl start → `/health` 200）。
  - `/health` 返回 `startup.status=ready` 和 `startup.phases` 数组。
  - 公网 smoke：`https://chat.donglicao.com/health` 200；`/device/v1/health` 200。
- **验证**：
  - `pytest tests/test_routing_engine.py tests/test_system_endpoints.py tests/test_retrieval_injection.py -q` → **34 passed**。
  - `ruff check server_lifespan.py context_pipeline/auto_indexer.py routes/system_endpoints.py` → clean。

### 最近完成（2026-06-17）G3 证据边界瘦身（小批）

- **目标**：沿证据边界删除一个冷区模块，保护热路径。
- **审计**：`python scripts/codegraph_orphans.py --fanin` 识别 `eval_status.py` 为 ORPHAN。
- **删除**：`eval_status.py`（115 行）；保留与其余 eval 模块有依赖的 `eval_pinned_call.py`、`eval_preflight.py`、`eval_quiet.py` 等。
- **验证**：eval 聚焦套件 23 passed / `ruff check .` clean / CodeGraph + ripgrep 确认无生产引用。

### 最近完成（2026-06-17）G2 设备模型准入复跑

- **目标**：执行作者意图计划 G2，让 `device_draw` / `device_vector` / `device_write` / `device_control` 的准入依据可复跑、可比较、可回滚。
- **修复**：原 `docs/model_admission/2026-06-16-device-drawing-writing.md` 因 Windows 控制台重定向编码错误变为 ISO-8859 二进制损坏，已删除并重建为 `docs/model_admission/2026-06-17-device-drawing-writing.md`。
- **报告**：按 `docs/model_admission/TEMPLATE.md` 补齐元数据、角色详情、路由偏好配置、准入门控和可复现命令。
- **验证**：
  - `python scripts/eval_device_model_role.py --all` → 6 角色 admit/admit_conditional，2 角色 defer，0 fail。
  - `pytest tests/test_device_gateway_model_routing.py -q` → **32 passed**。
  - `pytest tests/test_routing_engine.py -q --tb=short` → **24 passed**。
  - `ruff check` 触及文件 clean。
- **文档同步**：`docs/README.md` 最新准入报告索引更新为 2026-06-17 版本。

### 最近完成（2026-06-17）第二轮瘦身：零引用模块 + 归档脚本清理

> 两轮合计：794→684 文件（-110），93,145→80,546 行（-12,599）

- **14 个零生产引用模块删除**：`coding_eval`、`edit_protocol`、`esp32s_adapter/`、`eval_call`、`eval_digest`、`eval_registry`、`free_web_ai_admission`、`health_summary`、`healthchecks_io`、`mimo_stt`、`notify/`、`request_context_preflight`、`streaming_events`、`converters/` + 对应测试
- **归档脚本清理**：`scripts/archive/` 13 个文件（deploy_legacy + openclaw_retired + key_rotation_legacy）
- **配置同步**：`codegraph_orphans.py`、`pyrightconfig.json`、`ruff.toml` 移除已删模块条目
- **测试修复**：`test_eval_topology.py` 移除 `eval_call` 测试；`test_secret_hygiene.py` 移除归档断言
- **验证**：ruff clean；全量测试 1637 passed / 24 skipped / 4 pre-existing failures

### 最近完成（2026-06-17）大子系统审计瘦身

> 审计范围：`search_gateway`、`channel_gateway`、`routes/` + 全仓冷模块扫描
> 详见 [`docs/CODEBASE_SUBSYSTEM_TIER_CN.md`](docs/CODEBASE_SUBSYSTEM_TIER_CN.md) §13 和 [`docs/CODEBASE_COLD_PRUNE_PRIORITY_CN.md`](docs/CODEBASE_COLD_PRUNE_PRIORITY_CN.md) P6

- **channel_gateway 整体退役**：23 文件 + `routes/channel_gateway.py` + 13 测试删除；`route_registry.py` 注册块移除；`channel_retirement.py` RETIRED_CHANNELS 标记
- **冷模块清理**：`research/`、`web_reverse_eval.py`、`cli_status.py`、`sandbox/`、`data_workbench/`、`ops_entrypoint/` 共 6 个模块 + 测试删除
- **search_gateway 死适配器**：`zhihu_adapter.py`、`public_feeder.py`、`codesearch_status.py`、`policy.py` 删除
- **空目录与死 shim**：`eval_loop.py` 删除；`evals/`、`fragments/`、`reverse_gateway/`、`routes/.omc/` 清理
- **配置同步**：`pyrightconfig.json`、`deploy_unified.py`、`codegraph_orphans.py` 移除 channel_gateway 条目
- **验证**：ruff clean；全量测试 1736 passed / 25 skipped / 4 pre-existing failures（无新增）

### 最近完成（2026-06-16）阶段 2 续 — Image Generator 真实 API 夹具

- **`tests/test_dashscope_image_live.py`**：Wanx 同步 + 异步轮询；`ALIYUN_API_KEY` + `LIMA_DEVICE_ADMISSION_LIVE=1` 启用
- **`eval_device_model_role.py --live`**：image_generator 合并 live 目标；默认离线 7 passed
- **文档**：`docs/model_admission/TEMPLATE.md`、`.env.example`、`2026-06-16-device-drawing-writing.md`
- **验证**：`pytest tests/test_eval_device_model_role.py tests/test_dashscope_image_client.py tests/test_dashscope_image_live.py` → **12 passed**（live 无密钥时 skip）

### 最近完成（2026-06-16）M13 AI→Motion 发布证据模板

- **重写** `docs/release_evidence/TEMPLATE_AI_TO_MOTION_RELEASE.md`：对齐门 A–F、`RELEASE_GATE_CHECKLIST`、假 U8 环与真实 pytest 命令；替换原通用占位表
- **新增** `docs/release_evidence/README.md`；`docs/README.md` 索引
- **验证**：`pytest tests/test_device_gateway_model_routing.py` + `test_fake_u8_hello_heartbeat_transcript_motion_event_loop` → **33 passed**

### 最近完成（2026-06-16）M9–M12 设备路由与准入

- **M9 假 U8 消费 route_policy**：固件 `fake_lima_u8` 硬契约解析 + JSONL 证据；主仓稳定性门测试对齐
- **M10 路由制品证据**：`task_recorder` 全场景 `route_evidence`（创建/阻止/验证失败/恢复/终端消费）
- **M11 模型准入脚手架**：`docs/model_admission/TEMPLATE.md` + `scripts/eval_device_model_role.py`（8 角色评测）
- **M12 Profile 路由输入**：`enrich_route_policy_with_profile()` 接入 `resolve_device_route_policy()`；不完整 profile 审批门控
- **准入快照**：`docs/model_admission/2026-06-16-device-drawing-writing.md`

### 最近完成（2026-06-15）Hardware AI Phase 1 M5–M8 Closeout + 清理

- **M5 Recovery + Reliability**：`execute_recovery()` 实现 retry/home/stop 决策；重试耗尽后 action 改为 `"stop"`；retry 任务 WS 直发时从 pending queue 移除，避免双发；task store 增加 `increment_retry_count` / `reset_task_for_retry` / `remove_pending_task`；`RedisDeviceTaskStore` 补齐相同协议
- **M6 Memory + Continuous Learning**：新增 `device_memory/extractor.py` / `consolidation.py` / `recall.py` / `quality_gates.py` / `store.py` / `routes/device_memory.py`；terminal 事件自动提取 episode 与 failure pattern；episode ID 加入 `event_id` 防止重试历史覆盖；memory 提取失败改为 `logger.warning`（符合 AGENTS.md 无静默降级）；`MemoryStore` 加 RLock 并标注生产化 TODO
- **M7 External Enrichment + Support/Ops**：`device_support/snapshot.py` 提供 shadow/firmware/self-check/近期终端任务/故障告警/脱敏建议；support snapshot 过滤 24h 时间窗口；`external_enrichment` 天气/节假日 provider 验证可用
- **M8 OTA + Release Gate**：`device_ota/release.py` + `canary.py` + `routes/device_ota.py`；新增 `/deploy/{version}`、`/canary/record-success/{device_id}`、`/canary/record-failure/{device_id}`、`DELETE /canary/devices/{device_id}`；未知 criteria 返回 400；gate 未就绪时 deploy 返回 412；部署新版本自动重置 canary 计数
- **代码审查修复**：review 发现的 6 个 P0/P1 问题全部修复，新增 20+ 测试覆盖去重、Redis store 协议、OTA 路由、support 时间窗口
- **死区代码清理**：删除 `routes/ops_probe_ingest.py`、`converters/anthropic_format.py`、`deploy/key_rotation.py`、`scripts/vps_eval_smoke_remote.py` 等 4 个死文件
- **Anthropic 残留清理**：移除 `/v1/messages` 端点及所有 Anthropic 转换函数（chat_endpoints.py 363→142 行）；route_registry.py 移除 4 个 anthropic 字段 + 7 个 agent_* 硬编码 False
- **配置死路径清理**：pyrightconfig.json 移除 agent_runtime/voice_gateway/code_orchestrator_context 等 8 个不存在的 include/exclude 路径；ruff.toml 移除 8 个不存在 exclude 路径；deploy_unified.py 移除 agent_runtime core dir + m1m5 slice + eval smoke 代码
- **文档清理**：归档 task_plan.md、OPS_ENTRYPOINTS_CN.md、FREE_MODEL_ROUTING_STATUS_CN.md、MODEL_CATALOG.md、ROUTING_ENGINE_DESIGN.md、PLAN_CLOSURE_STATUS.md 至 docs/archive/；删除 root-historical 21 个个人编码助手时代遗物；归档 21 个已完成 superpowers/plans 至 docs/archive/superpowers-2026-06/
- **findings.md 轮转**：拆分 2026-05 CQ-046 至 CQ-110 旧记录至 docs/archive/findings-2026-05.md（1094→204 行，148KB→18KB）
- **route_policy backend 字段贯通**：`resolve_device_route_policy` 复用 `get_preferred_backend` 填充 backend，route_policy 携带真实后端（如 dashscope_wanx）；固件 edge_c/edge_b schema 加可选 backend 字段
- **Edge-C motion_task route_policy 硬契约**：schema required 化（固件 edge_c）+ 固件 DeviceServer 与云端 xiaozhi_compat 两条下行链路补 route_policy
- **双端语义统一**：`CONTROL_CAPABILITIES` 重构为单一真相源（model_routing.py）并补 `estop`；固件 generate_route_policy 对齐云端 resolve（run_path→device_vector）
- **固件子模块指针**：更新至 esp32S_XYZ `a4cab61`；详见 findings.md 与 spec/plan

### 最近完成（2026-06-15）代码质量治理 Q0–Q7 Closeout

权威计划：[`docs/archive/superpowers-2026-06/2026-06-15-code-quality-governance-plan.md`](docs/archive/superpowers-2026-06/2026-06-15-code-quality-governance-plan.md)

- **Q0 统计/CI**：`repo_stats.py` 排除 `.venv*`；`CLAUDE.md` 规模更正；P13 静默 `except: pass` 门恢复
- **Q1 route_policy**：`esp32s_adapter` 委托 `resolve_device_route_policy`（`run_path`→`device_vector`）
- **Q2 tasks 拆分**：`device_gateway/tasks.py` 521→68 行 facade + task_creation/events/lifecycle/deps
- **Q3 routing_executor**：显式 `import health_tracker` / `budget_manager`
- **Q4 Store 生产化**：Memory/Ledger env 切换（`memory|redis`）；health 暴露 store 后端
- **Q5 超标文件拆分**：channel_gateway、orchestrate、admin_api_extra、eval_loop→scripts、routing_intent、speculative
- **Q6 测试卫生**：`test_provider_automation` / `test_ops_metrics` 拆为 4+4 域文件；`tests/README.md` 聚焦/全量门
- **Q7 战略评估**：[`docs/CODEBASE_SUBSYSTEM_TIER_CN.md`](docs/CODEBASE_SUBSYSTEM_TIER_CN.md) hot/warm/cold 分层

### 测试结果（治理切片）

```text
Q0–Q3 聚焦: 112 passed
Q6 拆分套件: 83 passed, 1 skipped
Q7 文档验证切片: 22 passed
聚焦 device 套件: 452 passed
ruff check: clean（触及文件）
公网 health: https://chat.donglicao.com/health = 200
```

### 当前活跃路线图
- 旧“个人编码助手”优化路线图阶段 1-5 已关闭
- 新战略路线图见 [`docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md`](docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md)，M9–M12 已关闭；下一阶段 M13 发布证据模板

## 退役模块

| 模块 | 状态 | 说明 |
|------|------|------|
| LiMa Code CLI (deepcode-cli) | ✅ 已退役 | 子模块已移除 |
| Telegram bot/operator | ✅ 已退役 | 路由/webhook 已移除 |
| WeChat 集成 | ✅ 已退役 | 桥接代码已归档 |
| agent_runtime 路由 | ✅ 已退役 | HTTP 路由已移除 |
| Anthropic `/v1/messages` 兼容层 | ✅ 已退役 | 端点与转换函数已移除 |
| channel_gateway（WeChat 绑定层） | ✅ 已退役 | 2026-06-17；23 文件 + 路由 + 13 测试删除；`channel_retirement.py` 标记 |

## 部署状态

- **主 VPS**: Alibaba Cloud 47.112.162.80
- **备用节点**: JDCloud 117.72.118.95
- **公网健康检查**: chat.donglicao.com/health = 200（2026-06-16 19:15 恢复；此前因 `device_ledger.store` 缺失 `configure_ledger_store_from_env` 导致 systemd 反复崩溃）
- **设备网关**: chat.donglicao.com/device/v1/health = 200
- **VPS 启动耗时**: 约 7 分钟（backend retirement / probe loop 历史数据分析预热），之后服务完全可用
- **最近恢复操作**: 部署 15 个 store/memory/notifier/gateway/lifespan 文件，备份 `/opt/lima-router/backups/unified-files-20260616_190649/runtime-before.tgz`

## 代码质量

| 项目 | 状态 |
|------|------|
| P0 违规 | ✅ 已修复 |
| xiaozhi_v1_compat 重构 | ✅ 完成 (1184→518, 7 模块) |
| admin_ui 模块化 | ✅ 完成 (482→55, 4 模块) |
| ops_metrics 重构 | ✅ 完成 (3 模块拆分) |
| tasks.py 拆分 | ✅ 完成 (task_recorder.py) |
| legacy 路由/HTTP 栈退役 | ✅ 完成 |
| route_policy backend 字段贯通 | ✅ 完成 |
| Edge-C route_policy 硬契约 | ✅ 完成 |
| 代码质量治理 Q0–Q7 | ✅ 已关闭（见 governance plan） |
| channel_gateway / orchestrate / admin 拆分 | ✅ 完成 |
| Memory/Ledger Redis 后端 | ✅ 完成（env 切换） |

## 已知技术债务与注意事项

- **启动时间**：VPS 启动需约 7 分钟，主要消耗在 backend profile / retirement 历史数据分析；这些初始化目前阻塞 lifespan 完成，导致 health 等待较长。后续应改为后台预热或并行启动。
- **本地/远程双环境**：Windows 本地代理后端、FRP `:8088`、VPS 直接后端共存，新增后端需明确拓扑归属
- **context_pipeline 膨胀**：Hot 五模块外仍有大量 Cold 实验代码；见 `docs/CODEBASE_SUBSYSTEM_TIER_CN.md` P0–P4 建议
- **findings 历史**：2026-05 CQ-046~CQ-110 旧记录已归档至 `docs/archive/findings-2026-05.md`；当前 findings.md 仅保留 2026-06-09 战略转型后记录

## 关键文档

| 文档 | 用途 | 优先级 |
|------|------|--------|
| `docs/README.md` | 文档唯一入口与权威规则 | 必读 |
| `STATUS.md` | 当前项目状态（本文件） | 必读 |
| `docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md` | 当前活跃路线图 | 必读 |
| `docs/DEVICE_DEVELOPER_GUIDE_CN.md` | 设备开发、联调、验证入口 | 必读 |
| `docs/CODEBASE_SUBSYSTEM_TIER_CN.md` | 子系统 hot/warm/cold 分层 | 推荐 |
| `AGENTS.md` | 开发约定与命令 | 必读 |
| `docs/ARCHITECTURE.md` | 系统架构 | 推荐 |
| `docs/REQUEST_PIPELINE_AUTHORITY_CN.md` | 生产路由所有权 | 推荐 |
| `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md` | 设备模型路由策略 | 推荐 |
| `docs/ESP32S_XYZ_MANAGEMENT_CN.md` | 产品子模块边界 | 推荐 |
| `docs/LIMA_MEMORY_CN.md` | 持久跨会话记忆 | 推荐 |
