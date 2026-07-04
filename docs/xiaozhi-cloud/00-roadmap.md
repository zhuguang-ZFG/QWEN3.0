# 小智官方云 + DLC 核心实施路线图

> 当前主路线：**在 `D:/QWEN3.0` 内瘦身出 `dlc_core / dlc_api / dlc_mcp`，以小智官方云承载语音/对话/LLM，以 DLC 核心承载写字/绘图/路径/设备控制。**
> 关联总设计：`docs/xiaozhi-cloud/lima-slimdown-design.md`
> 关联入口：`docs/xiaozhi-cloud/README.md`

---

## 1. 路线图目的

本文件用于把当前重构拆成可执行阶段，明确：

- 每一阶段的目标
- 本阶段不做什么
- 进入条件
- 完成标准
- 下一阶段依赖

原则：**先证据、后接口、再实现、最后删除旧系统。**

---

## 2. 总体阶段

| 阶段 | 名称 | 核心目标 |
|------|------|----------|
| P0 | MCP 接入打底 | 证明官方云能发现 DLC MCP tool，并跑通最小 `/health`、`/write`、`/draw` 骨架 |
| P1 | 接口与核心闭环 | 冻结 `dlc_core / dlc_api / dlc_mcp` 边界，跑通写字/预设绘图闭环 |
| P2 | 固件与小程序接入 | 接入 U8/U1 固件、小程序状态页/任务页/一键配网 |
| P3 | 安全与可运维 | 失败恢复、防呆、安全边界、双云部署、观测、回滚 |
| P4 | LiMa 旧系统收缩 | 删除不再需要的旧入口/旧链路/旧文档，完成瘦身 |

---

## 3. P0：MCP 接入打底

### 目标

证明“小智官方云 + 本地 DLC MCP 服务”这条链路成立。

### 已完成项

- `dlc_api` 最小服务已具备：`/health`、`/write`、`/draw`
- `dlc_mcp.server` 已暴露：
  - `dlc.write_text`
  - `dlc.draw_generated`
- `dlc_mcp.mcp_pipe` 已跑通官方云 broker discovery
- 官方云已成功发现上述 tool
- Windows 控制台 UTF-8 输出问题已定位并修复

### 当前限制

- 官方云握手阶段只完成 tool discovery，真实 `tools/call` 需通过智能体对话触发
- `dlc.draw_generated` 当前受图像生成链路限制，出现 `414 Request-URI Too Large`

### 完成标准

满足以下条件即可认定 P0 完成：

1. `dlc.write_text` / `dlc.draw_generated` 能被官方云发现
2. `/write` 本地提交成功并返回 `task_id`
3. 聚焦测试通过
4. P0 证据已落文档

### 进入 P1 条件

- P0 证据文档已收口
- 主路线与目录入口已统一

---

## 4. P1：接口与核心闭环

### 目标

把“最小可用骨架”升级为“可实施的稳定接口层”。

### 本阶段重点

1. 冻结 `dlc_core` 模块边界：
   - `intent`
   - `write`
   - `draw`
   - `path_pipeline`
   - `path_validator`
   - `dispatch`
   - `device_status`
2. 冻结 `dlc_api` 路由边界
3. 冻结 `dlc_mcp` tool 边界
4. 跑通：
   - 写字闭环
   - 预设图形绘图闭环
   - `draw_from_image` 设计路径（可先文档冻结，后实现）
5. 明确 `draw_generated` 的路线选择：
   - 优化 prompt / 后端；或
   - 降级为预设图形 + 图片矢量化优先

### 本阶段不做

- 不先做大规模旧代码删除
- 不先做双云高可用
- 不先做复杂 observability 改造

### 完成标准

1. `02-service-refactor.md` 完成并冻结接口
2. `dlc.write_text` 可稳定提交任务
3. `draw_generated` 路线选择明确
4. `draw_from_image` 是否进入 P2 已决策

### 进入 P2 条件

- 服务端接口边界已冻结
- 固件/小程序所需依赖输入已明确

---

## 5. P2：固件与小程序接入

### 目标

把服务端骨架接到真正的设备与用户入口上。

### 本阶段重点

#### 固件端

- U8 端：
  - `self.motor.run_path`
  - `self.plotter.write_text` / `self.plotter.draw_generated` 的角色冻结
  - `motion_busy_` 防呆机制
- U1 端：
  - Edge-D UART 协议执行稳定
  - HOME / MOVE / PATH_BEGIN / PATH_SEG / PATH_END 路径完整性

#### 小程序端

- 登录 / 设备绑定
- 一键配网
- 状态页 / 任务页
- 写字 / 画图入口
- 尽量减少蓝牙大数据传输依赖，优先 Wi-Fi / HTTP / 任务化交互

### 本阶段不做

- 不做全量 LiMa 清理
- 不做多实例水平扩展
- 不做复杂多租户控制台重构

### 完成标准

1. 固件文档 `03-firmware-refactor.md` 完成并冻结
2. 小程序文档 `04-miniprogram-refactor.md` 完成并冻结
3. 真机至少跑通一条写字路径
4. 一键配网方案清晰并可实施

### 进入 P3 条件

- 真机基础路径成功
- 用户操作链路已明确

---

## 6. P3：安全与可运维

### 目标

把系统从“能跑”提升到“可维护、可观察、可恢复”。

### 本阶段重点

1. 失败恢复
   - 重试策略
   - 死信
   - 用户通知
2. 防呆与安全边界
   - device busy
   - 路径越界
   - 未 HOME
   - 急停
3. 双云部署分工
   - 阿里云：公网入口 / edge
   - JDCloud：数据 / 后台 / 观测
4. 观测与回滚
   - health
   - metrics
   - deploy / rollback 最小闭环

### 完成标准

1. `05-deployment-and-ops.md` 完成
2. `06-failure-and-safety.md` 完成
3. `07-validation-and-acceptance.md` 初版完成
4. 失败场景与防呆场景有明确验收矩阵

### 进入 P4 条件

- 新主线已可稳定承载产品
- 旧系统只剩历史包袱

---

## 7. P4：LiMa 旧系统收缩

### 目标

在不破坏 DLC 主线的前提下，删除不再需要的旧入口与旧链路。

### 本阶段重点

- 标记旧入口为 legacy
- 删除不再使用的 chat/LLM 路由主链
- 删除与当前产品无关的旧文档入口
- 清理重复任务入口与重复协议层

### 前提约束

只有在以下全部满足时才能进入：

1. 新链路已稳定运行
2. 文档、测试、部署路径完整
3. 小程序与固件都已切到新主线
4. 用户确认可以开始大范围瘦身

### 完成标准

- 旧链路被明确标注或删除
- 文档入口完全切到新体系
- 项目结构明显简化

---

## 8. 关键里程碑判断

### 当前所在位置

**当前处于：P0 已完成，正在进入 P1 前的文档收口阶段。**

### 当前真正应该先做什么

不是继续写代码，而是先完成：

1. 文档入口统一
2. 路线图落地
3. P0 证据文档收口
4. 开放问题显式归档

---

## 9. 风险提醒

1. 如果在 P1 前不先统一文档入口，后续实现会反复摇摆。
2. 如果在 P2 前不冻结服务端接口，固件/小程序会被来回返工。
3. 如果在 P3 前就开始大删 LiMa，回滚成本会很高。
4. 如果把未验证的 LLM 行为当成确定事实，会在设备端联调阶段踩坑。

---

## 10. 下一步执行顺序

按优先级：

1. `README.md`（已完成）
2. `00-roadmap.md`（本文件）
3. `09-p0-evidence.md`
4. `08-open-questions.md`
5. `01-architecture.md`
6. `02-service-refactor.md`

这是当前最小、最稳、最符合 Ponytail 的推进顺序。
