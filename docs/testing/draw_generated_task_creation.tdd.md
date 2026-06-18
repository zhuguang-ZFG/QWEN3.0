# draw_generated 任务创建 TDD 证据

来源：将 `device_draw_handler` 接入 `task_creation` 主热路径，修复自然语言绘图误走笔画字库的问题。

## 用户旅程

1. 作为设备用户，我说「画一只猫」时，云端应走 AI 简笔画生图与矢量化，而不是把汉字当 `write_text` 描出来。
2. 作为开发者，我提交已是 SVG path 的 `draw_generated` prompt 时，应本地解析，不调用 DashScope。
3. 作为运维，当万相/矢量化失败时，任务应明确 `draw_failed`，不能静默降级。

## 任务报告

- RED：新增 `tests/test_task_creation_draw_generated.py`，断言 `project_to_motion_task_async` 会 `await handle_device_draw`；修复前自然语言走 `render_text_task`。
- GREEN：
  - 新增 `device_gateway/task_draw_params.py`（`build_draw_generated_params` / `build_run_params_async`）。
  - `task_creation.py` 提供 `project_to_motion_task_async`、`create_task_from_transcript_async`。
  - `routes/device_gateway_ws_handlers.py`、`device_gateway/task_service.py`、`routes/device_app_tasks.py` 改为 await 异步入口。
- REFACTOR：删除未使用的同步 `_build_run_params`；绘图参数构建独立为 `task_draw_params.py`（`task_creation.py` ≤300 行）。

## 验证命令

```powershell
.venv310\Scripts\python.exe -m pytest tests\test_task_creation_draw_generated.py -q
.venv310\Scripts\python.exe -m pytest tests\test_device_gateway_routes.py tests\test_device_gateway_model_routing.py tests\test_device_gateway_profiles.py -q
.venv310\Scripts\ruff.exe check device_gateway\task_creation.py device_gateway\task_draw_params.py routes\device_app_tasks.py
```

## 保证

| # | 保证 | 测试 | 结果 |
|---|---|---|---|
| 1 | 自然语言 `draw_generated` 调用 `handle_device_draw` | `test_draw_generated_natural_language_uses_device_draw_handler` | PASS |
| 2 | SVG path prompt 跳过 AI 生图 | `test_draw_generated_svg_prompt_skips_device_draw_handler` | PASS |
| 3 | 生图失败产生 `draw_failed` 任务 | `test_draw_generated_handler_failure_becomes_failed_task` | PASS |

## 生产依赖

- 自然语言绘图需要 DashScope 图像 API 凭证（通常 `ALIYUN_API_KEY`）及 OpenCV（`cv2`）用于矢量化。
- 凭证缺失或配额不足时，任务以 `draw_failed` 终态返回，符合 AGENTS.md Hard Rule 1（禁止静默降级）。

## 已知缺口

- 假 U1 / 真机端到端「画一只猫」全链路证据仍待 `firmware_hardware_gate.py --hardware-smoke` 与实机刷写后补录。
- 真实 C++ 固件仍未消费 `route_policy`（见 `findings.md` U1RP-4）。
