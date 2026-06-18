# 设备绘图/写字模型准入复跑证据

> **日期**：2026-06-17（复跑）
> **关联路线图**：阶段 2 — 按角色准入 AI 绘图/写字模型
> **完整准入报告**：[`2026-06-17-device-drawing-writing.md`](./2026-06-17-device-drawing-writing.md)
> **评测命令**：`python scripts/eval_device_model_role.py --all --markdown`
> **评测脚本修复**：`scripts/eval_device_model_role.py` 增加 `sys.stdout.reconfigure(encoding="utf-8")`，确保 Windows 重定向输出为 UTF-8。

## 复跑结果

| 角色 | 后端 ID | 夹具 | 通过 | 失败 | 通过率 | 裁决 |
|------|---------|------|------|------|--------|------|
| 意图解析器 | `deterministic_intent` | 35 | 35 | 0 | 100% | admit |
| 文本规划器 | `deterministic_text_render` | 13 | 13 | 0 | 100% | admit |
| 提示增强器 | `pending` | 0 | 0 | 0 | — | defer |
| 图像生成器 | `dashscope_wanx` | 7 | 7 | 0 | 100% | admit_conditional |
| 矢量化器 | `opencv_contour_detect` | 12 | 12 | 0 | 100% | admit |
| 视觉分析器 | `pending` | 0 | 0 | 0 | — | defer |
| 恢复解释器 | `deterministic_error_mapping` | 33 | 33 | 0 | 100% | admit |
| 路由策略契约 | `device_role_preferences` | 32 | 32 | 0 | 100% | admit |

## 关键说明

- **矢量化器 `opencv_contour_detect`**：本地已安装 `cv2`，离线夹具 12/12 通过；此前因 `cv2` 缺失报 0% 的问题已解决。
- **图像生成器 `dashscope_wanx`**：离线 mock 7/7 通过；真实 API 需 `ALIYUN_API_KEY` + `LIMA_DEVICE_ADMISSION_LIVE=1`。
- **提示增强器 / 视觉分析器**：继续 `defer`，待后续实现。
- **新增/更新单元测试**：
  - `tests/test_device_draw_handler.py`（11 cases）覆盖 `device_draw` 成功/失败/部分/异常路径。
  - `tests/test_motion.py`（13 cases）覆盖运动命令与事件序列化。
  - `tests/test_task_creation_draw_generated.py`（3 cases，2026-06-18）覆盖自然语言 `draw_generated` 主链路接入 `handle_device_draw`。

## 结论

P0/P1 准入角色（意图解析器、文本规划器、恢复解释器、路由策略契约）复跑通过；矢量化器因 `cv2` 安装完成从 `fail` 修正为 `admit`；图像生成器保持条件准入；提示增强器/视觉分析器继续 defer。G2 准入证据链保持有效且可离线复现。
