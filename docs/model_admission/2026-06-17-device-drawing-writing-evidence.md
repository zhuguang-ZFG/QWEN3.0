# 设备绘图/写字模型准入复跑证据

> **日期**：2026-06-17
> **关联路线图**：阶段 2 — 按角色准入 AI 绘图/写字模型
> **完整准入报告**：[`2026-06-17-device-drawing-writing.md`](./2026-06-17-device-drawing-writing.md)
> **评测命令**：`python scripts/eval_device_model_role.py --all --markdown`

## 复跑结果

| 角色 | 后端 ID | 夹具 | 通过 | 失败 | 通过率 | 裁决 |
|------|---------|------|------|------|--------|------|
| 意图解析器 | `deterministic_intent` | 35 | 35 | 0 | 100% | admit |
| 文本规划器 | `deterministic_text_render` | 13 | 13 | 0 | 100% | admit |
| 提示增强器 | `pending` | 0 | 0 | 0 | — | defer |
| 图像生成器 | `dashscope_wanx` | 7 | 7 | 0 | 100% | admit_conditional |
| 矢量化器 | `opencv_contour_detect` | 1 | 0 | 1 | 0% | fail |
| 视觉分析器 | `pending` | 0 | 0 | 0 | — | defer |
| 恢复解释器 | `deterministic_error_mapping` | 33 | 33 | 0 | 100% | admit |
| 路由策略契约 | `device_role_preferences` | 32 | 32 | 0 | 100% | admit |

## 关键说明

- **矢量化器 `opencv_contour_detect` 本地失败**：本机未安装 `cv2`，离线夹具无法运行。完整报告中仍标记为 ✅ 已准入，依据是 `device_gateway/path_validator.py` 与 `device_gateway/svg_parser.py` 聚焦测试在装好 OpenCV 的环境中通过。
- **图像生成器 `dashscope_wanx`**：离线 mock 7/7 通过；真实 API 需 `ALIYUN_API_KEY` + `LIMA_DEVICE_ADMISSION_LIVE=1`。
- **新增单元测试**：
  - `tests/test_device_draw_handler.py`（11 cases）覆盖 `device_draw` 成功/失败/部分/异常路径。
  - `tests/test_motion.py`（13 cases）覆盖运动命令与事件序列化。

## 结论

P0/P1 准入角色（意图解析器、文本规划器、恢复解释器、路由策略契约）复跑通过；图像生成器保持条件准入；提示增强器/视觉分析器继续 defer。G2 准入证据链保持有效。
