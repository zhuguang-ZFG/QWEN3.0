# LiMa 设备开发者入口

> 更新日期：2026-06-18
> 目标：给设备联调、模型准入、任务发布和故障排查提供一页式入口。

## 适用场景

- 新增或调整设备任务能力
- 验证 `route_policy`、profile、模型准入或发布证据
- 联调假 U8 / 假 U1 / 真实设备链路
- 排查 `motion_event`、任务阻断、准入失败和发布门问题

## 最小闭环

1. 先看 [设备协议](device_protocol_alignment.md)。
2. 再看 [模型路由指南](AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md)。
3. 然后看 [发布证据模板](release_evidence/TEMPLATE_AI_TO_MOTION_RELEASE.md)。
4. 最后按 [路线图](PROJECT_OPTIMIZATION_ROADMAP_CN.md) 选择当前阶段任务。

## 开发时优先检查

- `routes/device_gateway.py`
- `device_gateway/task_creation.py` — 任务投影与仿真
- `device_gateway/task_draw_params.py` — **draw_generated 参数构建（AI 绘图接入点）**
- `device_gateway/device_draw_handler.py` — 万相简笔画 → SVG 矢量化
- `device_gateway/model_routing.py`
- `device_gateway/tasks.py`
- `device_gateway/path_validator.py`
- `device_gateway/path_pipeline.py`

## draw_generated 热路径（2026-06-18）

```text
transcript / POST /device/v1/tasks / /device/v1/app/tasks
  → resolve_voice_task / 结构化 capability
  → project_to_motion_task_async
  → build_run_params_async (task_draw_params.py)
       ├─ prompt 像 SVG path → render_svg_task（本地，无 AI）
       └─ 否则 → handle_device_draw（预设 / 万相 / OpenCV）
  → validate_capability_params → policy_engine → motion_task (run_path)
```

生图失败返回 `error.code=draw_failed`，不会回退到笔画字库。

## 常用验证

```powershell
python -m pytest tests/test_task_creation_draw_generated.py -q
python -m pytest tests/test_device_gateway_model_routing.py tests/test_device_gateway_protocol.py -q
python -m pytest tests/test_device_gateway_routes.py -q
python -m pytest tests/test_device_gateway_path_validator.py -q
python -m pytest tests/test_device_draw_handler.py tests/test_draw_prompt_enhancer.py -q
```

TDD 证据：[`testing/draw_generated_task_creation.tdd.md`](testing/draw_generated_task_creation.tdd.md)

## 证据要求

- 任何影响任务执行的改动，都要记录 `route_policy`。
- 任何影响几何或运动的改动，都要记录模拟器或假设备证据。
- 任何准备发布的改动，都要写入 `docs/release_evidence/`。
- 自然语言 AI 绘图改动需确认 VPS 已配置 DashScope 图像凭证，否则预期 `draw_failed`。

## 常见判断

- 控制命令优先走确定性解析，不先找模型。
- 纯书写优先走确定性路径，模型只做可选润色。
- 绘图类任务：`device_draw` + `image_then_vector` 经 `handle_device_draw` 执行；不是 `render_text_task`。
- 已是 SVG path 的 prompt 本地解析，不调万相。
- 发现旧文档、旧路径、旧入口时，先更新索引再扩散引用。
