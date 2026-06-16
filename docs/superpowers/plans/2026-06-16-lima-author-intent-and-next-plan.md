# LiMa 作者意图理解与下一阶段项目计划

> 日期：2026-06-16
> 性质：代码理解 + 项目计划
> 依据：当前仓库代码、`STATUS.md`、`docs/README.md`、`docs/ARCHITECTURE.md`、`docs/REQUEST_PIPELINE_AUTHORITY_CN.md`、`docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md`、`docs/CODEBASE_SUBSYSTEM_TIER_CN.md`

## 1. 结论摘要

LiMa 的作者意图不是继续堆叠一个“全能聊天后端”，而是把既有多后端 AI 路由能力收束为 **AI 绘图/写字设备的统一云端控制平面**。现有 OpenAI 兼容聊天接口仍保留，但它的战略角色已经变成基础能力和兼容入口；真正的产品主线是让 ESP32 绘图机/写字机的任务从自然语言进入，经过模型角色路由、安全策略、设备 profile、路径验证、模拟评估、任务制品、终端事件和发布证据，形成可解释、可回放、可运维的闭环。

当前阶段最重要的工程方向是：**用更少的代码承载更硬的设备契约**。过去几轮已经完成大量退役、瘦身和 `route_policy` 硬契约建设；下一阶段不应再扩大通用聊天功能，而应把设备任务发布门、真实/假设备证据、模型准入报告和运行时可观测性串成一条稳定交付线。

## 2. 代码证据

### 2.1 入口层意图

- `server.py` 保持薄启动器：创建 FastAPI、安装 body limit、初始化运行态，再把路由注册交给 `routes.route_registry.register_all_routes()`。
- `routes/route_registry.py` 同时挂载聊天、公共 demo、设备网关、小智兼容、运维指标、fleet、device_memory、device_support、device_ota 等路由；这说明系统边界已经从“聊天 API”扩展为“设备云端服务 + 兼容 API”。
- `routes/route_registry.py` 通过 `mark_retired_modules()` 明确标记退役通道，说明作者正在主动切断旧集成，而不是保留所有历史入口。

### 2.2 AI 路由层意图

- `routing_engine.py` 的公开 API 是 `route()` / `pick_backend()` / `respond()`，核心流程是 classify、scenario、retrieval、coding context、health、selector、skills、execute、post_route。
- `docs/REQUEST_PIPELINE_AUTHORITY_CN.md` 明确规定生产聊天请求的权威路径是显式分层管道，而不是 `context_pipeline.factory` 这类实验室工厂。
- 这说明通用 AI 路由仍是基础设施，但作者已经把“权威入口”和“实验模块”拆开，避免实验代码重新污染热路径。

### 2.3 设备任务层意图

- `routes/device_gateway.py` 暴露 `/device/v1/health`、`/events`、`/tasks`、`/ws`、任务查询、设备历史等入口，并记录 `device_task_created` 能力证据。
- `device_gateway/task_creation.py` 在任务创建时依次处理 profile、`route_policy`、策略校验、固件兼容、参数校验、策略引擎、workflow、模拟器、制品记录和路由证据。
- `device_gateway/model_routing.py` 把设备任务拆成 `device_control`、`device_write`、`device_draw`、`device_vector`、`device_unknown`，并为每类角色绑定准入后的 backend，例如 `deterministic`、`dashscope_wanx`、`opencv_contour`。
- 这说明作者不希望 LLM 直接控制硬件；AI 只能在角色和准入证据限定内提供规划/生成能力，运动下发仍由确定性校验链路守门。

### 2.4 瘦身层意图

- `STATUS.md` 和 `docs/CODEBASE_SUBSYSTEM_TIER_CN.md` 记录了从个人编码助手后端向智能设备云服务的战略转型，并持续删除 Telegram、LiMa Code CLI、Anthropic `/v1/messages`、channel_gateway、冷实验模块等旧路径。
- `docs/CODEBASE_COLD_PRUNE_PRIORITY_CN.md` 把 Hot/Warm/Cold 分层作为后续删除和迁移依据，避免为了“少文件”误删热路径。
- 这说明瘦身不是单纯减行数，而是为设备主线释放认知空间、启动时间、测试门和部署风险预算。

## 3. 作者意图的可执行解释

| 主题 | 当前代码表达 | 推断出的作者意图 | 计划含义 |
|---|---|---|---|
| 产品定位 | `STATUS.md` 定位为 AI 智能设备统一云端服务 | 从聊天代理转向设备云平台 | 所有新任务优先服务设备闭环 |
| 路由权威 | `routing_engine.route()` 是聊天/编码权威入口 | 保留兼容 API，但收紧入口所有权 | 不新增旁路路由和隐式 pipeline |
| 设备安全 | `route_policy`、profile、policy engine、simulator 串联 | AI 输出不能绕过运动安全 | 发布门必须覆盖策略、路径、终端事件 |
| 模型准入 | 设备角色映射到准入 backend | 模型能力按角色使用，不按“最聪明”使用 | 后端升级必须有角色准入报告 |
| 瘦身治理 | Hot/Warm/Cold 分层和退役记录 | 减少历史耦合，保护热路径 | 每批删除必须有 fan-in 与回归证据 |
| 运维证据 | device health、Prometheus、capability evidence、release template | 发布声明必须可验证 | 本地测试不足以证明生产和硬件安全 |

## 4. 下一阶段目标

### G1：把 AI 到运动发布门做成默认交付路径

目标：任何会影响设备运动行为的变更，都必须能从用户请求追踪到 `motion_event` 或明确的阻止证据。

交付物：

- 完整使用 `docs/release_evidence/TEMPLATE_AI_TO_MOTION_RELEASE.md` 的首个真实切片报告。
- 假 U8/U1 到云端 `/device/v1/tasks`、WS 下发、`motion_event` 回收的闭环证据。
- `STATUS.md`、`progress.md`、`docs/LIMA_MEMORY_CN.md` 中记录同一批证据，避免只在临时报告中存在。

验收标准：

- `python -m pytest tests/test_device_gateway_model_routing.py tests/test_device_gateway_protocol.py -q` 通过。
- 假设备链路测试包含 `route_policy` 消费和终端事件回收。
- 任何 blocked/failed 任务都有 `route_policy` 或 `policy`/`error` 证据。
- 若部署生产，必须有 `https://chat.donglicao.com/health` 和 `/device/v1/health` 的真实 smoke 记录。

### G2：把设备模型准入从文档模板推进到可重复评估

目标：设备绘图/写字相关 backend 的准入依据可复跑、可比较、可回滚。

交付物：

- 在 `docs/model_admission/` 新增下一份有日期的准入报告。
- 扩展或固化 `scripts/eval_device_model_role.py` 的离线/真实 API 评估输入输出。
- 把 `device_draw`、`device_vector`、`device_write`、`device_control` 的准入结果与 `DEVICE_ROLE_PREFERENCES` 对齐。

验收标准：

- 默认离线评估不依赖真实密钥并通过。
- 真实 API fixture 只在显式环境变量和密钥存在时运行。
- 准入报告必须记录 backend、模型、角色、通过/失败、失败模式、回滚策略。
- 任何新增一线设备 backend 都能指向对应报告。

### G3：继续瘦身，但只沿证据边界删除

目标：继续降低代码规模和维护面，同时保护 `routing_engine`、`device_gateway`、`session_memory`、`observability` 等热路径。

交付物：

- 更新 `docs/CODEBASE_SUBSYSTEM_TIER_CN.md` 的下一轮 Hot/Warm/Cold 审计。
- 对候选删除模块运行 `python scripts/codegraph_orphans.py --fanin` 并记录 lazy import 例外。
- 每批删除只处理一个主题：冷实验、退役脚本、测试残留、文档归档，不混入功能变更。

验收标准：

- 删除前后 focused pytest 明确覆盖受影响热路径。
- `ruff check .` 或 tracked ruff wrapper clean。
- `git diff --check` clean。
- 文档同步更新，且不出现未来日期、已完成但代码未删、代码已删但文档仍列为活跃的漂移。

### G4：降低启动和部署不确定性

目标：把当前 VPS 启动约 7 分钟的问题拆成可观测、可延迟、可并行的启动阶段。

交付物：

- 记录 lifespan 内每个启动任务耗时。
- 区分“健康检查必须完成”和“后台预热可稍后完成”的任务。
- 对 backend profile / retirement 历史分析 / probe loop 做异步预热或延迟加载方案。

验收标准：

- 本地或测试环境能输出启动阶段耗时日志。
- `/health` 的 ready/started/warming 状态语义明确。
- 不牺牲设备安全初始化；任务 store、ledger、notifier 必须在设备网关 ready 前完成。

## 5. 推荐执行顺序

1. **先做 G1 发布门闭环**：这是最贴近产品主线的证据链，能验证 `route_policy`、设备网关、假设备、制品和文档模板是否真的串起来。
2. **并行准备 G2 模型准入复跑**：不要先引入新模型，先让现有 `dashscope_wanx` / `opencv_contour` / `deterministic` 的报告可复现。
3. **随后做 G3 小批瘦身**：只处理已经被 CodeGraph 和文本搜索证实为冷区的内容，不和设备行为变更混在一个提交里。
4. **最后做 G4 启动优化**：启动优化容易误伤生命周期依赖，应在发布门稳定后进行。

## 6. 风险与控制

| 风险 | 表现 | 控制措施 |
|---|---|---|
| 文档超前代码 | 计划写成已完成，但源码/测试未兑现 | 每条完成声明必须带命令、文件和结果 |
| 误删 Warm lazy 模块 | CodeGraph 显示 0 fan-in，但函数内 lazy import 仍使用 | 删除前同时用文本搜索、测试和运行入口确认 |
| AI 绕过确定性运动门 | draw/write 任务直接信任 LLM 输出 | 保持 path_validator、policy_engine、simulator、route_policy 必经 |
| 真实 API fixture 影响默认 CI | 无密钥环境失败或变慢 | live 测试必须显式 gate，默认离线通过 |
| VPS smoke 被本地成功替代 | 本地测试通过但生产不可用 | 部署声明必须包含真实域名 smoke |

## 7. 验证矩阵

| 变更类型 | 最小验证 | 扩展验证 |
|---|---|---|
| 设备任务/route_policy | `tests/test_device_gateway_model_routing.py`、`tests/test_device_gateway_protocol.py` | 假 U8/U1 闭环 + `/device/v1/health` smoke |
| 模型准入 | `tests/test_eval_device_model_role.py`、离线 fixture | live fixture，显式密钥 gate |
| 通用路由 | `tests/test_routing_engine.py`、`tests/test_http_caller.py` | 认证公开 `model=code` smoke |
| 瘦身删除 | `scripts/codegraph_orphans.py --fanin`、focused pytest、ruff | full pre-commit gate |
| 部署/发布 | `scripts/run_pre_commit_check.py --full` | `scripts/deploy_unified.py` + 真实域名 smoke |

## 8. ADR

### Decision

下一阶段以“AI 到运动发布门”为主线，模型准入和代码瘦身作为支撑线，暂不扩大通用聊天功能面。

### Drivers

- 代码和文档均显示项目已完成战略转型，设备云端是当前主线。
- `route_policy`、profile、policy engine、simulation、evidence 已具备闭环雏形，需要以发布门固化。
- 历史聊天/编码助手遗留已经多轮退役，继续扩通用能力会增加认知和测试负担。

### Alternatives Considered

- **继续优化通用聊天/编码路由**：能改善兼容 API，但不直接推进设备产品闭环，且容易重新扩大旧主线。
- **先做更激进瘦身**：能减代码量，但若缺少发布门，可能把风险转移到设备安全链路。
- **先做启动性能优化**：有运维收益，但生命周期依赖未完全梳理时容易引入隐性故障。

### Why Chosen

发布门能同时验证产品价值、安全边界、模型准入、设备协议、可观测性和文档纪律，是最能表达作者当前意图的下一阶段核心工作。

### Consequences

- 后续任务应优先围绕设备闭环组织，而不是按模块孤立优化。
- 文档、测试、VPS smoke 和设备证据必须成为同一批交付的一部分。
- 代码瘦身继续进行，但必须服从 Hot/Warm/Cold 证据边界。

### Follow-ups

- 产出第一份真实 AI→Motion 发布证据报告。
- 复跑并更新设备模型准入报告。
- 对启动生命周期做耗时分解。
- 继续小批次冷区删除并记录验证证据。

## 9. 执行建议

适合使用 `$ultragoal` 作为 durable ledger owner，跟踪 G1-G4 的完成证据；若要并行推进，可使用 `$team` 分成四条 lane：设备发布门、模型准入、瘦身审计、启动观测。当前 Codex App 外部 tmux OMX runtime 不直接可用时，可以按本文档逐切片执行，并把每个切片的证据回写到 `progress.md` / `findings.md` / `STATUS.md`。
