# AI 绘图/写字机模型路由指南

> 更新时间: 2026-06-16
> 范围: LiMa 云端模型管理、路由策略和 `esp32S_XYZ` AI 绘图/写字机的准入门。

## 目的

LiMa 是 `esp32S_XYZ` 的云端控制平面。产品仓库拥有固件、设备模式、硬件证据、假设备和发布流程。LiMa 拥有模型路由、提供商托管、任务规划、安全策略、记忆、可观测性以及公共/私有端点。

本文档定义了 LiMa 在服务 AI 绘图和写字设备时应如何选择、切换、准入和退役 AI 模型。它有意比通用路由器文档更具体，因为错误的模型选择可能产生不安全的运动、浪费材料、用户可见的故障或设备损坏。

## 真实来源

联合使用以下文件：

| 关注点 | 来源 |
|---|---|
| 生产请求管道 | `docs/REQUEST_PIPELINE_AUTHORITY_CN.md` |
| 路由引擎设计 | `docs/archive/ROUTING_ENGINE_DESIGN.md` |
| 后端/模型目录 | `docs/archive/MODEL_CATALOG.md` |
| 免费模型证据和策略 | `docs/archive/FREE_MODEL_ROUTING_STATUS_CN.md` |
| 产品子模块边界 | `docs/ESP32S_XYZ_MANAGEMENT_CN.md` |
| 设备协议 | `docs/device_protocol_alignment.md` |
| 产品固件和假设备 | `esp32S_XYZ/` |
| 实时路由池 | `router_v3.py` |
| 实时路由排名 | `routing_selector.py` |
| 设备任务投影 | `device_gateway/tasks.py` |
| 设备意图解析 | `device_gateway/intent.py` |
| 路径生成/验证 | `device_gateway/path_pipeline.py`、`device_gateway/path_validator.py` |
| 模型准入报告 | `docs/model_admission/2026-06-16-device-drawing-writing.md` |
| 发布证据模板 | `docs/release_evidence/TEMPLATE_AI_TO_MOTION_RELEASE.md` |

当文档和代码不一致时，生产行为遵循代码。在更改路由池、提供商准入、设备任务契约或绘图/写字任务的模型要求时更新本文档。

## 实现状态

截至 2026-06-16：

| 区域 | 状态 | 证据 |
|---|---|---|
| 云端指南 | 完成 | 本文档定义了 AI 绘图/写字机的路由角色、模型准入、切换策略、安全、可观测性和验证。 |
| 设备路由角色 | 完成 | `device_gateway/model_routing.py` 分类 `device_control`、`device_write`、`device_draw`、`device_vector` 和 `device_unknown`。 |
| 任务元数据 | 完成 | `device_gateway/tasks.py` 将 `route_policy` 附加到成功、验证失败和策略阻止的 `motion_task` 负载。 |
| 产品模式兼容性 | 完成 | `esp32S_XYZ` 已推进到 `a4cab61`：Edge-C `route_policy` required 化，Edge-B/Edge-C schema 接受可选 `backend` 字段。 |
| LiMa 子模块指针 | 完成 | 主仓库分支 `design/route-policy-backend-field` 将 `esp32S_XYZ` 推进到 route_policy 硬契约和 backend 字段兼容版本。 |
| 固件消费 | 下一步 | 假 U8 应消费、记录和回显路由策略证据，然后才直接更改 U1 运动固件行为。 |

## 所有权边界

LiMa 云端拥有：

- 意图理解和用户提示规范化；
- AI 模型选择和后端故障转移；
- 图像、矢量、文本和安全模型准入；
- 任务规划到 `write_text`、`draw_generated`、`draw_asset`、`run_path`、`home`、`pause`、`resume`、`stop`、`self_check`；
- 内容安全、几何安全、策略门控、模拟、审批和恢复；
- 任务账本、预览制品、操作员诊断、指标和反馈。

`esp32S_XYZ` 拥有：

- U8 AI MCU 固件行为和 LiMa 协议适配器；
- U1 电机 MCU 确定性运动执行；
- Edge-A/B/C/D 模式和产品管理服务；
- GPIO、归零、限位、OTA、配置、假 U8/U1 工具和物理硬件证据；
- 产品发布制品和子模块历史。

任何影响两个仓库的更改必须按以下顺序落地：

1. 更新 `esp32S_XYZ` 模式/固件/假设备行为。
2. 提交并推送产品仓库。
3. 更新 LiMa 代码/文档/测试。
4. 推进 LiMa 子模块指针。
5. 在 `STATUS.md`、`progress.md` 和 `docs/LIMA_MEMORY_CN.md` 中记录验证证据。

## 产品任务分类

LiMa 应在选择模型之前将绘图/写字请求分类为设备任务族。

| 族 | 示例 | 模型需求 | 默认路径 |
|---|---|---|---|
| 控制 | stop、pause、resume、home、设备信息 | 无需 LLM | 确定性解析器 -> 设备网关 |
| 纯书写 | 写 "Happy Birthday"、复制短文本 | 无需图像模型；可选文本润色 | `write_text` -> 笔画字体/路径 |
| 创意书写 | 诗歌、祝福语、儿童友好句子 | 具有 JSON 安全输出的文本模型 | 文本规划器 -> `write_text` |
| 简单绘图 | 星形、心形、房屋、猫轮廓 | 优先素材库，其次图像/矢量 | 预设 SVG -> `run_path` |
| 生成绘图 | 画一只简单线稿风格的猫 | 图像模型 + 矢量器或经过验证的 SVG 提供商 | 图像 -> 骨架/矢量 -> `run_path` |
| 上传图像临摹 | 描摹这张照片 | 视觉/图像预处理 + 矢量器 | 图像规范化 -> 矢量 -> `run_path` |
| 练习/教育 | 写汉字、笔画练习 | 文本/布局模型加模板规则 | 模板素材 -> `run_path` |
| 模糊命令 | "让它更好看"、"画点可爱的" | 仅低风险规划器 | 门控 LLM 规划器 -> 需要时确认 |
| 不安全/无界 | 超大图片、成人/暴力提示、整页涂鸦 | 拒绝或需要审批 | 分发前策略阻止 |

路由从任务族开始，而不是从提供商名称开始。后端只有通过了该族的证据门才具有资格。

## 模型角色类

使用特定角色的模型准入，而非一个全局"最佳模型"排名。

| 角色 | 必需属性 | 非目标 |
|---|---|---|
| 意图解析器 | 确定性 JSON、低延迟、保守拒绝 | 创意文本生成 |
| 文本规划器 | 中英文质量、可控长度、JSON 模式规范 | 运动几何 |
| 提示增强器 | 产生短图像提示、儿童安全、风格感知 | 最终任务权威 |
| 图像生成器 | 线稿质量、快速小输出、低伪影率 | 直接运动输出 |
| 视觉分析器 | 识别可绘制结构和安全问题 | 艺术发明 |
| 矢量器 | 确定性几何、有界点计数、预览制品 | 语义推理 |
| 运动验证器 | 无 AI 依赖；强制边界/进给/点限制 | 静默"修复"不安全输出 |
| 恢复解释器 | 从已知错误代码提供清晰的用户/操作员解释 | 盲目重试硬件 |

当前产品证据偏好 `qwen-image-2.0` 在 `512x512` 用于生成线稿，因为它在产品仓库中足够快并且矢量化良好。直接 LLM 到 SVG 应保持非主要路径，直到可重复的几何评估显示准确、有界、设备安全的路径。

## 路由决策矩阵

| 输入信号 | 主路由 | 回退 | 阻止条件 |
|---|---|---|---|
| 精确控制命令 | `device_gateway.intent` 确定性解析器 | 无 | 未知设备/会话 |
| 短纯文本 | 确定性 `write_text` 路径 | 仅在请求时使用文本模型格式化 | 文本对工作空间太长 |
| 模糊自然语言 | 确定性解析器优先；仅当 `LIMA_DEVICE_LLM_PLANNER=1` 时使用 LLM 规划器 | 要求澄清或书写字面文本 | 低置信度加上高风险能力 |
| 来自常见形状的绘图 | 本地/预设 SVG 素材 | 生成图像路由 | 素材超出工作空间/点限制 |
| 来自提示的绘图 | 准入的图像模型 -> 矢量器 -> 验证器 | 准入的回退图像模型；然后简单预设/文本回退 | 不安全提示、矢量化失败、路径太大 |
| 上传照片 | 视觉/预处理 -> 矢量器 -> 验证器 | 要求用户裁剪/简化 | 面部/隐私策略或太复杂 |
| 汉字练习 | 模板/笔画素材路由 | 文本规划器仅用于说明 | 缺少字体/模板覆盖 |
| 设备报告低能力 | 更简单的配置文件和更低的点/进给限制 | 排队直到兼容 | 缺少必需能力 |
| 后端降级/死亡 | `routing_selector.select()` 移除或降级 | 下一个准入的后端 | 该角色没有准入的后端 |
| 硬件高风险 | 模拟器 + 审批 | 降低比例/进给/点 | 策略拒绝或缺少审批 |

## 准入门

没有有日期的证据，新模型不得进入热绘图/写字路由。

### 门 A：提供商和密钥保管

- 提供商密钥保留在 LiMa 或经批准的 VPS 密钥存储中。
- 不将提供商令牌复制到 `esp32S_XYZ`、固件、移动客户端或浏览器可见配置中。
- 后端配置名称必须在 `backends_registry.py` 或经批准的准入覆盖中稳定且可搜索。

### 门 B：功能适配

在提升之前运行特定角色的夹具：

| 角色 | 最低夹具 |
|---|---|
| 意图解析器 | 20 条命令：控制、书写、绘图、模糊、拒绝 |
| 文本规划器 | 20 个 JSON 输出：有效模式、长度有界、无隐藏散文 |
| 图像生成器 | 20 个提示：线稿、儿童安全、简单物体、无文本伪影 |
| 视觉分析器 | 10 张图像：返回有界追踪策略并拒绝不合适的输入 |
| SVG/矢量模型 | 20 个输出：有效 SVG 路径、有界工作空间、<= 配置点 |
| 恢复解释器 | 20 个错误代码：正确的用户面向原因和下一步操作 |

### 门 C：几何安全

生成的制品必须通过：

- 工作空间边界；
- 最大点计数；
- 最大进给率；
- 最大运行时间估计；
- 抬笔/落笔编码兼容性；
- 预览制品创建；
- 模拟器风险评分低于审批阈值，或显式审批流程。

### 门 D：路由行为

在第一梯队提升之前，记录：

- 后端 ID；
- 提供商；
- 模型 ID；
- 用于评估的命令；
- 夹具计数；
- 通过计数；
- 平均延迟；
- p95 延迟（当可用时）；
- 故障模式；
- 准入决策；
- 回滚规则。

证据应从 `docs/model_admission/` 下的有日期准入报告链接；历史免费模型策略见 `docs/archive/FREE_MODEL_ROUTING_STATUS_CN.md`。路由池编辑不得与无关重构混合。

## 切换策略

模型切换在提高可靠性或安全性时允许，但必须是可解释的。

### 用户面向模型别名

保持公共别名稳定。不要将原始后端 ID 暴露给产品用户。

| 别名 | 含义 | 预期后端类 |
|---|---|---|
| `lima-device` | 默认平衡设备大脑 | 确定性优先，准入快速模型其次 |
| `lima-device-fast` | 速度优先于创意 | 预设/确定性/轻文本 |
| `lima-device-creative` | 更好的绘图或文本质量 | 更高延迟的图像/文本模型 |
| `lima-device-safe` | 保守课堂/儿童模式 | 严格安全、低复杂性、风险确认 |
| `lima-device-local` | 配置时使用本地代理/回退 | 仅本地/假/离线能力后端 |

别名应映射到路由偏好，而不是永久直接映射到一个提供商。

### 自动切换原因

路由器可以在以下情况切换后端：

- 当前后端死亡、降级、隔离、冷却、超出预算或已退役；
- 请求需要当前后端缺乏的能力；
- 粘性后端对当前任务族不安全；
- 任务复杂性需要图像/视觉/矢量能力；
- 设备配置文件需要更低的点限制或更小的上下文；
- 准入证据将另一个后端排名更高用于该角色；
- 操作员已启用推出/回滚标志。

路由器不得因以下原因切换：

- 存在新提供商但没有准入证据；
- LLM 声称可以在没有验证器成功的情况下生成几何；
- Web 反向适配器一次有效而没有稳定性运行；
- 本地 Windows 代理可从 Windows 访问但不能从 VPS 进程访问；
- 付费回退比修复正确的免费路由更便宜，除非预算策略明确允许。

## 提示和输出契约

规划器模型必须仅返回机器可读的 JSON。设备网关不得将散文解析为权威。

意图规划器输出：

```json
{
  "capability": "draw_generated",
  "params": {
    "prompt": "simple black line drawing of a cat, centered, no text",
    "style": "line_art",
    "complexity": "low"
  },
  "risk": "low",
  "needs_approval": false,
  "reason": "safe simple drawing request"
}
```

文本规划器输出：

```json
{
  "capability": "write_text",
  "params": {
    "text": "生日快乐",
    "layout": "single_line",
    "max_chars": 12
  },
  "risk": "low",
  "needs_approval": false
}
```

图像提示输出：

```json
{
  "image_prompt": "simple black line art of a smiling cat, white background, centered, no shading, no text",
  "negative_prompt": "photo, color, dense texture, background, letters, watermark",
  "size": "512x512"
}
```

每个模型产生的对象在成为运动任务之前必须经过验证。无效 JSON、额外散文、缺少字段或不安全字段是路由失败，而非部分成功。

## 设备感知路由输入

路由选择最终应包括来自 `hello` 和影子状态的设备配置文件数据：

| 输入 | 用途 |
|---|---|
| `device_id` | 粘性路由、任务账本、每设备策略 |
| `fw_rev` / `u1_fw_rev` | 兼容性门 |
| `hw_rev` | 工作空间和 GPIO 风险假设 |
| `profile_id` / `profile_rev` | 进给、笔压、比例、最大点数 |
| `workspace_mm` | 路径边界和布局 |
| `capabilities` | 允许的任务族 |
| `limits.max_points` | 矢量器简化目标 |
| `supports_crc` | U8/U1 事务可靠性模式 |
| 在线/离线状态 | 排队、重试或拒绝决策 |
| 最后故障代码 | 恢复策略和后端降级 |

如果配置文件数据缺失，使用保守默认值并偏好书写/预设路由而非生成绘图。

## 安全和策略规则

硬阻止：

- 没有已知 `device_id` 则不进行运动；
- 当设备未绑定、已转移、已处置、维护锁定、更新中或固件不兼容时不进行物理分发；
- 生成路径不得超出工作空间；
- 路径不得超过点/进给/运行时间限制；
- 不允许来自上传素材或用户文本的隐藏提示注入；
- 提供商密钥不得出现在固件、产品仓库、客户端应用或日志中；
- 在 `E_U1_UNAVAILABLE`、`E_UNSUPPORTED_BOARD`、硬限制警报或紧急停止后不自动重试硬件命令。

需要审批或简化的软门控：

- 高模拟器风险评分；
- 密集上传图像；
- 非常长的文本；
- 大填充区域；
- 未知材料/配置文件；
- 任务估计超过产品延迟/运行时间预算。

云端可在分发前简化比例、点计数或样式，但必须在任务制品和用户/操作员解释中记录该简化。

## 可观测性要求

每个 AI 到运动任务应产生可追踪的链：

```text
request_id
  -> route_decision
  -> model/backend call evidence
  -> generated artifact
  -> vector/path artifact
  -> validation result
  -> simulation result
  -> policy decision
  -> dispatch event
  -> motion_event stream
  -> terminal result
```

路由证据的最小字段：

- `request_id`、`device_id`、`task_id`；
- 任务族和能力；
- 选择的后端和回退链；
- 每阶段延迟；
- 模型输出有效性；
- 安全决策；
- 路径点计数、边界、估计运行时间；
- 最终设备阶段；
- 如果失败的恢复操作。

## 验证命令

主要 LiMa 云端/设备集成检查：

```powershell
python -m pytest tests/test_device_gateway_routes.py -q
python -m pytest tests/test_device_protocol_validation.py -q
python -m pytest tests/test_routing_engine.py -q --tb=short
python scripts/run_pre_commit_check.py --full
```

在推进子模块指针之前的产品仓库检查：

```powershell
cd D:\QWEN3.0\esp32S_XYZ
python tools/validate_schemas.py
python tools/check_gpio.py
python -m unittest discover -s tests -p "test_*.py" -v
python -m unittest tools.fake_u1.tests.test_app -v
python -m unittest tools.fake_device_server.tests.test_app -v
python -m unittest tools.fake_ai.tests.test_app -v
python -m unittest tools.fake_lima_u8.tests.test_app -v
python -m unittest tests.ci.test_fake_integration -v
```

发布候选的公共端点冒烟必须包括：

- `/device/v1/health`；
- 假 U8 WebSocket 会话；
- 一条控制命令；
- 一个 `write_text` 任务；
- 一个带有预览制品的简单 `draw_generated` 任务；
- 一次强制验证失败；
- 一次模拟设备故障和恢复解释。

## 路线图

### 阶段 1：使当前路由显式化

- 记录当前确定性解析器和路径管道行为。
- 为 `write_text` 和 `draw_generated` 添加路由证据。
- 默认保持 `LIMA_DEVICE_LLM_PLANNER=0`。
- 演示优先使用预设和确定性绘图路径。

### 阶段 2：按角色准入绘图模型

- 为线稿质量和矢量化成功构建图像生成夹具。
- 在有日期的准入报告中记录证据。
- 添加专用绘图角色路由偏好，而非重用通用聊天池。
- 保持直接 LLM 到 SVG 为实验性，直到几何夹具通过。
- 准入报告以 `docs/model_admission/` 下的有日期文件为准，并同步 `docs/LIMA_MEMORY_CN.md`、`STATUS.md` 与 `progress.md`。

### 阶段 3：设备配置文件感知路由

- 在路由决策中包含 `workspace_mm`、`profile_rev`、`limits` 和固件版本。
- 将低能力设备路由到更低的点计数和更简单的样式。
- 仅在安全和配置文件兼容性检查后添加每设备粘性记忆。

### 阶段 4：硬件在环发布门

- 先运行假 U8/U1 测试。
- 每个发布候选运行一次物理设备冒烟。
- 验证归零、停止、暂停/恢复、书写、绘图、断开恢复和无重复分发。
- 在声明生产就绪之前记录物理设备证据。
- 交付模板使用 `docs/release_evidence/TEMPLATE_AI_TO_MOTION_RELEASE.md`，并将首份真切片证据放入 `docs/release_evidence/`。

## 更改规则

- 在添加或提升绘图/写字路由使用的模型时更新本文档。
- 当证据更改后端排名或准入状态时更新 `docs/model_admission/` 下的有日期报告；历史免费模型策略只作为参考。
- 仅在路由所有权或生产管道更改时更新 `docs/REQUEST_PIPELINE_AUTHORITY_CN.md`。
- 不得在没有聚焦测试和路由证据的情况下编辑 `router_v3.py` 池。
- 不得在没有产品端测试或明确原因说明为何不能运行的情况下推进 `esp32S_XYZ` 子模块指针。
