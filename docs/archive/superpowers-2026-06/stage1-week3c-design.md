# Stage 1 Week 3C 设计文档：预设图形库

**日期**: 2026-06-11
**Owner**: zhuguang-ZFG
**状态**: 设计中

---

## 一、目标

实现预设图形库，提供常用基础图形的快速 SVG 生成，无需调用 DashScope API。

---

## 二、业务价值

### 2.1 为什么需要预设图形

| 场景 | 问题 | 解决方案 |
|------|------|----------|
| 简单图形 | 调用 DashScope 生成圆形浪费时间和成本 | 本地生成，0 延迟 |
| 网络故障 | DashScope API 不可用时用户无法使用 | 降级到预设图形 |
| 测试/演示 | 开发/演示时频繁调用 API | 本地预设，快速迭代 |
| 教学模式 | 儿童学习基础图形 | 预设形状库 |

### 2.2 用户体验提升

- ⚡ 响应时间: 从 3-5 秒 → <100ms
- 💰 成本节省: 基础图形 0 API 调用
- 🛡️ 可靠性: 离线可用

---

## 三、技术方案

### 3.1 预设图形清单（MVP）

**基础形状 (6 个)**:
- 圆形 (circle)
- 正方形 (square)
- 三角形 (triangle)
- 五角星 (star)
- 心形 (heart)
- 月亮 (crescent)

**扩展形状 (4 个，Phase 2)**:
- 花朵 (flower)
- 房子 (house)
- 树 (tree)
- 太阳 (sun)

### 3.2 接口设计

```python
def get_preset_svg(
    shape: str,
    size: int = 180
) -> Dict[str, Any]:
    """
    获取预设图形的 SVG 路径

    Args:
        shape: 图形名称 (circle/square/triangle/star/heart/crescent)
        size: 目标尺寸（工作区适配）

    Returns:
        {
            'status': 'success' | 'failed',
            'svg_path': str,
            'width': int,
            'height': int,
            'shape': str,
            'error': str | None
        }
    """
```

### 3.3 路由集成

修改 `device_draw_handler.py`，增加预设图形检测：

```python
# 检测预设图形关键词
PRESET_KEYWORDS = {
    'circle': ['圆', '圆形', 'circle'],
    'square': ['方', '方形', '正方形', 'square'],
    'triangle': ['三角', '三角形', 'triangle'],
    'star': ['星', '星星', '五角星', 'star'],
    'heart': ['心', '心形', 'heart', '爱心'],
    'crescent': ['月', '月亮', '月牙', 'crescent']
}

async def handle_device_draw(prompt: str, ...):
    # 1. 检测预设图形
    for shape, keywords in PRESET_KEYWORDS.items():
        if any(kw in prompt for kw in keywords):
            result = get_preset_svg(shape)
            # 跳过 DashScope API
            return result

    # 2. 正常 DashScope 流程
    ...
```

---

## 四、实现细节

### 4.1 SVG 路径定义

**圆形** (最简单):
```python
def _circle_path(cx: int, cy: int, r: int) -> str:
    # 使用 4 段贝塞尔曲线近似圆
    return f"M {cx} {cy-r} A {r} {r} 0 1 1 {cx} {cy+r} A {r} {r} 0 1 1 {cx} {cy-r} Z"
```

**五角星** (数学计算):
```python
def _star_path(cx: int, cy: int, outer_r: int) -> str:
    inner_r = outer_r * 0.382  # 黄金比例
    points = []
    for i in range(10):
        angle = math.pi / 2 - (2 * math.pi * i / 10)
        r = outer_r if i % 2 == 0 else inner_r
        x = cx + r * math.cos(angle)
        y = cy - r * math.sin(angle)
        points.append((x, y))
    path = f"M {points[0][0]} {points[0][1]}"
    for x, y in points[1:]:
        path += f" L {x} {y}"
    return path + " Z"
```

### 4.2 尺寸适配

所有图形居中在 `size x size` 工作区：
- 计算图形内接于 `size * 0.9` 圆（留边距）
- 中心点 `(size/2, size/2)`

---

## 五、测试策略

### 5.1 单元测试 (6-8 个)

- ✅ 每种预设图形可生成
- ✅ 返回格式正确
- ✅ SVG 路径有效（M/L/A/Z）
- ✅ 尺寸适配正确
- ❌ 未知图形返回错误

### 5.2 集成测试

- ✅ device_draw 检测预设关键词
- ✅ 跳过 DashScope API 调用
- ✅ 响应时间 <100ms

---

## 六、模块结构

```
xiaozhi_drawing/
├── svg_validator.py       (Week 3A)
├── path_optimizer.py      (Week 3A)
├── svg_converter.py       (Week 3B)
└── preset_shapes.py       (新增, 80-100 行)

device_gateway/
└── device_draw_handler.py (修改, +20 行)
```

---

## 七、实现顺序

1. **Phase 1**: 预设图形库
   - 实现 `preset_shapes.py`（80 行）
   - 6 个基础图形
   - 单元测试（6 个）

2. **Phase 2**: 路由集成
   - 修改 `device_draw_handler.py`（+20 行）
   - 关键词检测逻辑
   - 集成测试（2 个）

3. **Phase 3**: VPS 部署
   - 部署新模块
   - 端到端验证

---

## 八、质量目标

| 指标 | 目标 |
|------|------|
| 响应时间 | <100ms |
| 测试覆盖率 | ≥90% |
| 文件规模 | <100 行 |
| Ruff 检查 | Clean |

---

## 九、下一步

- [ ] 实现 `preset_shapes.py`
- [ ] 编写单元测试
- [ ] 集成到 device_draw
- [ ] VPS 部署验证
