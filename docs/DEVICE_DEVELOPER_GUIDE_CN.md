# LiMa 设备开发者入口

> 更新日期：2026-06-16
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
- `device_gateway/task_creation.py`
- `device_gateway/model_routing.py`
- `device_gateway/tasks.py`
- `device_gateway/path_validator.py`
- `device_gateway/path_pipeline.py`

## 常用验证

```powershell
python -m pytest tests/test_device_gateway_model_routing.py tests/test_device_gateway_protocol.py -q
python -m pytest tests/test_device_gateway_routes.py -q
python -m pytest tests/test_device_gateway_path_validator.py -q
```

## 证据要求

- 任何影响任务执行的改动，都要记录 `route_policy`。
- 任何影响几何或运动的改动，都要记录模拟器或假设备证据。
- 任何准备发布的改动，都要写入 `docs/release_evidence/`。

## 常见判断

- 控制命令优先走确定性解析，不先找模型。
- 纯书写优先走确定性路径，模型只做可选润色。
- 绘图类任务先看模型准入和几何安全，再看后端可用性。
- 发现旧文档、旧路径、旧入口时，先更新索引再扩散引用。
