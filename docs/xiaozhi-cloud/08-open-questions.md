# 未决问题清单：小智官方云 + DLC 主线

> 关联入口：`docs/xiaozhi-cloud/README.md`
> 关联证据：`docs/xiaozhi-cloud/09-p0-evidence.md`
> 关联路线图：`docs/xiaozhi-cloud/00-roadmap.md`
> 收口原则：**任何未实测、未定型、未决策的事项必须显式登记在本文件，且不得在其它设计稿里当成确定事实。**

---

## 1. 本文件的角色

`09-p0-evidence.md` 只记录“已经跑通过、已经看到过、已经修好”的事实。
本文件与之对称：**只记录尚未验证、尚未决策、尚未收敛的事项**，并给出：

- 当前状态
- 为什么它是未决
- 打算在哪个阶段解决
- 解决前的默认策略（不能因为未决就阻塞主线）

任何 P1~P4 的设计文档如果引用了未决项，必须显式回指本文件的对应条目编号（`Q-*`）。

---

## 2. 未决项一览

| 编号 | 主题 | 严重度 | 打算解决阶段 |
|------|------|--------|--------------|
| Q-01 | 官方云 LLM 在真实对话中是否会稳定链式调用多个 MCP tool | 高 | P1 实测 |
| Q-02 | `dlc.draw_generated` 图像生成链路（后端 / 提示词 / 传输方式）如何收敛 | 高 | **P1 已解决**：降级为预设图形优先，AI 生图延后 |
| Q-03 | `draw_from_image`（图库图片矢量化）是否进入 P2 主链路 | 中 | P1 决策 |
| Q-04 | 服务端 MCP 接入模式最终采用 A（官方直连）还是 B（自托管 mcp-endpoint-server） | 高 | P1 冻结 |
| Q-05 | 图库存储长期方案（保留 Telegram，还是切到 S3 / R2 / MinIO） | 中 | P4 或按容量触发 |
| Q-06 | `shadow_store` 是否需要迁移到 Redis 以支持多实例部署 | 中 | 触发条件：需要 2+ `dlc_api` 实例时 |
| Q-07 | `dlc_api` 鉴权：`v2_device_token` DB 表 vs `LIMA_DEVICE_TOKENS` env 兜底的边界 | 高 | **P1 部分解决**：位置冻结为 `dlc_api/deps.py`，per-device token 下放 P2/P3 |
| Q-08 | 固件 `motion_busy_` 防呆机制的最终实现路径与回归验证 | 高 | P2 实施 |
| Q-09 | 小程序一键配网的 UX 与底层通道（Wi-Fi 直连 / 蓝牙 / 云侧激活） | 高 | P2 实施 |
| Q-10 | 官方云智能体“角色 prompt”与“MCP tool 强制调用”的边界 | 中 | P2 结合真机验证 |
| Q-11 | 双云部署下 `dlc_mcp` 是否需要跟随 `dlc_api` 一起做灾备 | 中 | P3 决策 |
| Q-12 | LiMa 旧链路的具体删除清单与切换开关 | 高 | P4 冻结 |

---

## 3. 详细条目

### Q-01 官方云 LLM 在真实对话中是否会稳定链式调用多个 MCP tool

- **背景**：`lima-slimdown-design.md` 中路径 A（纯 MCP）依赖 LLM 在拿到 `dlc.write_text` 返回的路径后主动继续调用 `self.motor.run_path` 或 `self.plotter.*`。
- **已知事实**：
  - 自托管 `xinnan-tech/xiaozhi-esp32-server` 的 `connection.py` 已确认平台支持多轮 tool call（`MAX_DEPTH=5` + `chat(depth+1)`）。
  - 但 `xiaozhi.me` 官方云是闭源服务，我们只能间接推测。
  - P0 阶段官方云 broker 只完成 discovery，未验证真实语音对话下的 tool call 行为。
- **风险**：如果官方云 LLM 在一次对话里不稳定地做多轮 tool call，路径 A 会退化，用户体验会打折。
- **默认策略（在未验证前）**：
  - P1 起路径 B（小程序 HTTP dispatch）与路径 C（语音 + 小程序确认）作为**主备**，不押注路径 A。
  - 路径 A 的启用条件是 Q-01 得到实测正结论。
- **解决方式**：P1 用真实智能体做一句“写你好”与“画一颗星星”的完整对话测试，抓 broker 交互日志。
- **相关文档**：`lima-slimdown-design.md §2.3`；`00-roadmap.md §4`；`09-p0-evidence.md §4.2`。

### Q-02 `dlc.draw_generated` 图像生成链路如何收敛（已解决）

- **背景**：P0 已实测 `draw_generated` 端到端失败：
  - DashScope：`401 InvalidApiKey`
  - Pollinations：`414 Request-URI Too Large`（提示词增强导致 URL 超长）
- **P1 决策**：采用方向 4 + 5 组合：
  - `dlc.draw_generated` 保留为正式 tool，但 P1 默认 `allow_dashscope=False`；
  - 实际语义降级为「预设图形匹配 → 字体路径 → AI 生图（仅小程序/显式开启时）」；
  - AI 生图端到端承诺延后到后端修复完成。
- **默认策略**：
  - MCP/固件调用 `draw_generated` 时只走预设图形/字体路径；
  - 小程序 HTTP 调用可显式开启 `allow_dashscope=True` 尝试 AI 生图。
- **解决方式**：已在 `dlc_core/draw.py` 落地，证据见 `10-p1-evidence.md §2.4`。
- **相关文档**：`lima-slimdown-design.md §3.2/§3.4`；`09-p0-evidence.md §4.1`；`10-p1-evidence.md §2.4`。

### Q-03 `draw_from_image` 是否进入 P2 主链路

- **背景**：`draw_from_image` 依赖 `xiaozhi_drawing.svg_converter` 的图片矢量化能力，是路径 A/B/C 中最“确定性可控”的绘图入口。
- **未决点**：
  - Telegram `getFile` URL 时效 5~10 分钟，`dlc_api` 是否必须“收到请求即下载到本地临时文件”；
  - 200 点上限下的分片/压缩策略是否需要在 P2 前落地；
  - 是否要在 P2 提供小程序端“图库选图 → 一键写画”入口。
- **默认策略**：`draw_from_image` 进入 P2 的语音路径需先在 P1 完成设计冻结（§Q-04 也影响这里）。
- **解决方式**：在 `02-service-refactor.md`（P1）中给出 `handle_draw_from_image` 接口签名与临时文件策略。
- **相关文档**：`lima-slimdown-design.md §2.3/§3.2`；`00-roadmap.md §4.6`。

### Q-04 服务端 MCP 接入模式最终选 A 还是 B

- **背景**：
  - 模式 A：`dlc_mcp` 直连 `wss://api.xiaozhi.me/mcp/?token=<JWT>`；无需自部署 broker，配置最简单。
  - 模式 B：接入自托管 `mcp-endpoint-server`；便于私有化部署与调试。
- **P0 事实**：P0 阶段已实测模式 A 成功完成 discovery。
- **未决点**：
  - 生产环境是否要长期依赖官方 broker？
  - 是否需要在 B 模式下自建一层，把多台 `dlc_mcp` 挂到同一 broker 做多设备/多租户？
- **默认策略**：**P0/P1 沿用模式 A**；模式 B 只作为后续私有化交付或调试环境备选。
- **解决方式**：P1 明确“主线 = A”写入 `05-deployment-and-ops.md`（当此文件后续新增时）。
- **相关文档**：`lima-slimdown-design.md §1.3`；`p0-mcp-smoke-commands.md §4`。

### Q-05 图库存储长期方案

- **背景**：当前图库把 Telegram Bot API 作为对象存储；容量与速率有硬上限。
- **未决点**：
  - 是否在产品放量前主动切换到 S3/R2/MinIO；
  - 是否保留 `gallery_store` 抽象层以便未来平滑替换。
- **默认策略**：P4 前不动 Telegram 图盘；`gallery_store` 抽象保持稳定即可。
- **解决方式**：等到图片量或速率触碰阈值时再触发迁移，替换 `integrations/telegram_bot/client.py`。
- **相关文档**：`lima-slimdown-design.md §1.6.1`。

### Q-06 `shadow_store` 是否迁移到 Redis

- **背景**：`device_intelligence/shadow.py` 当前是进程内 `dict + RLock`，不跨实例共享。
- **未决点**：
  - P2 是否单实例部署即可满足所需并发；
  - 何时触发水平扩展（多 `dlc_api` 实例）。
- **默认策略**：**P2 默认单实例**；只有触发扩展条件后才做 Redis 化。
- **解决方式**：等 P3 观测数据出来后再判断，触发条件：并发或可用性 SLA 要求 2+ 实例。
- **相关文档**：`lima-slimdown-design.md §1.6.4`；`00-roadmap.md §6`。

### Q-07 `dlc_api` 鉴权最终边界（P1 部分解决）

- **背景**：设计文档要求 `verify_dlc_api_token` 主要使用 `v2_device_token` 表；`LIMA_DEVICE_TOKENS` 只作为开发/应急兜底。
- **P1 决策**：
  - 正式实现位置确定为 `dlc_api/deps.py`；
  - P1 使用 `LIMA_DEVICE_TOKENS` env 兜底，保证接口边界存在且不阻塞 P1 闭环；
  - per-device token 下发与 `v2_device_token` 表接入放到 P2/P3。
- **未决点**：
  - per-device token 下发流程（小程序激活时生成还是预生成）；
  - `v2_device_token` 表读写的具体实现。
- **默认策略**：
  - P1/P2 继续使用 env 兜底；
  - 代码中保留 `FIXME-Q07` 标记，提醒 P2 必须替换。
- **解决方式**：`dlc_api/deps.py` 已落地占位实现，证据见 `10-p1-evidence.md §2.2`。
- **相关文档**：`lima-slimdown-design.md §3.3`；`10-p1-evidence.md §4`。

### Q-08 固件 `motion_busy_` 防呆机制

- **背景**：`lima-slimdown-design.md §1.6.6` 已经给出层 1（固件）+ 层 2（服务端）+ 层 3（可选）的方案。
- **未决点**：
  - 层 1 的具体落点：所有 `RunPathWithTaskId` / `ExecuteHomeWithTaskId` / `ExecuteMoveWithTaskId` / `ExecuteMoveRelWithTaskId` 都需要覆盖；
  - `pause` / `resume` / `stop` 保持豁免的边界；
  - 真机回归验证方案。
- **默认策略**：P2 前不进固件；文档冻结在 `03-firmware-refactor.md`。
- **解决方式**：P2 内实施，配合真机与假 U1 双通道验证。
- **相关文档**：`lima-slimdown-design.md §1.6.6`。

### Q-09 小程序一键配网

- **背景**：用户已经明确“配网必须简单方便”。
- **未决点**：
  - Wi-Fi 直连 vs 蓝牙 vs 云侧激活的组合；
  - 蓝牙大数据传输受限的现实（小程序蓝牙对大数据流不友好）；
  - 配网期间是否允许小程序侧显式指引跳过。
- **默认策略**：P2 冻结 UX 与技术方案到 `04-miniprogram-refactor.md`。
- **解决方式**：P2 前先做一次“配网体验矩阵”，明确哪几步是必需的、哪几步可以自动化。
- **相关文档**：`lima-slimdown-design.md §1.4`；`00-roadmap.md §5`。

### Q-10 官方云“角色 prompt” vs “MCP tool 强制调用”的边界

- **背景**：小智官方控制台允许配置智能体角色 prompt，可以覆盖 80% 的知识问答。
- **未决点**：
  - 哪些问题走角色 prompt、哪些必须调 MCP tool（如 `get_device_status`）；
  - 角色 prompt 会不会在真实对话中被 LLM 忽略而误答。
- **默认策略**：
  - 状态类问答（“机器在忙什么？”“任务进度？”）：必须调 `dlc.get_device_status`；
  - 知识类问答（“怎么归位？”“错误码含义”）：先走 prompt，动态知识再挂 tool。
- **解决方式**：P2 结合真机对话做一次“绕过工具调用”回归。
- **相关文档**：`lima-slimdown-design.md §1.6.3`。

### Q-11 双云下 `dlc_mcp` 是否需要一起做灾备

- **背景**：设计文档默认阿里云做入口，JDCloud 做数据后台。
- **未决点**：
  - `dlc_mcp` 是否也要在 JDCloud 常驻热备；
  - 官方云 broker 侧是否允许一个 endpoint 同时挂两条 stdio 桥接。
- **默认策略**：P3 前不做；P2 结束前默认阿里云单实例 `dlc_mcp`。
- **解决方式**：P3 时结合可用性目标与故障演练结果再定。
- **相关文档**：`lima-slimdown-design.md §1.5`。

### Q-12 LiMa 旧链路删除清单

- **背景**：P4 要做“LiMa 旧系统收缩”。
- **未决点**：
  - 哪些旧路由 / 旧后台 / 旧脚本 / 旧文档必须删除；
  - 是否需要一段“legacy alias”过渡期。
- **默认策略**：
  - P1~P3 期间**不做**大规模删除；
  - 只做 legacy 标记与新入口迁入。
- **解决方式**：P4 时依据 P3 结束状态生成删除清单。
- **相关文档**：`00-roadmap.md §7`。

---

## 4. 处理约束

- 未决项在被解决前，不得在其它设计稿里写成确定事实。
- 未决项被解决后，必须做两件事：
  1. 在 `09-p0-evidence.md` 或对应阶段文档补一条“已验证事实”。
  2. 在本文件把该 `Q-*` 条目标记为“已解决”并注明去向。
- 新出现的疑问优先登记为新的 `Q-*` 条目，而不是暗塞进主设计稿。

---

## 5. 下一步

按照 `00-roadmap.md`，未决项的实际解决顺序建议：

1. **P1 前**：Q-04（MCP 接入模式冻结）、Q-02（`draw_generated` 方向选择）、Q-07（鉴权边界）
2. **P1 中**：Q-01（官方云真实对话下 tool 调用行为）、Q-03（`draw_from_image` 主链路决策）
3. **P2**：Q-08（固件防呆）、Q-09（一键配网）、Q-10（角色 prompt 边界）
4. **P3**：Q-06（`shadow_store` Redis 化）、Q-11（双云 MCP 灾备）
5. **P4**：Q-12（旧链路删除清单）、Q-05（图库长期方案，如已触发容量阈值）
