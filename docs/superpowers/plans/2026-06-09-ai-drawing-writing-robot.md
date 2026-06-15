# AI 画图写字机方案

> 日期：2026-06-09
> 更新：2026-06-10，替换无效编码旧文档并清理退役适配残留
> 状态：当前方案文档
> 范围：LiMa 云端服务与 `esp32S_XYZ` 画图/写字机的产品、协议、路由和发布边界

## 目标

把 LiMa 从通用编码助手后端收敛为 AI 智能设备云端服务，优先服务
`esp32S_XYZ` AI 画图/写字机：

- 用户通过语音、文字或网页下达绘画/写字指令；
- LiMa 负责意图理解、模型选择、生成规划、路径校验、安全策略和任务调度；
- `esp32S_XYZ` 负责 U8 AI MCU、U1 运动 MCU、设备协议、假设备、固件和硬件证据；
- 真实运动只接受经过验证的任务和路径，不直接相信模型输出。

## 当前边界

### LiMa 负责

- 多后端 AI 路由、模型准入、健康状态、预算和降级；
- 设备任务生成与 `/device/v1/*` 网关；
- 画图/写字任务的 `route_policy`、任务账本、预览 artifact、校验和恢复解释；
- 公共域名、VPS 部署、Redis 任务队列和运维证据；
- 长期文档、状态、进展和跨仓库兼容记录。

### `esp32S_XYZ` 负责

- U8 AI MCU 固件和 LiMa 协议适配；
- U1 motor MCU 确定性运动执行；
- Edge-A/B/C/D schemas、示例、假设备和产品经理服务；
- GPIO、归零、限位、OTA、配网、硬件验证和产品发布证据。

## 退役边界

旧编码助手适配已经退出当前产品方向：

- 不再作为 AI 画图/写字机的协议目标；
- 不再在热路径注册专用路由或后端；
- 不再保留专用测试、脚本或运行时缓存；
- 只允许在归档、历史进展和长期记忆里保留审计引用。

如果未来需要借鉴外部编码工具，只能作为参考资料进入 `docs/archive/`
或 `docs/reference/`，不能重新进入设备热路径。

## 核心场景

| 场景 | 输入 | LiMa 处理 | 设备输出 |
|---|---|---|---|
| 写字 | “写春节快乐” | 文本清洗、布局、字形/模板选择、路径校验 | 落笔书写 |
| 简笔画 | “画一只猫” | 任务分类、图像/向量角色路由、路径生成和校验 | 线条绘画 |
| 临摹 | 上传图片 | 图像预处理、边缘/轮廓提取、简化和校验 | 轮廓临摹 |
| 练字 | “楷书写永字” | 字帖模板、笔画顺序、布局和速度限制 | 规范笔画 |
| 控制 | 暂停、继续、停止、回零 | 确定性解析，不调用模型 | 设备控制 |

## 路由策略

设备任务先按任务族分类，再选择模型角色：

1. 控制类任务使用确定性解析，不调用 LLM。
2. 普通写字优先使用模板、字体和路径算法。
3. 创意写字只允许模型生成受控 JSON 规划，路径仍由校验器把关。
4. 简单图形优先使用预设 SVG/asset。
5. 生成绘画必须经过模型准入、向量化、边界校验、点数限制和预览 artifact。
6. 上传图片必须经过隐私/内容策略、图像简化和路径校验。

详细规则以 `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md` 为准。

## 当前已落地

- `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md` 已成为设备模型路由准则。
- `device_gateway/model_routing.py` 已定义设备任务路由角色：
  `device_control`、`device_write`、`device_draw`、`device_vector`、
  `device_unknown`。
- `device_gateway/tasks.py` 已在 `motion_task` 中携带 `route_policy`。
- `esp32S_XYZ` commit `a8d98e3` 已让 Edge-B/C `motion_task` schema 接受
  `route_policy`。
- 主仓库 commit `423bf3e` 已更新 `esp32S_XYZ` 子模块指针。
- 主仓库 commit `ce1172d` 已补充全项目优化路线图。

## 下一步实施顺序

### 1. 假 U8 消费 `route_policy`

目标：产品侧假 U8 能解析、记录并回传 `route_policy`，为真实固件改动建立证据。

涉及文件：

- `esp32S_XYZ/tools/fake_lima_u8/app.py`
- `esp32S_XYZ/tools/fake_lima_u8/tests/test_app.py`
- `esp32S_XYZ/schemas/**/motion_task*.json`

验证：

```powershell
cd D:\QWEN3.0\esp32S_XYZ
python tools\validate_schemas.py
python -m unittest tests.ci.test_validate_schemas -v
python -m unittest tools.fake_lima_u8.tests.test_app -v
```

### 2. 设备 artifact 记录路由证据

目标：每个 AI 到运动任务都能追踪到路由角色、模型角色、校验结果和终态事件。

涉及文件：

- `device_gateway/tasks.py`
- `device_artifacts/`
- `tests/test_device_gateway_model_routing.py`

验证：

```powershell
python -m pytest tests/test_device_gateway_model_routing.py tests/test_device_gateway_protocol.py -q
```

### 3. 建立模型准入报告

目标：所有进入画图/写字热路径的模型都有 dated evidence。

建议文件：

- `docs/model_admission/YYYY-MM-DD-device-drawing-writing.md`

报告必须记录：

- 后端 id、provider、model id；
- 任务角色；
- fixture 数量、通过数量、平均延迟；
- 失败模式；
- 准入结论和回滚规则。

### 4. 物理硬件发布门禁

目标：区分“云端可用”和“真实硬件可发布”。

发布证据至少包含：

- `/device/v1/health`；
- 假 U8 WebSocket；
- 控制、写字、绘画、校验失败、断线恢复；
- 真实设备板卡版本、固件版本、点数、路径预览、终态事件；
- 操作员记录和回滚策略。

## 不做事项

- 不把供应商密钥写入固件、移动端、网页端或产品示例。
- 不让模型直接决定运动执行。
- 不跳过路径校验和仿真。
- 不把本地 Windows 代理当作 VPS 可达能力。
- 不在没有假设备和硬件证据时宣称真实设备发布完成。

## 关联文档

- `docs/PROJECT_OPTIMIZATION_ROADMAP_CN.md`
- `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md`
- `docs/ESP32S_XYZ_MANAGEMENT_CN.md`
- `docs/REQUEST_PIPELINE_AUTHORITY_CN.md`
- `docs/device_protocol_alignment.md`
- `STATUS.md`
- `progress.md`
- `docs/LIMA_MEMORY_CN.md`
