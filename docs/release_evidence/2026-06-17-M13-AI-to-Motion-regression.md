# AI → Motion 回归证据：热路径拆分与覆盖率提升后

> **日期**：2026-06-17
> **关联里程碑**：M13 AI→Motion 发布门
> **关联路线图**：[`PROJECT_OPTIMIZATION_ROADMAP_CN.md`](../PROJECT_OPTIMIZATION_ROADMAP_CN.md) G1 / G3
> **上一版证据**：[`2026-06-16-M13-AI-to-Motion-release-gate.md`](./2026-06-16-M13-AI-to-Motion-release-gate.md)
> **Git commits**：`7e029e5`、`710d26f`、`a89790d`、`f583784`、`7f4c93b`

## 变更摘要

- 拆分四个生产热路径 oversized 函数：
  - `routing_selector.select` → 21 行
  - `server_lifespan.lifespan` → 8 行
  - `routes/chat_stream.stream_response` → 47 行
  - `device_gateway/device_draw_handler.handle_device_draw` → 45 行
- 删除死代码 `webhook_activity_buffer.py`（109 行）。
- 新增 `tests/test_device_draw_handler.py`（11 cases）和 `tests/test_motion.py`（13 cases）。
- `device_gateway` 聚焦覆盖率从 65.7% 提升至 **71.1%**。

## 回归验证

### 端到端假 U1 闭环

```powershell
python -m pytest tests/test_fake_u1_cloud_loop.py -v
```

结果：

```text
tests/test_fake_u1_cloud_loop.py::test_cloud_to_fake_u1_home_loop PASSED
tests/test_fake_u1_cloud_loop.py::test_cloud_to_fake_u1_write_text_loop PASSED
tests/test_fake_u1_cloud_loop.py::test_cloud_to_fake_u1_draw_generated_svg_loop PASSED
tests/test_fake_u1_cloud_loop.py::test_cloud_task_command_translation_matches_u1_protocol PASSED
4 passed in 4.93s
```

### 设备网关聚焦门

```powershell
python -m pytest tests/test_device_gateway_*.py tests/test_motion.py tests/test_device_draw_handler.py --cov=device_gateway -q
```

结果：**211 passed**，`device_gateway` 覆盖率 **71.1%**。

### 通用门禁

| 检查项 | 结果 |
|--------|------|
| `ruff check .` | clean |
| `pyright`（改动文件） | 0 errors |
| `scripts/check_code_size.py` | 23 个 >300 行文件、99 个 >50 行函数（基线） |

## 结论

热路径拆分与死代码清理未破坏 AI→Motion 端到端链路；设备绘图/写字关键路径新增单元测试覆盖。发布门 B/C/D 保持通过。
