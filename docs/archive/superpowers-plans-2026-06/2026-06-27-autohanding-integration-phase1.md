# autohanding.com 仿手写集成 Phase 1 执行计划

## 背景

将 https://www.autohanding.com/ 的免费仿手写预览能力接入 LiMa，供写字机/绘图机设备使用。autohanding 返回位图 PNG（ZIP 包），LiMa 需要把位图转成 SVG path，再复用现有 `device_gateway` 的 SVG 渲染链路驱动电机。

Phase 0 已完成：
- `integrations/autohanding/client.py` + `constants.py`
- `scripts/verify_autohanding_preview.py` 本地验证返回 675KB 有效 PNG。

## Phase 1 目标

完成 LiMa 后端路由接入、`task_draw_params.py` 集成，并通过代码体积检查与基础测试。

## 任务清单

### Task 1 — 修复代码体积违规

- 拆分 `integrations/autohanding/client.py::convert_text`：
  - `_build_request(text, client_id, ...)` 构建 form + headers。
  - `_post_preview(client, url, form, headers)` 执行 POST 并处理网络异常。
  - `_handle_response(response)` 处理状态码 / 限流 / ZIP 提取。
  - `convert_text` 本身只做参数校验与编排。
- 拆分 `routes/handwriting.py::device_app_handwriting`：
  - `_parse_handwriting_request(body)` 参数解析与校验。
  - `_generate_handwriting_svg(text, params)` 调用 autohanding + SVGConverter。
  - `device_app_handwriting` 只做鉴权、调用、返回 JSON。
- 精简/拆分 `xiaozhi_drawing/svg_converter.py`：
  - 已完成 docstring 精简；若仍 >300 行，将 `convert_url_to_svg` / `convert_bytes_to_svg` 的公共参数打包为内部 dataclass，或把 `_convert_image_bytes` 进一步拆分。
- 验证：`python scripts/check_code_size.py` 0 违规。

### Task 2 — 接入 `task_draw_params.py` 与设备渲染链路

- 在 `device_gateway/task_draw_params.py` 新增 `build_handwriting_params(text: str, svg_path: str, **options) -> dict`：
  - 生成与现有 `draw` task 兼容的 params（`svg_path`、`stroke_width`、`bounds`、`duration_ms` 等）。
- 修改 `routes/handwriting.py`：
  - 支持两种返回模式：
    - `mode=svg`（默认）：直接返回 SVG path，供小程序/上层预览。
    - `mode=task`：直接返回可下发给设备的 `draw` task JSON（调用 `build_handwriting_params`）。
- 验证 `handle_device_draw` 与 `render_svg_task` 能消费生成的 SVG path；必要时加 `viewBox` 标准化。

### Task 3 — 测试与质量门禁

- 新增 `tests/test_autohanding_client.py`：
  - mock httpx 返回 ZIP（含 PNG），验证 `convert_text` 返回 PNG bytes。
  - mock 429 / 非 ZIP 200，验证异常类型。
- 新增 `tests/test_handwriting_route.py`：
  - mock `autohanding_client.convert_text` 与 `SVGConverter.convert_bytes_to_svg`，验证 `/device/v1/app/handwriting` 200 返回。
  - 验证 `mode=task` 时返回 task params 且含 `svg_path`。
- 运行：
  - `python -m pytest tests/test_autohanding_client.py tests/test_handwriting_route.py -v`
  - `ruff check .`
  - `ruff format --check .`
  - `pyright integrations/autohanding/client.py routes/handwriting.py xiaozhi_drawing/svg_converter.py`
  - `python scripts/check_code_size.py`

### Task 4 — VPS 部署与冒烟验证

- 执行 `python scripts/deploy_unified.py --slice core`。
- 部署后：
  - `curl -sf https://chat.donglicao.com/health`
  - 带真实 token 调一次 `/device/v1/app/handwriting` 返回 SVG path。
- 更新 `progress.md` 与 `findings.md`。

## 退出标准

- `check_code_size.py` PASS。
- 新增测试全部通过。
- 本地服务 `/device/v1/app/handwriting` 返回可解析的 SVG path。
- VPS 部署成功且健康检查通过。
