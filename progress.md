# Personal Coding Assistant Progress

> Created: 2026-05-22

> Updated: 2026-06-13
> 注：2026-05-31 及更早的记录已归档到 [docs/archive/progress-2026-05.md](docs/archive/progress-2026-05.md)。

## 2026-06-13 项目文档更新与瘦身清理

- C1：删除根目录零引用 Python 模块 10 个（append_datasets.py、capture_prompt.py、closed_loop.py、deep_context.py、generate_routing_data.py、grpo_train.py、intent_templates.py、router_classifier_final.py、verify_router.py、worker_daemon.py）
- C3：清理 scratch/debug/tmp 脚本、日志、根目录 stray tests（test_muyuan*.py、test_sharedchat*.py、test_vps_route.py 等）
- C4：删除占位 device_memory 子系统（routes/device_memory.py + device_memory/{consolidation,extractor,quality_gates,recall}.py）
- C5：删除本地缓存与 IDE/agent 状态目录（.omc、.omx、.mimocode、.qoder、.reasonix、.codegraph、_codegraph_repo、.learnings、.hypothesis、.pytest_cache、.ruff_cache、__pycache__），释放约 100+ MB
- C6：移除已跟踪二进制/运行时产物（router_model.pkl 1.4MB、deploy_xiaozhi.tar.gz、emu_screen.png、GIT_STATUS.txt）及本地凭证类文件（cpk.json、kimi.txt、kimi_session_vps.json）
- C7：归档历史文档 22 份到 docs/archive/cleanup-2026-06/root-historical/（含 AGENTS_CN.md、May-18 prompt/model 文档、里程碑报告等）
- C8：更新 README.md、AGENTS.md、docs/REQUEST_PIPELINE_AUTHORITY.md 中的失效引用与退役子系统描述
- C9：legacy 路由/HTTP 栈退役
  - 删除：smart_router.py、router_http*.py、router_circuit_breaker.py、router_intent.py、router_image.py、router_prompt.py、auto_retrain.py、oldllm_*.py、patch_server_v3.py、scripts/validate_via_router.py、scripts/test_route_e2e.py
  - 迁移调用方：server.py、routes/admin_api.py、routes/system_endpoints.py、routes/health_dashboard.py、routes/chat_support.py、routes/chat_post_closeout.py、routes/chat_handler_dispatch.py、routes/chat_stream.py、orchestrate.py
  - 新增 `routing_intent.py` 承载 thinking/image 意图检测
  - 新增 `health_state.get_backend_quality()` 支撑 admin/health dashboard 的熔断兼容视图
  - 删除相关测试：test_router_http.py、test_router_image.py、test_vision_routing.py、test_router_circuit_breaker.py、test_oldllm_*.py
  - 保留：router_classifier.py、router_local.py（orchestrate.py 仍依赖，作为后续里程碑）
- 验证：ruff clean；pytest focused suite 95 passed

## 2026-06-13 C10：router_classifier/router_local 清零

- 在 `routing_intent.py` 新增 `analyze_intent()`，完整承接 `router_classifier.analyze()` 的规则/信号/上下文分类逻辑
- `orchestrate.py`：
  - 删除 `router_classifier`、`router_local` 导入
  - 使用 `routing_intent.analyze_intent()` 进行编排触发判断
  - 内联 `_call_local_router()` 替代 `router_local.call_local()`，保留 `LOCAL_ROUTER_URL` 环境变量行为
- `routes/chat_handler_dispatch.py`：流式/非流入口统一改用 `routing_intent.analyze_intent()`
- 更新测试：`tests/test_router_classifier.py` 改为测试 `routing_intent.analyze_intent()`；`tests/test_prompt_memory_recall.py` 移除对 `server.smart_router` 的死 monkeypatch，改 mock `routing_intent`
- 清理配置：`scripts/deploy_unified.py` 核心文件列表替换为 `routing_intent.py`；`pyrightconfig.json` 移除 `router_classifier.py` / `smart_router.py`
- 删除：`router_classifier.py`、`router_local.py`
- 修复 `scripts/run_ruff_check.py`：过滤 `git ls-files` 中已不存在于工作区的 tracked 路径，避免删除文件未提交时 ruff gate 误报 E902
- 验证：ruff clean；pytest focused suite 通过

## 2026-06-13 C10 部署修复：routing_engine budget_manager 重导出

- 问题：VPS `routing_executor.py` 仍通过 `re.budget_manager` 访问预算管理器，`routing_engine.py` 在 facade 拆分后未再导入 `budget_manager`，导致 chat 请求 500 (`AttributeError`)。
- 修复：`routing_engine.py` 增加 `import budget_manager`，恢复模块级属性暴露。
- 验证：ruff clean；pytest focused suite `54 passed`。

## 2026-06-13 C10 VPS 部署与验证

- 部署方式：git bundle 同步 HEAD 到 `/opt/lima-router`，清理 C9 遗留文件（`smart_router.py`、`router_http*.py`、`router_circuit_breaker.py`、`router_image.py`、`router_intent.py`、`router_prompt.py`、`auto_retrain.py`、`oldllm_*.py`、`patch_server_v3.py`、`scripts/validate_via_router.py`、`scripts/test_route_e2e.py`）。
- 服务启动：VPS 启动耗时约 2.5 分钟（backend profile / retirement 分析）。
- 健康检查：
  - VPS local `http://127.0.0.1:8080/health` → HTTP 200
  - Public `https://chat.donglicao.com/health` → HTTP 200，`modules.telegram=false`
  - Public `https://chat.donglicao.com/device/v1/health` → HTTP 200
- Chat smoke：VPS local `POST /v1/chat/completions` model=`code`，prompt=`Return exactly: c10-deploy-ok` → HTTP 200，返回 exact `c10-deploy-ok`，backend=`cfai_qwen_coder`。
- Git：提交 `cb91611`、`4cd5cf8` 已推送 origin/main。

## 2026-06-13 阶段 1 Step 1：失败/阻止路径 route_policy 保留测试

- 目标：`docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md` 阶段 1 要求每个 `motion_task`（含失败/阻止）都保留 `route_policy`。
- 新增 `tests/test_device_gateway_route_policy_retention.py`（5 个测试）：
  - route_policy 校验失败路径保留 `route_policy` + `error`
  - 固件不兼容路径保留 `route_policy` + `error`
  - capability 参数校验失败路径保留 `route_policy` + `error`
  - policy 决策 `reject` 路径保留 `route_policy` + `policy`
  - policy 决策 `require_approval` 路径保留 `route_policy` + `policy`
- 验证：
  - 新增测试：`5 passed`
  - device 聚焦套件：`169 passed`
  - ruff clean

## 2026-06-13 Phase 5 xiaozhi compat 拆分收尾

- `xiaozhi_v1_compat.py`：518 → ~27 行（删除与子模块重复 helper）
- `xiaozhi_compat/shared.py` 拆为 7 个子模块 + barrel
- `xiaozhi_compat/device_routes.py`：231 → 185 行（Slice 5-C：activation 状态机拆到 `activation.py`）
- 新增 `routes/xiaozhi_compat/activation.py`（65 行）：激活码生成/校验/TTL 清理
- 测试：`test_xiaozhi_v1_compat_p0/p1` + `test_route_registry` 18 passed
- ruff：clean

## 2026-06-13 路由权威收敛 Phase 4 closeout

**目标：** bypass 归零 + 部署后 eval/executor 可证明可用。

- Phase 4-A：`deploy_unified.py` 240s health + 20s grace + eval smoke 自动/手动门控
- Phase 4-B：`REQUEST_PIPELINE_AUTHORITY.md` 流式 vs 非流式刻意差异文档化
- VPS：`vps_eval_smoke_remote.py` 手动 ✅；`deploy_unified --eval-smoke` 全链路 ✅（backup `unified-files-20260613_175344`）
- Git：`0980ed9`、`4add436` + 本轮 health 加固待提交

## 2026-06-11 Stage 1 Week 3C: 预设图形库部署完成

**目标:** 实现预设图形快速响应，跳过 DashScope API 调用。

- 实现:
  - 新增 `xiaozhi_drawing/preset_shapes.py` (110 行): 6 种基础图形生成
  - 修改 `device_gateway/device_draw_handler.py` (+21 行): 关键词检测与快速路径
  - 图形: 圆形、正方形、三角形、五角星、心形、月牙
  - 测试: 12 个测试全部通过（8 预设图形 + 4 集成）
- 性能提升:
  - 响应时间: 3-5 秒 → <100ms（预设图形）
  - API 调用: 1 次 → 0 次（基础图形）
  - 离线可用: 无需网络连接
- 业务价值:
  - 成本节省: 预设图形 0 API 费用
  - 用户体验: 30-50 倍速度提升
  - 可靠性: 网络故障时降级方案
- VPS 部署:
  - preset_shapes.py 和 device_draw_handler.py 已部署
  - 模块导入验证通过，circle 测试成功
  - 服务运行正常: PID 2923895，启动于 21:47
- 本地验证:
  - pytest: 12/12 测试通过
  - ruff: clean
  - 文件规模: preset_shapes.py 110 行
- Git 管理:
  - 提交: f418433 feat(Stage1-Week3C): Preset shape library
  - 推送: GitHub (origin) ✅

## 2026-06-11 Stage 1 Week 3B: 真实矢量化（OpenCV）部署完成

**目标:** 替换占位符 SVG 转换器，实现真实的位图转矢量路径。

- 实现:
  - 修改 `xiaozhi_drawing/svg_converter.py` (69 → 117 行): OpenCV 轮廓检测算法
  - 流程: 下载 → 灰度化 → 高斯模糊 → Otsu 二值化 → findContours → approxPolyDP 简化 → SVG path
  - 新增 `opencv-python-headless==4.10.0.84` 依赖
  - 更新测试以验证真实轮廓检测（contour_count 字段）
- 技术细节:
  - Otsu 自动阈值二值化（适应不同亮度图像）
  - Douglas-Peucker 轮廓简化（epsilon=2.0）
  - 多轮廓支持（每个轮廓独立 M...Z 路径）
  - 面积过滤（min_area=100，去除噪点）
- VPS 部署:
  - svg_converter.py 已更新（时间戳 21:27）
  - opencv-python-headless 安装成功（版本 4.10.0）
  - 模块导入验证通过，无错误
  - 服务运行正常: PID 2897167，启动于 21:29
- 本地验证:
  - pytest: 25/25 测试通过（包含 OpenCV 矢量化验证）
  - ruff: clean
  - 文件规模: 117 行，符合 <150 行目标
- Git 管理:
  - 提交: 09e4745 feat(Stage1-Week3B): OpenCV real vectorization
  - 推送: GitHub (origin) ✅
- 质量改进:
  - 从占位符矩形 → 真实图像轮廓
  - 支持复杂图像的多轮廓检测
  - 自动阈值算法，适应不同图像

## 2026-06-11 Stage 1 Week 3A: SVG 验证+优化 + device_draw 集成完成

**目标:** 实现 SVG 验证和路径优化，集成到 device_draw 流程。

- 实现:
  - 新增 `xiaozhi_drawing/svg_validator.py` (133 行): 解析/验证 M/L/C/Q/Z 指令，检查工作区边界，计算复杂度
  - 新增 `xiaozhi_drawing/path_optimizer.py` (187 行): Douglas-Peucker 简化算法，缩放适配，居中对齐
  - 修改 `device_gateway/device_draw_handler.py` (+37 行): 集成验证+优化步骤
  - 测试: 23 个测试全部通过 (10 validator + 10 optimizer + 3 integration)
- 功能验证:
  - SVG 验证: 坐标范围检查 (200x200 工作区)，复杂度限制 (max 5000 点)，错误/警告分级
  - 路径优化: 点数减少 30%+ (高密度路径)，保持宽高比，居中对齐 (180x180 目标尺寸)
  - 完整流程: DashScope 生成 → SVG 转换 → 验证 → 优化 → 设备执行
- VPS 部署:
  - 3 个文件已部署: svg_validator.py, path_optimizer.py, device_draw_handler.py
  - 模块导入验证通过，无错误
  - 服务运行正常: PID 2871231，启动于 21:13
- 本地验证:
  - pytest: 23/23 测试通过
  - ruff: clean，所有文件符合规范
  - 文件规模: 最大 187 行，符合 <300 行要求
- Git 管理:
  - 提交: e22326b feat(Stage1-Week3A): SVG validator + path optimizer + device_draw integration
  - 推送: GitHub (origin) ✅
- 残余风险:
  - SVG 转换器仍是占位符实现（Week 3B 补充真实矢量化）
  - 不支持椭圆弧 (A 指令)，仅支持 M/L/C/Q/Z
  - 笔顺未优化（按原始顺序）

## 2026-06-11 Stage 1 Week 2: DashScope Image API + Device Draw/Write 部署完成

**目标:** 实现图生功能并部署到 VPS。

- 实现:
  - 新增 `dashscope_image_client.py` (141 行): DashScope 文生图 API 客户端，支持 wanx-v1 和 flux-schnell 模型
  - 新增 `device_gateway/device_draw_handler.py` (93 行): device_draw 路由处理器，调用 DashScope API 并转换为 SVG
  - 新增 `device_gateway/device_write_handler.py` (56 行): device_write 确定性路由（无 LLM）
  - 新增 `xiaozhi_drawing/svg_converter.py` (68 行): 图像下载 + SVG 转换（当前为占位符实现）
  - 后端注册: `dashscope_wanx` (wanx-v1) 和 `dashscope_flux` (flux-schnell)
  - 测试: 8 个单元测试全部通过 (test_dashscope_image_client.py: 6, test_svg_converter.py: 2)
- VPS 部署:
  - 5 个文件已部署: dashscope_image_client.py, device_draw_handler.py, device_write_handler.py, svg_converter.py, backends_registry.py
  - 依赖安装: dashscope==1.20.11, Pillow==10.4.0 (pypotrace 等可选依赖因编译问题跳过)
  - 服务重启成功，健康检查通过: /health 返回 status=ok, device_gateway=true
  - 模块导入验证通过，后端注册确认
  - 备份位置: /opt/lima-router/backups/unified-files-20260611_203701/runtime-before.tgz
- 本地验证:
  - pytest: 8/8 测试通过
  - ruff: clean，所有文件符合规范
  - 函数复杂度: 最大 46 行，符合 <50 行要求
  - 文件规模: 最大 141 行，符合 <300 行要求
- Git 管理:
  - 提交: 8ca9433 feat(Stage1-Week2): DashScope image API + device_draw/write routing
  - 推送: GitHub (origin) ✅
- 残余风险:
  - SVG 转换器当前是占位符实现（返回矩形路径），真实矢量化需要后续补充
  - 可选依赖 (pypotrace, svgpathtools, shapely) 未安装，不影响当前功能

## 2026-06-09 Hardware AI Phase 1 M4: Planner + Simulator + Workflow Closeout

**Goal:** Make task creation an explicit workflow, not a route helper.

- Implementation:
  - added `device_intelligence/planner.py` — `plan_from_text()` wraps the
    gateway intent parser and produces immutable `TaskPlan` instances with
    unique plan_ids; `PlannerError` for empty/invalid input;
  - added `device_intelligence/simulator.py` — `simulate_motion()` computes
    draw distance, pen-up distance, estimated runtime, and risk score (0–1)
    from path geometry; `SimResult` is a frozen dataclass with `to_dict()`;
  - added `device_workflow/state.py` — `TaskState` enum (9 states: created
    → planned → simulated → waiting_approval → ready_to_dispatch → dispatched
    → running → recovering → terminal), `WorkflowEvent` enum, transition
    table, and `WorkflowTransitionError`;
  - added `device_workflow/orchestrator.py` — thread-safe
    `WorkflowOrchestrator` with register/advance/get_state/history/snapshot;
  - wired planner+simulator+workflow into `device_gateway/tasks.py`:
    `project_to_motion_task()` now registers tasks in workflow, runs
    simulation, and advances through CREATED→PLANNED→SIMULATED→READY_TO_DISPATCH
    (or WAITING_APPROVAL for high-risk tasks); `mark_task_dispatched()` and
    `record_motion_event()` advance workflow on dispatch/terminal events;
  - created 3 test files: `test_device_intelligence_planner.py` (19 tests),
    `test_device_intelligence_simulator.py` (17 tests),
    `test_device_workflow.py` (29 tests).
- Local verification:
  - focused pytest: all 65 M4 tests pass;
  - full device suite: `208 passed, 1 warning` (includes all M1–M4 + gateway tests);
  - ruff check clean on all 10 modified/created files.
- Residual risk:
  - Workflow is in-memory; SQLite/Redis durability deferred.
  - Risk threshold (0.7) for approval gating is a starting default; tuning
    requires real hardware evidence.
  - `create_task_from_transcript()` response format is backward-compatible;
    new keys (`simulation`, `workflow_state`) are additive.

## 2026-06-09 Hardware AI Phase 1 M3: Policy Engine + Protocol Registry Closeout

**Goal:** Centralize permission, safety, compatibility, and approval decisions
before task dispatch.

- Implementation:
  - added `device_policy/decisions.py` with 7 decision values (allow,
    require_approval, reject, require_self_check, require_home, require_ota,
    degrade_to_asset) and Chinese labels;
  - added `device_policy/engine.py` with 3-gate PolicyEngine: protocol
    compatibility → profile safety → capability match;
  - added `device_protocol_registry.py` with ProtocolRegistry dataclass
    mapping protocol version, min firmware, supported capabilities, and
    deprecated fields;
  - wired `policy_engine.decide()` into `device_gateway/tasks.py`
    `project_to_motion_task()` — stores policy result in task params,
    blocks dispatch with status="blocked" when decision is not "allow";
  - created `tests/test_device_policy_protocol_registry.py` with 23 tests
    covering decision vocabulary, protocol compatibility, and engine logic.
- Local verification:
  - focused pytest: `tests/test_device_ledger_artifacts.py
    tests/test_device_intelligence_safety.py
    tests/test_device_intelligence_schemas.py
    tests/test_device_intelligence_shadow.py
    tests/test_device_policy_protocol_registry.py
    tests/test_device_gateway_routes.py` →
    `57 passed, 1 warning`;
  - `py_compile` clean.
- Residual risk:
  - M3 is in-memory and interface-shaped; SQLite/Redis durability for
    policy decisions deferred to later milestones.
  - The policy engine currently uses string comparison for firmware
    versioning; a semver library would be more robust for real hardware.

## 2026-06-09 capacity-aware deploy + JDCloud probe closeout

**Goal:** make primary VPS deployment capacity-aware and turn the new JDCloud
server into a real, bounded monitoring/probe asset.

- Implementation:
  - added primary VPS deploy preflight to `scripts/deploy_unified.py`;
  - deploy preflight checks free disk under `/opt/lima-router` and
    `MemAvailable`, with `LIMA_DEPLOY_MIN_FREE_MB=512` and
    `LIMA_DEPLOY_MIN_MEM_MB=128` defaults;
  - non-dry-run deploys now create a remote tar backup before SFTP upload and
    print the rollback path;
  - added `scripts/check_jdcloud_node.py`, a read-only JDCloud smoke command
    that reports sanitized capacity, service state, and primary LiMa health;
  - added focused deploy/JDCloud pytest coverage.
- Local verification:
  - touched `py_compile`: clean;
  - focused pytest:
    `tests/test_deploy_unified.py tests/test_jdcloud_node_check.py` ->
    `10 passed`;
  - `scripts/run_ruff_check.py`: clean;
  - `git diff --check`: clean apart from Git CRLF normalization warnings;
  - `scripts/run_pre_commit_check.py --full`:
    `2074 passed, 10 skipped, 1 warning in 393.43s`;
  - deploy dry-run:
    `scripts/deploy_unified.py --dry-run --files scripts/deploy_unified.py`
    listed one safe upload.
- Primary VPS deploy and smoke:
  - final no-restart helper deploy:
    `scripts/deploy_unified.py --files scripts/deploy_unified.py scripts/check_jdcloud_node.py --no-restart`;
  - capacity preflight reported `disk_free_mb=13685`,
    `mem_available_mb=488`;
  - rollback backup:
    `/opt/lima-router/backups/unified-files-20260609_130457/runtime-before.tgz`;
  - upload result: `2 uploaded, 0 failed, 0 skipped`;
  - public `https://chat.donglicao.com/health` returned HTTP `200` and
    `modules.telegram=false`.
- JDCloud runtime evidence:
  - read-only smoke before activation returned `ok=true`,
    `chat_health_http_code=200`, `prometheus_service=active`,
    `disk_free_mb=41266`, and `mem_available_mb=2308`;
  - `lima-probe.timer` was enabled but inactive, then started and became
    active; next run was reported as `Wed 2026-06-10 00:18:10 CST`;
  - manual `systemctl start lima-probe.service` completed with
    `status=0/SUCCESS`;
  - discovery reported `37 new, 37 total known` and wrote
    `/opt/lima-probe/data/discoveries.jsonl` plus `known_providers.json`;
  - follow-up smoke returned `ok=true`, `lima_probe_timer=active`,
    `lima_probe_service=inactive`, `prometheus_service=active`,
    `disk_free_mb=41266`, and `mem_available_mb=1761`.
- Residual risk:
  - JDCloud browser helper requests to `http://127.0.0.1:8092/render` return
    HTTP `500`; keep port `8092` private and debug the helper as a separate
    small slice;
  - JDCloud key auth is not configured locally yet, so unattended checks need
    either SSH key setup or an operator-provided `JDCLOUD_SSH_PASSWORD`.

## 2026-06-09 pre-commit hook hygiene closeout

**Goal:** stop local commits from hanging on the wrong full-suite command while
keeping a real, repeatable LiMa quality gate available.

- Implementation:
  - added `scripts/run_pre_commit_check.py`;
  - default quick mode runs tracked-file ruff through
    `scripts/run_ruff_check.py`, staged whitespace via
    `git diff --cached --check`, and `py_compile` for staged `.py` files;
  - `--full` mode runs the documented CI-style pytest command with the same
    long/external ignore list used in closeouts;
  - `--full` now creates a unique `tmp/pytest-run-precommit-full-*`
    `--basetemp`, avoiding the Windows pytest temp cleanup issue seen during
    the first wrapper attempt;
  - local `.git/hooks/pre-commit.ps1` now delegates to the tracked wrapper.
- Verification:
  - focused CI gate pytest: `8 passed`;
  - `python scripts/run_pre_commit_check.py`: clean;
  - direct local hook run:
    `powershell.exe -ExecutionPolicy Bypass -File .git/hooks/pre-commit.ps1`
    clean;
  - `python scripts/run_pre_commit_check.py --full`:
    `2060 passed, 10 skipped, 1 warning in 656.60s`;
  - touched `py_compile`: clean;
  - focused ruff on touched files: clean.
- Residual risk:
  - `.git/hooks/pre-commit.ps1` is local Git metadata and is not committed;
    the durable behavior lives in `scripts/run_pre_commit_check.py`.
  - No VPS deploy was needed because this is local developer tooling only.

## 2026-06-09 JDCloud workspace hygiene closeout

**Goal:** keep the newly added JDCloud server as a real LiMa ops asset while
removing password-bearing local helper files and generated reports from normal
repository review noise.

- Implementation:
  - added `deploy/jdcloud/README.md` as the tracked manifest for non-secret
    JDCloud deploy templates;
  - added `docs/ops/JDCLOUD_RUNTIME_STATUS.md` as the sanitized runtime status
    and credential boundary;
  - updated `docs/ONLINE_DISTRIBUTIONS.md` and
    `docs/DOCUMENTATION_STATUS.md` so JDCloud is discoverable as a secondary
    provider-probe / monitoring node;
  - added exact `.gitignore` rules for local JDCloud password helpers,
    generated deployment reports, command transcripts, local cookies/sessions,
    root scratch scripts, and local agent/tool state;
  - ignored CodeGraph PID files and removed `.codegraph/daemon.pid` from the
    Git index without deleting the local runtime file;
  - retained the JDCloud tracked script changes that switch probe services from
    `python3.10` / `pip3.10` to the live server's `python3` / `pip3` path.
- Verification:
  - `git status --short` now shows only intentional JDCloud hygiene changes
    instead of the previous large scratch-file list;
  - local secret scan found password-bearing JDCloud helpers and those files
    were not staged;
  - `python -m py_compile provider_probe\browser_service.py provider_probe\discovery\scheduler.py`:
    clean;
  - `git diff --check`: clean apart from Git CRLF normalization warnings;
  - `git check-ignore -v` confirmed the known JDCloud password helpers,
    generated reports, root scratch files, local cookies, and CodeGraph PID are
    ignored;
  - bash is not available in this Windows shell, so `bash -n` syntax checks for
    the JDCloud shell scripts were skipped.
  - no JDCloud redeploy was performed in this slice.
- Residual risk:
  - any real JDCloud deployment still needs fresh SSH/service/smoke evidence;
  - if the password-bearing helper files were ever copied outside this local
    workspace, rotate the affected credentials.

## 2026-06-09 CI hygiene after retirement closeout

**Goal:** close the post-retirement gate noise that blocked the next LiMa
Server optimization slice, while preserving the Telegram retirement hard
boundary on all public surfaces.

- Implementation:
  - added missing split-registry entries for local/direct, DuckAI, XFYun,
    DashScope, and Zhihu coding backends still referenced by route pools;
  - removed phantom OpenRouter constants that had no registry definitions;
  - moved IDE fingerprints into `backends_constants.py` and kept
    `router_v3.detect_ide_by_fingerprints()` as the local helper;
  - changed `scripts/run_ruff_check.py` to lint git-tracked `.py` / `.pyi`
    files with `--force-exclude`, keeping scratch files out of the gate;
  - added `tests/test_ci_gates.py` coverage for tracked-file filtering and
    ruff config excludes;
  - added nginx edge-level `/telegram/` 404 guards for both
    `api.donglicao.com` and `chat.donglicao.com`.
- Local verification:
  - focused pytest:
    `tests/test_backend_registry.py tests/test_phase_b.py tests/test_health_tracker.py tests/test_ci_gates.py tests/test_channel_retirement.py tests/test_route_registry.py`
    -> `64 passed, 1 warning`;
  - `python -m py_compile` on touched runtime/wrapper files: clean;
  - focused ruff on touched Python files: clean;
  - `python scripts/run_ruff_check.py`: clean (`All checks passed!`);
  - focused pyright on touched production Python files: `0 errors`;
  - CI-style pytest with documented long/external ignores:
    `2056 passed, 10 skipped, 1 warning in 292.37s`;
  - `git diff --check`: clean apart from Git CRLF normalization warnings;
  - quick import check: missing registry entries `[]` and
    `router_v3.IDE_SOURCES is backends.IDE_SOURCES` returned `True`.
- VPS deploy and smoke:
  - deployed registry/router files with
    `scripts/deploy_unified.py --files backends_constants.py backends_registry/coding_pool.py backends_registry/free_web.py backends_registry/misc.py router_v3.py`;
  - upload result: `5 uploaded`, `0 failed`, `0 skipped`; restart health OK;
  - nginx backups:
    `/etc/nginx/conf.d/donglicao.conf.bak-20260609-040449` and
    `/etc/nginx/conf.d/chat.donglicao.com.conf.bak-20260609-040449`;
  - after `nginx -t` and reload, VPS and local public exits both returned
    HTTP `404` for `POST /telegram/webhook` on `api.donglicao.com` and
    `chat.donglicao.com`;
  - public `/health` returned HTTP `200`;
  - authenticated public `model=code` chat returned HTTP `200`.
- Residual risk:
  - `api.donglicao.com` live nginx currently targets `/opt/ai-router` on
    local port `8769`, while New API/One API processes remain on the VPS.
    The tracked online-distribution docs and sanitized nginx snapshot now
    record this observed topology.
  - this checkout has no `gitee` remote, so the closeout can push only to
    GitHub `origin`.

## 2026-06-09 Telegram retirement closeout

**Goal:** fully retire the Telegram bot/operator surface while preserving
LiMa Server, Agent Task / Agent Worker, GitHub/Gitee webhook ingestion,
Device Gateway, and public coding API productivity.

- Implementation:
  - removed `/telegram` router registration and lifespan startup wiring;
  - added `channel_retirement.py` so health explicitly reports
    `modules.telegram=false` and legacy bot webhook cleanup is centralized;
  - replaced Telegram push hooks in GitHub/Gitee webhooks, Agent Task review,
    Device Gateway task phases, budgets, health/token alerts, eval notify, and
    deploy helpers with internal activity records or structured logs;
  - removed Telegram runtime modules, route modules, tests, deploy/smoke
    scripts, GitHub Actions Telegram curl notifications, and active env
    examples;
  - updated active project rules and docs so future work validates
    `/telegram/webhook` 404 instead of real Telegram messages.
- Local verification:
  - focused Telegram-retirement pytest:
    `112 passed, 1 warning`;
  - JSON/retirement supplement:
    `tests/test_json_body_contract.py tests/test_channel_retirement.py` ->
    `9 passed, 1 warning`;
  - `python -m py_compile` on touched runtime files: clean;
  - focused `ruff check` on touched runtime/tests: clean;
  - focused `pyright`: `0 errors`, `7 warnings` for local dependency
    resolution (`fastapi`/`httpx`) only;
  - `git diff --check`: clean;
  - local TestClient smoke: `/health=200`, `/telegram/webhook=404`,
    `loaded_modules.telegram=False`.
- Broad test signal:
  - CI-style `tests/` run with the documented ignores completed:
    `2046 passed, 10 skipped, 8 failed in 287.60s`;
  - failures are outside the Telegram slice:
    backend registry drift, full ruff gate GBK decode, `health_tracker`
    state assertion drift, and AutoIndexer mtime detection flake.
- VPS deploy and smoke:
  - backup:
    `/opt/lima-router/backups/telegram-retirement-20260609_031429/runtime-before.tgz`;
  - deployed 23 runtime files with `scripts/deploy_unified.py --files`;
  - removed backed-up remote Telegram-only files and Telegram pycache;
  - service restart is active;
  - VPS-local `/health` returned `modules.telegram=false`;
  - public `/health` returned HTTP `200`;
  - public `POST /telegram/webhook` returned HTTP `404`;
  - authenticated public `model=code` chat returned HTTP `200`;
  - remote deleted-file check returned `0`.
- Residual risk:
  - Cloudflare Worker source `deploy/lima_security_gateway.js` is updated
    locally, but public `/telegram/webhook=404` already proves the active
    public path is closed through the current edge/origin chain;
  - full-suite residual failures should be closed in a separate backend
    registry / CI hygiene slice, not mixed into Telegram retirement.

## 2026-06-09 LiMa Code CLI retirement closeout

**Goal:** retire the tracked LiMa Code / `deepcode-cli` CLI integration from
the main LiMa repository while preserving the generic server-side Agent Task /
Agent Worker path.

- Implementation:
  - removed the `deepcode-cli` submodule stanza from `.gitmodules` and removed
    the gitlink from the main repository index;
  - removed tracked `.lima-code` examples, local `start_lima*` launchers,
    LiMa Code-only stress/verification scripts, and active LiMa Code
    management/old implementation plan docs;
  - changed active server/operator text from LiMa Code-specific wording to
    generic Agent Worker / developer-tool wording;
  - retired `model="lima-code"` as a first-class route alias while preserving
    `model="code"` as the coding route;
  - changed new learning/outcome evidence writes to `agent_worker` while
    keeping `limacode_worker` accepted for historical database compatibility.
- Local verification:
  - focused retirement pytest: `116 passed, 1 warning`;
  - `python -m py_compile` on retained touched scripts: clean;
  - focused `ruff check` on touched files: clean;
  - active tracked `ruff check` excluding archived scripts: clean;
  - focused `pyright` on touched files: `0 errors, 6 warnings` for unresolved
    FastAPI imports in the local pyright environment;
  - `git diff --check` and `git diff --cached --check`: clean;
  - `gitleaks` is not installed locally; manual staged added-line credential
    scan returned no matches.
- VPS deploy and smoke:
  - backup:
    `/opt/lima-router/backups/lima-code-retirement-20260609_020314/runtime-before.tgz`;
  - deployed 11 runtime files with `scripts/deploy_unified.py`; upload count
    `11`, restart health OK;
  - public Python urllib smoke returned `/health=200`;
  - authenticated public `model="code"` chat returned HTTP `200` and marker
    `agent-worker-retirement-ok`;
  - authenticated `/agent/worker/preflight` returned HTTP `200`, `ready=true`,
    `contract_version=agent-task-v1+prompt-contract-v0.1`.
- Residual risk:
  - full `pyright` remains blocked by unrelated, already-staged admin redesign
    work in `routes/admin_api_extra.py` (three type errors);
  - unrestricted `ruff check .` is blocked by unrelated local scratch scripts
    with Paramiko `AutoAddPolicy`; active tracked non-archive ruff is clean;
  - full `pytest -q` was attempted and timed out after about 350 seconds with
    many pre-existing failures/errors and a Windows temp cleanup `WinError 5`;
    the retirement-focused target suite passed.
  - GitHub push completed on `origin/feat/kilo-provider-probe`; Gitee mirror
    push was not available because this checkout has no `gitee` remote and
    `origin` has only a GitHub push URL.


## 历史归档

- [2026-05 执行进展](docs/archive/progress-2026-05.md)
- 更早的历史记录可在 Git 历史中检索
