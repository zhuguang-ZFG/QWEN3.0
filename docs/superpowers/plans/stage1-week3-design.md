# Stage 1 Week 3A 设计文档：SVG 验证与路径优化

**日期**: 2026-06-11
**Owner**: zhuguang-ZFG
**状态**: 设计中

---

## 一、目标

实现 SVG 验证器和路径优化器，为绘图机提供可靠的路径处理能力。

---

## 二、技术方案

### 2.1 SVG 验证器 (`xiaozhi_drawing/svg_validator.py`)

**职责**:
- 解析 SVG path 字符串（支持 M/L/C/Q/Z 指令）
- 验证坐标范围（设备工作区限制）
- 计算路径复杂度（点数、笔画数）
- 提取绘制指令序列

**接口**:
```python
@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]
    complexity: dict  # {point_count, stroke_count, bbox}

def validate_svg_path(
    path_data: str,
    workspace: tuple[float, float] = (200, 200)
) -> ValidationResult:
    """验证 SVG 路径"""
```

**验证规则**:
1. 路径不为空
2. 指令格式合法（M/L/C/Q/Z + 坐标）
3. 坐标在工作区内
4. 复杂度不超限（<5000 点）

**依赖**: `svgpathtools`（已在 requirements_server.txt）

---

### 2.2 路径优化器 (`xiaozhi_drawing/path_optimizer.py`)

**职责**:
- 路径简化（Douglas-Peucker 算法）
- 笔画顺序优化（最短路径问题）
- 工作区适配（缩放 + 居中）

**接口**:
```python
@dataclass
class OptimizationResult:
    optimized_path: str
    original_points: int
    optimized_points: int
    reduction_ratio: float

def optimize_svg_path(
    path_data: str,
    tolerance: float = 2.0,
    target_size: tuple[float, float] = (180, 180)
) -> OptimizationResult:
    """优化 SVG 路径"""
```

**优化策略**:
1. **简化**: Douglas-Peucker 算法，`tolerance=2.0`（2mm 误差可接受）
2. **缩放**: 保持宽高比，适配目标尺寸
3. **居中**: 计算 bbox 后偏移至中心
4. **笔顺**: 贪心算法（起点→最近未绘制笔画）

**依赖**: `shapely`（几何计算）

---

## 三、模块结构

```
xiaozhi_drawing/
├── __init__.py
├── svg_converter.py       (已完成，Week 2)
├── svg_validator.py       (新增，80-100 行)
└── path_optimizer.py      (新增，120-150 行)
```

---

## 四、测试策略

### 4.1 SVG 验证器测试

**测试用例** (8-10 个):
- ✅ 有效路径（M L Z）
- ❌ 空路径
- ❌ 非法指令
- ❌ 坐标超出工作区
- ❌ 复杂度超限
- ⚠️ 警告：路径过长但未超限

### 4.2 路径优化器测试

**测试用例** (8-10 个):
- ✅ 简化高密度路径
- ✅ 缩放过大路径
- ✅ 居中偏移路径
- ✅ 优化前后相似度 >95%
- ✅ 点数减少 >30%

---

## 五、实现顺序

1. **Phase 1**: SVG 验证器
   - 实现 `svg_validator.py`（80 行）
   - 单元测试（8 个）
   - 本地验证

2. **Phase 2**: 路径优化器
   - 实现 `path_optimizer.py`（120 行）
   - 单元测试（8 个）
   - 本地验证

3. **Phase 3**: 集成到 device_draw
   - 修改 `device_draw_handler.py`
   - 在 SVG 转换后添加验证+优化步骤
   - 端到端测试

4. **Phase 4**: VPS 部署
   - 部署新模块
   - 安装依赖 (svgpathtools, shapely)
   - 健康检查

---

## 六、质量目标

| 指标 | 目标 |
|------|------|
| 测试覆盖率 | ≥90% |
| 函数复杂度 | <50 行 |
| 文件规模 | <200 行 |
| Ruff 检查 | Clean |
| 优化效果 | 点数减少 30%+，相似度 >95% |

---

## 七、风险与缓解

| 风险 | 缓解 |
|------|------|
| shapely 编译失败（VPS） | 提供 wheel 或使用纯 Python 实现 |
| 路径优化质量不足 | 调参 tolerance，提供多档位 |
| 复杂路径性能问题 | 限制点数上限（5000），超限拒绝 |

---

## 八、下一步

- [ ] 实现 `svg_validator.py`
- [ ] 编写验证器测试
- [ ] 实现 `path_optimizer.py`
- [ ] 编写优化器测试
- [ ] 集成到 device_draw
- [ ] VPS 部署验证
