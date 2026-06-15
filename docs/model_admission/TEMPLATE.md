# 设备绘图/写字模型准入报告模板

> 复制本文件为 `docs/model_admission/YYYY-MM-DD-device-drawing-writing.md` 并填写。
> 评测数据由 `python scripts/eval_device_model_role.py --all --markdown` 生成后合并。

## 元数据

| 字段 | 值 |
|------|-----|
| 报告日期 | YYYY-MM-DD |
| 评测人 / Agent | |
| 关联路线图 | 阶段 2 — 按角色准入 AI 绘图/写字模型 |
| 上一版报告 | `docs/model_admission/2026-06-12-device-drawing-writing.md` |

## 准入标准（全角色通用）

1. 角色 fixture 通过率 ≥ 80%
2. 平均延迟在角色可接受范围内（记录 P50/P95，可选）
3. 无安全性 / 确定性回归
4. 失败模式已记录并有回滚方案
5. 未验证后端不得进入一级通用 chat/coding 池

## 角色总览

| 角色 | 描述 | 优先级 | 当前后端 | 准入状态 |
|------|------|--------|---------|---------|
| Intent Parser | 语音/文字 → 结构化意图 | P0 | deterministic_intent | |
| Text Planner | 写字需求 → 路径规划 | P1 | deterministic_text_render | |
| Prompt Enhancer | 增强绘图提示词 | P2 | 待定 | |
| Image Generator | 图生（后续矢量化） | P1 | dashscope_wanx | |
| Vectorizer | 图像/提示 → SVG 路径 | P0 | opencv_contour_detect | |
| Vision Analyzer | 输出图像质量分析 | P2 | 待定 | |
| Recovery Explainer | 故障恢复解释 | P1 | deterministic_error_mapping | |
| Route Policy | 路由角色/backend 契约 | P0 | device_role_preferences | |

准入状态枚举：`✅ 已准入` / `⚠️ 条件准入` / `⏳ 待实现` / `❌ 拒绝`

## 角色详情（每个角色复制一节）

### {角色英文名} — {准入状态}

**Backend ID:** `{backend_id}`
**Provider:** {提供商}
**Model / 实现:** `{模块路径}`
**Fixture Count:** {N}
**Pass Count:** {N}
**Pass Rate:** {XX%}

#### 实现摘要

- （实现路径、关键依赖、是否 LLM）

#### 失败模式

| 失败类型 | 次数 | 示例 | 影响 |
|---------|------|------|------|
| | | | |

#### 准入决策

- **决策:** `admit` | `admit_conditional` | `defer` | `reject`
- **理由:**
- **回滚方案:**
- **路由偏好:** （对应 `device_gateway/model_routing.py` 中 `DEVICE_ROLE_PREFERENCES`）

## 路由偏好配置

| 角色 route_role | 首选 backend | 备选 backend | 回滚策略 |
|----------------|-------------|-------------|---------|
| device_control | deterministic | — | 错误返回 |
| device_write | deterministic | — | 错误返回 |
| device_draw | dashscope_wanx | dashscope_flux | 预设图形降级 |
| device_vector | opencv_contour | — | 错误返回 |
| device_unknown | deterministic | — | write_text 回退 |

## 准入门控

1. **Gate A — 密钥托管**：DashScope 等密钥仅在 LiMa `.env`，不进入固件/客户端
2. **Gate B — 功能适配**：角色 fixture 通过率达标
3. **Gate C — 几何安全**：工作区边界、点数上限、simulator 风险评分
4. **Gate D — 路由行为**：`route_policy` 字段与 `validate_route_policy` 一致

## 可复现评测命令

```powershell
# 全角色评测（推荐）
python scripts/eval_device_model_role.py --all

# 单角色
python scripts/eval_device_model_role.py --role intent_parser

# 生成 Markdown 片段（粘贴到本报告）
python scripts/eval_device_model_role.py --all --markdown

# 聚焦门（与路线图阶段 2 一致）
python -m pytest tests/test_device_gateway_model_routing.py -q
python -m pytest tests/test_routing_engine.py -q --tb=short
```

## 维护

- 每个新评测周期复制本模板并更新日期
- fixture 或实现变更后重新运行 `eval_device_model_role.py`
- 关闭切片时同步更新 `STATUS.md` / `progress.md`
