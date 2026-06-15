# 设备绘图/写字模型角色评测 — 2026-06-16

由 `python scripts/eval_device_model_role.py --all --markdown` 生成。

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

## 复现命令


- 全量角色：`python scripts/eval_device_model_role.py --all`
