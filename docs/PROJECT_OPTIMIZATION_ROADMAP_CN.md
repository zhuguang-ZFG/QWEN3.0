# LiMa 项目优化路线图

> 更新时间: 2026-06-10
> 范围: 战略转型后从个人编码助手后端到 AI 智能设备云服务的全项目文档和实施路线图。

## 当前定位

LiMa 现在是一个多后端 AI 路由服务器和设备云端控制平面。当前的优先级不再是添加更多通用聊天功能，而是让 AI 绘图/写字机工作流变得可靠、可观测和安全，同时保持现有的 OpenAI/Anthropic 兼容 API 可用。

最新设备路由切片已关闭：

- `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE.md` 定义了绘图/写字模型角色、准入门、切换规则、设备感知输入、安全、可观测性和发布验证。
- `device_gateway/model_routing.py` 将设备任务分类为 `device_control`、`device_write`、`device_draw`、`device_vector` 和 `device_unknown`。
- `device_gateway/tasks.py` 将 `route_policy` 元数据附加到生成的 `motion_task` 负载中。
- `esp32S_XYZ` 提交 `a8d98e3` 在 Edge-B 和 Edge-C `motion_task` 模式和示例中接受 `route_policy`。
- 主仓库提交 `423bf3e` 将产品子模块指针推进到该模式兼容版本。

该切片未执行 VPS 重启或物理固件刷新，因为运行时行为仅限元数据/模式/文档。

## 运营原则

1. 设备安全优于模型聪明。
2. 提供商准入基于证据，而非可用性。
3. 确定性路由是控制、纯书写和已知资产的首选。
4. AI 模型可以规划、生成、解释和恢复，但经过验证的几何形状是运动的唯一权威。
5. 密钥保留在 LiMa 或经批准的服务器端密钥存储中，绝不放在固件、客户端应用、产品示例或浏览器可见配置中。
6. 跨仓库更改先行产品仓库，然后更新 LiMa 文档/测试/子模块指针。
7. 完整部署声明需要 VPS 冒烟证据；硬件发布声明还需要假设备和物理设备证据。

## 优化流

| 流 | 负责区域 | 当前状态 | 下一步成果 |
|---|---|---|---|
| 设备任务路由 | `device_gateway/` | 路由角色和 `route_policy` 已存在 | 假 U8 消费并报告路由策略 |
| 绘图/写字模型策略 | `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE.md` | 云端策略已文档化 | 首次有日期的图像/矢量准入报告 |
| 产品固件/模式 | `esp32S_XYZ/` | Edge-B/C 模式接受路由策略 | U8 适配器验证并记录路由策略 |
| 运动安全 | `path_validator.py`、产品 U1/U8 | 验证器存在，物理门仍分离 | 模拟器和假设备发布门成为强制性 |
| 通用 LLM 路由 | `routing_engine.py`、`router_v3.py`、`routing_selector.py` | 现有聊天/编码路由引擎保持活跃 | 设备角色停止依赖通用聊天池行为 |
| 可观测性 | `observability/`、设备账本/制品 | 指标和设备制品存在 | 路由决策到终端运动追踪可查询 |
| CI 和发布 | `scripts/run_pre_commit_check.py`、部署脚本 | 主要聚焦门通过；全部门因基线而异 | 分离设备、服务器和产品发布门 |
| 文档 | `docs/README.md`、`STATUS.md`、`progress.md` | 最新设备路由已记录 | 文档索引成为所有活跃工作的起点 |

## 阶段 1：稳定设备路由契约

目标：每个设备任务都能解释为什么选择了该路由以及设备允许做什么。

步骤：

1. 在所有 `motion_task` 路径上保留 `route_policy`，包括策略阻止和验证失败的路径。
2. 添加假 U8 断言，确保路由角色被接收、记录并在终端 `motion_event` 证据中呈现。
3. 添加 `device_control`、`device_write`、`device_draw` 和 `device_vector` 的产品端模式示例，而不仅仅是 `run_path`。
4. 在设备制品中记录路由角色、能力、模型角色和验证结果。
5. 在 U1 运动执行之前拒绝未知或固件不兼容的路由策略。

所需验证：

```powershell
python -m pytest tests/test_device_gateway_model_routing.py tests/test_device_gateway_protocol.py -q
cd D:\QWEN3.0\esp32S_XYZ
python tools\validate_schemas.py
python -m unittest tests.ci.test_validate_schemas -v
python -m unittest tools.fake_lima_u8.tests.test_app -v
```

晋升规则：仅从本阶段不更改 U1 运动固件。U1 更改需等待假 U8 和模拟器证据显示契约稳定。

## 阶段 2：按角色准入 AI 绘图/写字模型

目标：将设备模型角色从通用聊天/编码路由池中分离出来。

步骤：

1. 在 `docs/model_admission/` 下为绘图/写字夹具创建有日期的准入报告。
2. 至少评估以下角色类别：意图解析器、文本规划器、提示增强器、图像生成器、矢量器、视觉分析器和恢复解释器。
3. 记录后端 ID、提供商、模型 ID、夹具计数、通过计数、延迟、故障模式、准入决策和回滚规则。
4. 保持直接 LLM 到 SVG 为实验性，直到几何夹具证明有界路径和稳定点计数。
5. 为设备角色添加路由偏好，而不将未验证的提供商移入一级通用聊天/编码池。

所需验证：

```powershell
python -m pytest tests/test_device_gateway_model_routing.py -q
python -m pytest tests/test_routing_engine.py -q --tb=short
python scripts/run_pre_commit_check.py --full
```

晋升规则：后端只有在从 `docs/FREE_MODEL_ROUTING_STATUS.md` 或特定角色的准入报告链接其有日期的证据后才能进入热绘图/写字路由。

## 阶段 3：使设备配置文件成为一级路由输入

目标：路由决策在模型选择之前考虑固件、硬件、工作空间和点限制。

步骤：

1. 扩展设备影子/配置文件记录，增加 `fw_rev`、`u1_fw_rev`、`hw_rev`、`workspace_mm`、`capabilities`、`profile_rev` 和 `limits.max_points`。
2. 使缺失的配置文件数据保守：较低的点计数、较小的比例、偏好预设路由、降级或审批门控生成绘图。
3. 在分发到硬件之前添加兼容性检查。
4. 仅在安全/配置文件兼容性检查通过后添加每个设备的粘性路由记忆。
5. 在任务制品和恢复解释中记录简化决策。

所需验证：

```powershell
python -m pytest tests/test_device_gateway_routes.py tests/test_device_gateway_store.py -q
python -m pytest tests/test_p1_4_device_stability_gate.py -q
```

晋升规则：允许配置文件感知的简化；不允许静默几何修复。任务必须记录简化了什么。

## 阶段 4：加固通用 LLM 路由同时保持设备工作隔离

目标：保留公共 OpenAI/Anthropic 兼容 API，而不让通用聊天回归控制设备安全。

步骤：

1. 保持 `routing_engine.route()` 作为权威聊天/编码路由入口。
2. 仅将 `smart_router.py` 和 `router_http.py` 保留为兼容/遗留表面；新生产调用者使用当前路由引擎和 `http_caller`。
3. 按表面拆分路由测试：聊天/编码、设备、运维、产品集成。
4. 保持提供商健康/冷却/预算故障在日志和指标中可见。
5. 避免将本地 Windows 代理后端提升到 VPS 优先路由，除非 VPS 进程能通过文档化的拓扑访问它们。

所需验证：

```powershell
python -m pytest tests/test_routing_engine.py tests/test_http_caller.py -q
python scripts/run_ruff_check.py
```

晋升规则：任何提供商池更改都需要聚焦路由顺序测试和实际部署拓扑的新鲜冒烟证据。

## 阶段 5：构建 AI 到运动的发布门

目标：发布声明基于从用户请求到终端运动事件的端到端追踪。

步骤：

1. 为 `/device/v1/health`、假 U8 WebSocket、控制、书写、生成绘图、验证失败、断开恢复和终端事件回放添加发布检查清单。
2. 在物理设备验证之前强制假 U8/U1 测试。
3. 添加物理设备证据模板，记录板版本、固件版本、工作空间、材料、提示、生成制品哈希、路径点计数、运行时间估计、终端结果和操作员笔记。
4. 在 `STATUS.md`、`progress.md` 和 `docs/LIMA_MEMORY.md` 中存储发布证据；长报告放在 `docs/release_evidence/` 下。
5. 将部署证据与硬件证据分开。健康的 VPS 不能证明安全的运动。

所需验证：

```powershell
python scripts/run_pre_commit_check.py --full
python scripts/deploy_unified.py
curl -sf https://chat.donglicao.com/health
curl -sf https://chat.donglicao.com/device/v1/health
```

晋升规则：公共生产就绪需要服务器冒烟和任何影响运动的发布的硬件门证据。

## 文档系统

使用此源层次结构：

| 文档 | 角色 |
|---|---|
| `docs/README.md` | 入口点和文档地图 |
| `STATUS.md` | 当前项目状态和最新关闭 |
| `progress.md` | 按时间顺序的执行证据 |
| `docs/LIMA_MEMORY.md` | 持久跨会话记忆 |
| `docs/REQUEST_PIPELINE_AUTHORITY.md` | 生产路由所有权 |
| `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE.md` | 设备模型路由策略 |
| `docs/ESP32S_XYZ_MANAGEMENT.md` | 产品子模块边界 |
| `docs/PROJECT_OPTIMIZATION_ROADMAP.md` | 活跃全项目路线图 |

文档规则：

- 当新的活跃文档成为入口点时更新 `docs/README.md`。
- 当切片关闭或运维状态更改时更新 `STATUS.md`。
- 在提交前更新 `progress.md` 以包含验证证据。
- 为未来代理不应重新发现的跨会话事实更新 `docs/LIMA_MEMORY.md`。
- 在事实合并到持久文档后归档或删除过时的执行报告。

## 立即下一步编码任务

1. 产品假 U8 消费 `route_policy`。
   预期文件：`esp32S_XYZ/tools/fake_lima_u8/app.py`、`esp32S_XYZ/tools/fake_lima_u8/tests/test_app.py`、模式示例。
2. LiMa 设备制品记录路由证据。
   预期文件：`device_gateway/tasks.py`、`device_artifacts/`、`tests/test_device_gateway_model_routing.py`。
3. 设备模型准入报告脚手架。
   预期文件：`docs/model_admission/YYYY-MM-DD-device-drawing-writing.md` 和聚焦评估脚本或可重复命令列表。
4. 设备配置文件路由输入。
   预期文件：`device_gateway/profiles.py`、`device_gateway/tasks.py`、匹配的路由和存储测试。
5. AI 到运动发布证据模板。
   预期文件：`docs/release_evidence/TEMPLATE_AI_TO_MOTION_RELEASE.md`。

## 需关注的风险

| 风险 | 为什么重要 | 控制措施 |
|---|---|---|
| 通用聊天池驱动运动任务 | 聊天质量不是运动安全 | 设备路由角色和准入门 |
| 来自 LLM 的直接 SVG 绕过验证器 | 无效几何可能损坏输出或硬件 | 验证器和模拟器保持权威 |
| 固件消费未知路由策略 | U8/U1 行为变为非确定性 | 模式兼容性和假 U8 断言 |
| 文档与代码不一致 | 代理做出错误的路由/部署决策 | 代码优先；文档在同一切片中更新 |
| 运行时更改后跳过 VPS 冒烟 | 仅本地成功隐藏了生产故障 | 部署声明需要真实的 `chat.donglicao.com` 冒烟 |
| 完整测试基线漂移 | 代理将无关故障误读为切片故障 | 聚焦门加上记录的完整门基线 |

## 关闭标准

项目切片仅在满足以下条件时完成：

1. 相关聚焦测试通过。
2. 格式化/lint/diff 检查通过或记录了已知无关阻塞项。
3. 当产品契约更改时产品仓库检查通过。
4. 当运行时部署更改时存在 VPS 冒烟证据。
5. 当物理运动行为更改时存在硬件证据。
6. `STATUS.md`、`progress.md` 和 `docs/LIMA_MEMORY.md` 包含持久结果。
7. 仅暂存、提交和推送相关文件。