# 设备绘图/写字模型准入报告 — 阶段 1-5

> 本文件为 `docs/model_admission/TEMPLATE.md` 在阶段 1-5 的实例化产物，
> 也是 `tests/device_gateway_profile/test_device_gateway_profile_release_gates.py`
> 断言其存在的准入报告。后续评测周期请复制新日期文件并刷新下表。

## 元数据

| 字段 | 值 |
|------|-----|
| 报告日期 | 2026-06-12 |
| 评测人 / Agent | lima-agent |
| 关联路线图 | 阶段 2 — 按角色准入 AI 绘图/写字模型 |
| 关联发布证据 | [`docs/release_evidence/2026-06-12-phase1-5-complete.md`](../release_evidence/2026-06-12-phase1-5-complete.md) |

## 角色总览

| 角色 | 描述 | 当前后端 | 准入状态 |
|------|------|---------|---------|
| Intent Parser | 语音/文字 → 结构化意图 | deterministic_intent | ✅ 已准入 |
| Image Generator | 图生（后续矢量化） | dashscope_wanx | ✅ 已准入 |
| Vectorizer | 图像/提示 → SVG 路径 | opencv_contour_detect | ✅ 已准入 |

## 角色详情

### Intent Parser — ✅ 已准入

**Backend ID:** `deterministic_intent`
**实现:** `device_gateway/intent.py`（无 LLM，正则 + 关键词路由）

- 语音/文字 → capability（write_text / draw_generated / home …）的确定性映射。
- 失败模式：无法解析时回退到 `device_unknown` 路由，由后续门处理。

#### 准入决策

- **决策:** `admit`
- **理由:** 纯确定性、可复现、fixture 通过率达标。
- **回滚方案:** 回退到上一版 intent.py。

### Image Generator — ✅ 已准入

**Backend ID:** `dashscope_wanx`
**实现:** `device_gateway/dashscope_image_client.py`（DashScope wanx2.1-t2i-turbo）

- 接收 prompt 生成图像，供下游 Vectorizer 转 SVG。
- 密钥仅在 LiMa `.env`（门 A — 密钥托管）。

#### 准入决策

- **决策:** `admit`
- **理由:** 延迟与稳定性满足绘图角色；真实 DashScope live 测试需密钥，CI 默认不跑。
- **回滚方案:** 切换到备选 backend `dashscope_flux`，或预设图形降级。

### Vectorizer — ✅ 已准入

**Backend ID:** `opencv_contour_detect`
**实现:** `xiaozhi_drawing/svg_converter.py`（OpenCV 骨架化 + 轮廓追踪）

- 图像 → SVG polyline → motion path（经 `render_svg_task` 归一化进工作区）。
- 几何安全由 path_validator + simulator 门控（门 C）。

#### 准入决策

- **决策:** `admit`
- **理由:** 纯本地 CV，无外部依赖；输出经几何/点数校验后下发。
- **回滚方案:** 回退到上一版 svg_converter。

## 准入门控

1. **Gate A — 密钥托管**：DashScope 密钥仅在 `.env`，不入固件/客户端。
2. **Gate B — 功能适配**：角色 fixture 通过率达标。
3. **Gate C — 几何安全**：工作区边界、点数上限、simulator 风险评分。
4. **Gate D — 路由行为**：`route_policy` 字段与 `validate_route_policy` 一致。

## 可复现评测

```powershell
python scripts/eval_device_model_role.py --all
python -m pytest tests/test_device_gateway_model_routing.py -q
```
