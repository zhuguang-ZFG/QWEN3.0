# 小智服务端精简迁移设计

> 日期：2026-07-04
> 状态：历史/备选路线（当前默认路线已切换为 `D:/QWEN3.0` 内瘦身：`dlc_core / dlc_api / dlc_mcp`）
> 目标工作区：`D:\xiaozhi-dlc-server`
>
> 说明：本文档记录的是早期“独立新仓 `D:\xiaozhi-dlc-server`”迁移思路，现保留作历史对照与备选方案。
> 当前权威主路线请以 `docs/xiaozhi-cloud/README.md`、`docs/xiaozhi-cloud/00-roadmap.md`、`docs/xiaozhi-cloud/lima-slimdown-design.md` 为准。

## 背景

当前 `D:\QWEN3.0` 的 LiMa 已演进为多后端 AI 路由 + 智能硬件云平台，包含路由、官网、SDK、文档站、设备网关、图库、OTA、provider 探测、记忆与可观测等大量能力。

如果目标只是尽快做出稳定的 ESP32 写字机/绘图机产品，继续在 LiMa 上叠加会带来过重的维护成本。`D:\QWEN3.0\esp32S_XYZ\server\xiaozhi-esp32-server` 里的上游小智服务端主体已于 2026-06-25 物理删除，只保留历史 README 和小程序等残留，因此需要重新从 GitHub 上游恢复服务端。

## 决策

采用“上游小智服务端为主，LiMa 作为能力参考库”的路线。

新建独立工作区：

```text
D:\xiaozhi-dlc-server
```

该工作区用于拉取并改造 GitHub 上游 `xinnan-tech/xiaozhi-esp32-server`。LiMa 不再作为新硬件产品服务端主线，只保留为参考仓库和能力库。

## 目标

第一阶段目标是跑通最小写字/绘图闭环：

```text
微信小程序 / 测试 HTTP 请求
  → 精简小智服务端
  → 识别 write_text 或 draw_generated
  → 生成 motion_task / run_path
  → 通过小智 WebSocket 或 MQTT 下发到 U8
  → U8 通过 UART Edge-D 转给 U1
  → 假 U1 或真实 U1 返回 done
```

## 非目标

第一阶段明确不做：

- 多后端 AI 路由平台
- 170+ 后端健康、预算、fallback
- provider automation / provider probe
- semantic cache
- session memory / learning loop
- routing ML
- Chat Web / 官网 / docs-site / 三语言 SDK
- Fleet worker 系统
- 复杂 Prometheus/Grafana 可观测体系
- Telegram 图库存储
- 完整 OTA 发布系统
- 完整多租户管理后台重构

## 拟保留/迁移的 LiMa 能力

只迁移设备闭环必须能力：

| 能力 | LiMa 参考路径 | 迁移方式 |
|---|---|---|
| 写字/绘图意图规则 | `device_gateway/intent.py` | 提取确定性规则，避免引入 LiMa 路由依赖 |
| 文本/SVG/path 管线 | `device_gateway/path_pipeline.py` | 迁移精简纯函数版本 |
| path 校验 | `device_gateway/path_validator.py` | 迁移核心安全校验 |
| AI 绘图参数 | `device_gateway/task_draw_params.py` | 迁移最小 draw 参数构建 |
| 绘图处理 | `device_gateway/device_draw_handler.py` | 迁移预设/SVG/OpenCV 必需部分 |
| Edge-A/B/C/D 契约 | `esp32S_XYZ/docs/schemas/` | 作为协议依据，不复制无关文档 |
| U8↔U1 桥接 | `esp32S_XYZ/firmware/u8-xiaozhi/.../u1_protocol_client.cc` 等 | 固件侧参考，不直接搬到服务端 |
| 小程序写画 UI | `esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/` | 后续按接口适配 |

## 新服务端建议结构

在上游服务端内新增产品适配包，避免污染原有小智核心：

```text
main/
  xiaozhi-server/
    dlc_device/
      __init__.py
      intent.py
      task_model.py
      path_pipeline.py
      path_validator.py
      drawing.py
      u1_protocol.py
      routes.py
      tests/
```

职责边界：

- `intent.py`：把文本/语音结果分类为 `write_text`、`draw_generated`、`device_control`。
- `task_model.py`：定义最小任务结构和 `motion_task/run_path` 输出。
- `path_pipeline.py`：文本/SVG/简笔画到路径的确定性转换。
- `path_validator.py`：工作区、点数、feed、坐标边界、安全参数校验。
- `drawing.py`：AI 绘图/预设图形/图片矢量化的最小入口。
- `u1_protocol.py`：服务端侧用于测试和生成 Edge-D payload 的协议工具。
- `routes.py`：提供 PoC HTTP 端点，后续再接入小智 WS/MQTT 主链路。

## 接入策略

第一阶段先不改深层小智对话链路。

先提供最小 HTTP PoC 端点，例如：

```text
POST /dlc/tasks/preview
POST /dlc/tasks/dispatch
GET  /dlc/tasks/{task_id}
```

跑通后再选择接入点：

1. 小程序直接调用 `/dlc/tasks/*`。
2. 小智设备语音结果进入 `dlc_device.intent`。
3. 生成的 `motion_task` 复用小智现有设备通道下发。

## 验证策略

第一阶段验证优先级：

1. 单元测试：intent、path_pipeline、path_validator。
2. 假设备测试：假 U8 / 假 U1 收到任务并返回 done。
3. 本地服务冒烟：HTTP preview/dispatch。
4. 小程序联调：提交一句话生成任务。
5. 真机验证：U8→U1 UART、运动边界、激光/舵机安全。

不把本地假设备验证等同于真机发布证据。涉及真实运动、激光、OTA、配置写入时必须单独做硬件验证。

## 风险与约束

- 上游小智服务端重新拉取后，先保持可同步上游，不要大面积改核心目录。
- 不把 LiMa 的路由平台复杂度搬过去。
- 不做“为了未来灵活”的 registry/factory；需要分支时用简单显式判断。
- 不保留两套并行任务系统；PoC 跑通后应选定唯一任务入口。
- 任何凭证、token、VPS 密码、设备密钥都不迁移进仓库。
- `D:\QWEN3.0` 继续保留，不做破坏性删除。

## 第一阶段完成标准

满足以下条件即可认为迁移准备阶段完成：

- `D:\xiaozhi-dlc-server` 已存在并包含上游小智服务端。
- 上游服务端最简启动路径已确认。
- `dlc_device` 适配包的实现计划已写出。
- 已列出从 LiMa 迁移的具体文件和不迁移清单。
- 已有最小测试计划，覆盖 intent、path、安全边界、假设备 done。
