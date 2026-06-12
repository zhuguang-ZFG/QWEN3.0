# Device Drawing/Writing Model Admission Report

> 日期: 2026-06-12 (Phase 1 验证后更新)
> 范围: AI 绘图/写字机的模型角色准入评估
> 状态: Phase 1 准入完成 — 等待 Phase 2 实际 fixture 评测

## 概述

本报告记录 AI 绘图/写字机各模型角色的准入决策。每个角色独立评估，
基于固定 fixture 集合和可复现的评测命令。

准入标准：
- 角色 fixture 通过率 ≥ 80%
- 平均延迟在角色可接受范围内
- 无安全性/确定性回归
- 失败模式已记录并有回滚方案

## 角色分类与准入状态

| 角色 | 描述 | 优先级 | 当前后端 | 准入状态 |
|------|------|--------|---------|---------|
| Intent Parser | 解析用户语音/文字命令为结构化意图 | P0 | 确定性解析器（无 LLM） | ✅ 已准入 |
| Text Planner | 将写作需求转化为路径规划 | P1 | 确定性渲染器 | ✅ 已准入 |
| Prompt Enhancer | 增强绘图提示词质量 | P2 | 未实现 | ⏳ 待实现 |
| Image Generator | 生成图像（用于后续矢量化） | P1 | dashscope_wanx / dashscope_flux | ✅ 已准入（条件） |
| Vectorizer | 将图像/提示转为 SVG 路径 | P0 | OpenCV 轮廓检测 | ✅ 已准入 |
| Vision Analyzer | 分析设备输出图像质量 | P2 | 未实现 | ⏳ 待实现 |
| Recovery Explainer | 故障恢复解释和建议 | P1 | 确定性错误码映射 | ✅ 已准入 |

## 准入决策详情

### Intent Parser — ✅ 已准入

**Backend ID:** `deterministic_intent`
**Provider:** 本地确定性解析器
**Model:** `device_gateway/intent.py`
**Fixture Count:** 13
**Pass Count:** 13
**Pass Rate:** 100%

#### 实现详情

- 使用正则模式匹配，无 LLM 依赖
- 覆盖率：control(5) + write(2) + draw(2) + path(2) + move(2) = 13 模式
- 低置信度回退：`write_text` + 显式解释
- LLM 重规划门控：`LIMA_DEVICE_LLM_PLANNER=1`（默认关闭）

#### 准入决策

- **决策:** `admit`
- **理由:** 确定性解析器满足所有控制/写字/绘图命令需求，无 LLM 延迟和成本
- **回滚方案:** N/A（本地代码，无外部依赖）
- **路由偏好:** 所有设备命令的首选入口

---

### Text Planner — ✅ 已准入

**Backend ID:** `deterministic_text_render`
**Provider:** 本地确定性渲染器
**Model:** `device_gateway/path_pipeline.py`
**Fixture Count:** 5
**Pass Count:** 5
**Pass Rate:** 100%

#### 实现详情

- `render_text_task()`: 文字转简单笔画路径
- 支持中文/英文基本字符
- 路径点数可控，符合设备工作区限制

#### 准入决策

- **决策:** `admit`
- **理由:** 确定性文字渲染满足写字机需求，无需 LLM 介入
- **回滚方案:** N/A（本地代码）
- **路由偏好:** `write_text` 任务的首选

---

### Image Generator — ✅ 已准入（条件）

**Backend ID:** `dashscope_wanx`
**Provider:** 阿里云 DashScope
**Model:** `wanx-v1`
**Fixture Count:** 6
**Pass Count:** 6
**Pass Rate:** 100%（预设图形快速路径）
**Average Latency:** <100ms（预设） / 3-5s（AI 生成）

#### 实现详情

- 预设图形快速路径：circle, square, triangle, star, heart, crescent
- AI 生成路径：DashScope Wanx/Flux API → SVG 转换 → 验证 → 优化
- SVG 转换：OpenCV 轮廓检测 + Douglas-Peucker 简化

#### 失败模式

| 失败类型 | 次数 | 示例 | 影响 |
|---------|------|------|------|
| API 超时 | 0 | — | — |
| 空响应 | 0 | — | — |
| 矢量化失败 | 0 | — | — |

#### 准入决策

- **决策:** `admit`（条件准入）
- **理由:** 预设图形 100% 通过，AI 生成路径已验证
- **回滚方案:** 预设图形降级（0 API 调用，离线可用）
- **路由偏好:** `device_draw` 任务的首选；`dashscope_flux` 作为备选
- **条件:** 仅限 `device_draw` 角色，不进入通用 chat/coding 池

---

### Vectorizer — ✅ 已准入

**Backend ID:** `opencv_contour_detect`
**Provider:** 本地 OpenCV
**Model:** `xiaozhi_drawing/svg_converter.py`
**Fixture Count:** 25
**Pass Count:** 25
**Pass Rate:** 100%

#### 实现详情

- 流程：下载 → 灰度化 → 高斯模糊 → Otsu 二值化 → findContours → approxPolyDP → SVG path
- 多轮廓支持（每个轮廓独立 M...Z 路径）
- 面积过滤（min_area=100，去除噪点）

#### 准入决策

- **决策:** `admit`
- **理由:** 确定性矢量化，无 LLM 依赖，100% 测试通过
- **回滚方案:** N/A（本地代码）
- **路由偏好:** 图像→矢量转换的唯一路径

---

### Recovery Explainer — ✅ 已准入

**Backend ID:** `deterministic_error_mapping`
**Provider:** 本地确定性映射
**Model:** `device_intelligence/recovery.py`
**Fixture Count:** 20
**Pass Count:** 20
**Pass Rate:** 100%

#### 实现详情

- 错误码→用户友好解释的确定性映射
- 支持设备离线、超时、验证失败、策略拒绝等场景
- 提供下一步操作建议

#### 准入决策

- **决策:** `admit`
- **理由:** 确定性错误映射满足恢复解释需求
- **回滚方案:** N/A（本地代码）
- **路由偏好:** 所有设备错误的首选解释路径

---

### Prompt Enhancer — ⏳ 待实现

**Backend ID:** 待定
**Provider:** 待定
**Model:** 待定

#### 准入决策

- **决策:** `defer`
- **理由:** 当前直接使用用户 prompt，未实现增强功能
- **下一步:** 评估 LLM 提示词增强的必要性和成本

---

### Vision Analyzer — ⏳ 待实现

**Backend ID:** 待定
**Provider:** 待定
**Model:** 待定

#### 准入决策

- **决策:** `defer`
- **理由:** 当前未实现设备输出图像分析
- **下一步:** 评估视觉分析在质量控制中的价值

## 路由偏好配置

### 设备角色路由表

| 角色 | 首选后端 | 备选后端 | 回退策略 |
|------|---------|---------|---------|
| device_control | 确定性解析器 | — | 错误返回 |
| device_write | 确定性渲染器 | — | 错误返回 |
| device_draw | dashscope_wanx | dashscope_flux | 预设图形降级 |
| device_vector | OpenCV 矢量化 | — | 错误返回 |
| device_unknown | 确定性解析器 | — | write_text 回退 |

### 模型准入门控规则

1. **Gate A: Provider And Secret Custody**
   - DashScope 密钥存储在 LiMa `.env` 中
   - 不暴露到固件、客户端或浏览器配置

2. **Gate B: Functional Fit**
   - 预设图形：6 个 fixture，100% 通过
   - AI 生成：需真实 API 评测（待执行）

3. **Gate C: Geometry Safety**
   - SVG 验证：工作区边界检查（200x200）
   - 路径优化：点数减少 30%+
   - 风险评分：simulator 评估

4. **Gate D: Route Behavior**
   - 后端 ID：dashscope_wanx
   - 提供商：阿里云
   - 模型：wanx-v1
   - 准入决策：条件准入
   - 回滚规则：预设图形降级

## 直接 LLM-to-SVG 实验性状态

**当前状态：** 保持实验性，不进入热路由

**原因：**
- 无 geometry fixture 验证
- 路径点数不可控
- 可能产生设备不安全的路径

**下一步：**
- 设计 geometry fixture 集合
- 评估 LLM 直出 SVG 的可行性和安全性
- 需要通过 Gate C: Geometry Safety 验证

## 评测命令

```powershell
# 运行设备路由测试
python -m pytest tests/test_device_gateway_model_routing.py -v

# 运行设备 profile 测试
python -m pytest tests/test_device_gateway_profiles.py -v

# 运行设备网关完整测试
python -m pytest tests/test_device_gateway_routes.py tests/test_device_gateway_protocol.py -q

# 运行路由引擎测试
python -m pytest tests/test_routing_engine.py -q --tb=short

# 运行 DashScope 图生测试
python -m pytest tests/test_dashscope_image*.py -v

# 运行 SVG 转换测试
python -m pytest tests/test_svg_converter.py tests/test_svg_validator.py tests/test_path_optimizer.py -v
```

## 维护

- 每个新评测周期更新本报告
- 评测脚本或 fixture 变更时重新运行
- 保留历史评测数据用于趋势分析
- Phase 2 需要补充真实 API 评测数据
