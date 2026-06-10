# Device Drawing/Writing Model Admission Report

> 日期: 2026-06-11
> 范围: AI 绘图/写字机的模型角色准入评估
> 状态: Scaffold — 等待实际评测数据填充

## 概述

本报告记录 AI 绘图/写字机各模型角色的准入决策。每个角色独立评估，
基于固定 fixture 集合和可复现的评测命令。

准入标准：
- 角色 fixture 通过率 ≥ 80%
- 平均延迟在角色可接受范围内
- 无安全性/确定性回归
- 失败模式已记录并有回滚方案

## 角色分类

| 角色 | 描述 | 优先级 | 状态 |
|------|------|--------|------|
| Intent Parser | 解析用户语音/文字命令为结构化意图 | P0 | 待评测 |
| Text Planner | 将写作需求转化为路径规划 | P1 | 待评测 |
| Prompt Enhancer | 增强绘图提示词质量 | P2 | 待评测 |
| Image Generator | 生成图像（用于后续矢量化） | P1 | 待评测 |
| Vectorizer | 将图像/提示转为 SVG 路径 | P0 | 待评测 |
| Vision Analyzer | 分析设备输出图像质量 | P2 | 待评测 |
| Recovery Explainer | 故障恢复解释和建议 | P1 | 待评测 |

## 准入评测模板

每个角色使用以下模板记录评测结果：

### [角色名称] 准入评测

**Backend ID:** `[provider]_[model_id]`
**Provider:** `[provider]`
**Model:** `[model_id]`
**Fixture Count:** `[N]`
**Pass Count:** `[M]`
**Pass Rate:** `[M/N]`
**Average Latency:** `[ms]`

#### Fixture 结果

| # | Fixture 名称 | 输入 | 期望输出 | 实际输出 | 通过 | 延迟(ms) |
|---|-------------|------|---------|---------|------|---------|
| 1 | | | | | | |
| 2 | | | | | | |

#### 失败模式

| 失败类型 | 次数 | 示例 | 影响 |
|---------|------|------|------|
| | | | |

#### 准入决策

- **决策:** `[admit / reject / conditional]`
- **理由:** `[说明]`
- **回滚方案:** `[说明]`
- **路由偏好:** `[说明在路由表中的位置]`

## 当前状态

### Intent Parser（命令解析）

当前实现：确定性解析器 `device_gateway/intent.py`
- 使用正则模式匹配，无 LLM 依赖
- 覆盖率：control(5) + write(2) + draw(2) + path(2) + move(2) = 13 模式
- 低置信度回退：`write_text` + 显式解释
- LLM 重规划门控：`LIMA_DEVICE_LLM_PLANNER=1`（默认关闭）

**决策：无需额外模型准入，确定性解析已满足需求。**

### Vectorizer（SVG 路径生成）

当前实现：`device_gateway/path_pipeline.py`
- `render_svg_task()`: SVG path 直传
- `render_text_task()`: 文字转简单路径

待评测：
- [ ] 直接 LLM 生成 SVG（实验性，需 geometry fixture 验证）
- [ ] 图像→矢量转换后端

**决策：暂不开放 LLM 直出 SVG，保持确定性路径渲染。**

## 评测命令

```powershell
# 运行设备路由测试
python -m pytest tests/test_device_gateway_model_routing.py -v

# 运行设备 profile 测试
python -m pytest tests/test_device_gateway_profiles.py -v

# 运行设备网关完整测试
python -m pytest tests/test_device_gateway_routes.py tests/test_device_gateway_protocol.py tests/test_p1_4_device_stability_gate.py -q

# 运行路由引擎测试
python -m pytest tests/test_routing_engine.py -q --tb=short
```

## 准入标准

### 进入热路由的条件

1. 角色 fixture 通过率 ≥ 80%
2. 有日期标记的评测证据
3. 证据链接在 `docs/FREE_MODEL_ROUTING_STATUS.md` 或本报告
4. 回滚方案已验证
5. 不将未验证 provider 放入通用 chat/coding 路由池

### 禁止准入的情况

- 直接 LLM 生成 SVG 且无 geometry fixture 验证
- 无日期标记的评测结果
- 评测无法复现
- 安全性回归（如生成危险路径坐标）

## 维护

- 每个新评测周期更新本报告
- 评测脚本或 fixture 变更时重新运行
- 保留历史评测数据用于趋势分析
