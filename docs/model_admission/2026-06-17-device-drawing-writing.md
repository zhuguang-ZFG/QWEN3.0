# 设备绘图/写字模型准入报告

> 报告日期：2026-06-17
> 评测人 / Agent：Kimi Code CLI
> 关联路线图：阶段 2 — 按角色准入 AI 绘图/写字模型
> 上一版报告：`docs/model_admission/2026-06-12-device-drawing-writing.md`

## 准入标准（全角色通用）

1. 角色 fixture 通过率 ≥ 80%
2. 平均延迟在角色可接受范围内（记录 P50/P95，可选）
3. 无安全性 / 确定性回归
4. 失败模式已记录并有回滚方案
5. 未验证后端不得进入一级通用 chat/coding 池

## 角色总览

| 角色 | 描述 | 优先级 | 当前后端 | 准入状态 |
|------|------|--------|---------|---------|
| Intent Parser | 语音/文字 → 结构化意图 | P0 | deterministic_intent | ✅ 已准入 |
| Text Planner | 写字需求 → 路径规划 | P1 | deterministic_text_render | ✅ 已准入 |
| Prompt Enhancer | 增强绘图提示词 | P2 | 待定 | ⏳ 待实现 |
| Image Generator | 图生（后续矢量化） | P1 | dashscope_wanx | ⚠️ 条件准入 |
| Vectorizer | 图像/提示 → SVG 路径 | P0 | opencv_contour_detect | ✅ 已准入 |
| Vision Analyzer | 输出图像质量分析 | P2 | 待定 | ⏳ 待实现 |
| Recovery Explainer | 故障恢复解释 | P1 | deterministic_error_mapping | ✅ 已准入 |
| Route Policy | 路由角色/backend 契约 | P0 | device_role_preferences | ✅ 已准入 |

## 角色详情

### Intent Parser — ✅ 已准入

**Backend ID:** `deterministic_intent`
**Provider:** LiMa 本地确定性实现
**Model / 实现:** `device_gateway/intent.py`
**Fixture Count:** 35
**Pass Count:** 35
**Pass Rate:** 100%

#### 实现摘要

- 基于关键词与规则将设备语音/文本指令映射为 capability 与参数。
- 不依赖 LLM，避免非确定性解析直接进入运动控制。

#### 失败模式

| 失败类型 | 次数 | 示例 | 影响 |
|---------|------|------|------|
| 无 | 0 | — | — |

#### 准入决策

- **决策:** `admit`
- **理由:** 规则覆盖率高，测试全通过，无 LLM 幻觉风险。
- **回滚方案:** 回退到 `device_unknown` 并返回文本提示。
- **路由偏好:** `device_control`

### Text Planner — ✅ 已准入

**Backend ID:** `deterministic_text_render`
**Provider:** LiMa 本地确定性实现
**Model / 实现:** `device_gateway/path_pipeline.py`
**Fixture Count:** 13
**Pass Count:** 13
**Pass Rate:** 100%

#### 实现摘要

- 将文本内容渲染为笔画路径，供写字任务使用。
- 纯本地计算，不调用外部模型。

#### 失败模式

| 失败类型 | 次数 | 示例 | 影响 |
|---------|------|------|------|
| 无 | 0 | — | — |

#### 准入决策

- **决策:** `admit`
- **理由:** 本地渲染稳定，测试全通过。
- **回滚方案:** 返回 `E_TEXT_RENDER_FAILED` 并停止任务。
- **路由偏好:** `device_write`

### Prompt Enhancer — ⏳ 待实现

**Backend ID:** `pending`
**Provider:** 待定
**Model / 实现:** 未实现
**Fixture Count:** 0
**Pass Count:** 0

#### 准入决策

- **决策:** `defer`
- **理由:** 当前直接使用用户 prompt，无 LLM 增强路径。
- **回滚方案:** 继续使用原始 prompt。

### Image Generator — ⚠️ 条件准入

**Backend ID:** `dashscope_wanx`
**Provider:** 阿里云 DashScope
**Model / 实现:** `dashscope_image_client.py`
**Fixture Count:** 7（离线）
**Pass Count:** 7
**Pass Rate:** 100%

#### 实现摘要

- 调用 DashScope Wanx 模型生成图像，再经矢量化器转为路径。
- 离线 fixture 使用 mock 响应；真实 API 需 `ALIYUN_API_KEY` + `LIMA_DEVICE_ADMISSION_LIVE=1`。

#### 失败模式

| 失败类型 | 次数 | 示例 | 影响 |
|---------|------|------|------|
| 离线 mock 无失败 | 0 | — | — |
| 真实 API 可能失败 | — | 密钥缺失/额度耗尽/内容审核 | 任务降级或阻断 |

#### 准入决策

- **决策:** `admit_conditional`
- **理由:** 离线 fixture 全通过；真实 API 因成本和密钥限制未在默认 CI 中跑。
- **回滚方案:** 降级到预设图形或返回 `E_IMAGE_GENERATION_FAILED`。
- **路由偏好:** `device_draw`

### Vectorizer — ✅ 已准入

**Backend ID:** `opencv_contour_detect`
**Provider:** LiMa 本地 OpenCV 实现
**Model / 实现:** `xiaozhi_drawing/svg_converter.py`
**Fixture Count:** 12
**Pass Count:** 12
**Pass Rate:** 100%

#### 实现摘要

- 使用 OpenCV 轮廓检测将图像转换为 SVG 路径。
- 纯本地计算，无外部依赖。

#### 失败模式

| 失败类型 | 次数 | 示例 | 影响 |
|---------|------|------|------|
| 无 | 0 | — | — |

#### 准入决策

- **决策:** `admit`
- **理由:** 本地算法稳定，测试全通过。
- **回滚方案:** 返回 `E_VECTORIZATION_FAILED`。
- **路由偏好:** `device_vector`

### Vision Analyzer — ⏳ 待实现

**Backend ID:** `pending`
**Provider:** 待定
**Model / 实现:** 未实现
**Fixture Count:** 0
**Pass Count:** 0

#### 准入决策

- **决策:** `defer`
- **理由:** 设备输出图像 QC 尚未实现。
- **回滚方案:** 暂不启用视觉质检门。

### Recovery Explainer — ✅ 已准入

**Backend ID:** `deterministic_error_mapping`
**Provider:** LiMa 本地确定性实现
**Model / 实现:** `device_intelligence/recovery.py`
**Fixture Count:** 33
**Pass Count:** 33
**Pass Rate:** 100%

#### 实现摘要

- 将设备错误码映射为 retry/home/stop 动作及中文解释。
- 重试耗尽后动作固定为 `stop`，避免无限循环。

#### 失败模式

| 失败类型 | 次数 | 示例 | 影响 |
|---------|------|------|------|
| 无 | 0 | — | — |

#### 准入决策

- **决策:** `admit`
- **理由:** 错误码映射完整，测试全通过。
- **回滚方案:** 默认动作 `stop`。

### Route Policy — ✅ 已准入

**Backend ID:** `device_role_preferences`
**Provider:** LiMa 本地确定性实现
**Model / 实现:** `device_gateway/model_routing.py`
**Fixture Count:** 32
**Pass Count:** 32
**Pass Rate:** 100%

#### 实现摘要

- `DEVICE_ROLE_PREFERENCES` 将设备任务映射到准入后端，并填充 `route_policy.backend`。
- 验证器 `validate_route_policy` 拒绝未知 role。

#### 失败模式

| 失败类型 | 次数 | 示例 | 影响 |
|---------|------|------|------|
| 无 | 0 | — | — |

#### 准入决策

- **决策:** `admit`
- **理由:** 角色与 backend 映射清晰，制品证据完整。
- **回滚方案:** 未知 role 返回 `E_INVALID_ROUTE_POLICY`。

## 路由偏好配置

| 角色 route_role | 首选 backend | 备选 backend | 回滚策略 |
|----------------|-------------|-------------|---------|
| device_control | deterministic | — | 错误返回 |
| device_write | deterministic | — | 错误返回 |
| device_draw | dashscope_wanx | dashscope_flux | 预设图形降级 |
| device_vector | opencv_contour | — | 错误返回 |
| device_unknown | deterministic | — | write_text 回退 |

## 准入门控

1. **Gate A — 密钥托管**：DashScope 等密钥仅在 LiMa `.env`，不进入固件/客户端。
2. **Gate B — 功能适配**：角色 fixture 通过率达标（≥ 80%）。
3. **Gate C — 几何安全**：工作区边界、点数上限、simulator 风险评分已覆盖。
4. **Gate D — 路由行为**：`route_policy` 字段与 `validate_route_policy` 一致。

## 可复现评测命令

```powershell
# 全角色评测（推荐）
python scripts/eval_device_model_role.py --all

# 单角色
python scripts/eval_device_model_role.py --role intent_parser

# 生成 Markdown 片段
python scripts/eval_device_model_role.py --all --markdown

# Image Generator 真实 DashScope 图生（需密钥，默认 CI 不跑）
# .env: ALIYUN_API_KEY=sk-...
$env:LIMA_DEVICE_ADMISSION_LIVE = "1"
python scripts/eval_device_model_role.py --role image_generator --live
python -m pytest tests/test_dashscope_image_live.py -v

# 聚焦门
python -m pytest tests/test_device_gateway_model_routing.py -q
python -m pytest tests/test_routing_engine.py -q --tb=short
```

## 维护

- 每个新评测周期复制 `TEMPLATE.md` 并更新日期。
- fixture 或实现变更后重新运行 `eval_device_model_role.py`。
- 关闭切片时同步更新 `STATUS.md` / `progress.md` / `docs/LIMA_MEMORY_CN.md`。
