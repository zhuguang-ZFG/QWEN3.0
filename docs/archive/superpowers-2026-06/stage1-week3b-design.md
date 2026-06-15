# Stage 1 Week 3B 设计文档：真实矢量化

**日期**: 2026-06-11
**Owner**: zhuguang-ZFG
**状态**: 设计中

---

## 一、目标

替换 SVG 转换器占位符实现，将位图图像转换为真实可绘制的矢量路径。

---

## 二、技术方案选型

### 2.1 方案对比

| 方案 | 原理 | 优点 | 缺点 | 可行性 |
|------|------|------|------|--------|
| **Potrace** | 位图描边算法 | 质量高，专业工具 | C 扩展，VPS 编译难 | ⚠️ 中 |
| **OpenCV** | 轮廓检测 | 纯 Python，易部署 | 需调参，质量中等 | ✅ 高 |
| **PIL + 简化** | 边缘检测 + 简化 | 依赖少，轻量 | 质量较低 | ✅ 高 |

### 2.2 推荐方案：OpenCV 轮廓检测

**选择原因**:
1. ✅ 纯 Python wheel，VPS 易安装
2. ✅ 已在 requirements_server.txt（opencv-python）
3. ✅ 质量适中，满足绘图机需求
4. ⚠️ Potrace 需编译，之前失败过

---

## 三、实现策略

### 3.1 OpenCV 矢量化流程

```
下载图片 (HTTP)
    ↓
PIL 加载 + 灰度化
    ↓
OpenCV 二值化 (Otsu)
    ↓
轮廓检测 (findContours)
    ↓
轮廓简化 (approxPolyDP)
    ↓
转换为 SVG path (M/L/Z)
```

### 3.2 接口设计

```python
async def convert_url_to_svg(
    image_url: str,
    simplify_epsilon: float = 2.0,
    min_contour_area: int = 100
) -> Dict[str, Any]:
    """
    将图片 URL 转换为 SVG 路径

    Args:
        image_url: 图片 URL
        simplify_epsilon: 轮廓简化精度 (像素)
        min_contour_area: 最小轮廓面积 (过滤噪点)

    Returns:
        {
            'status': 'success' | 'failed',
            'svg_path': str,
            'width': int,
            'height': int,
            'contour_count': int,
            'error': str | None
        }
    """
```

---

## 四、实现细节

### 4.1 二值化策略

- **方法**: Otsu 自动阈值
- **预处理**: 高斯模糊去噪 (kernel=5)
- **反转**: 白色背景 → 黑色轮廓

### 4.2 轮廓简化

- **算法**: Douglas-Peucker (`approxPolyDP`)
- **精度**: `epsilon = 0.01 * perimeter` (1% 周长)
- **过滤**: 面积 < 100 的小轮廓丢弃

### 4.3 SVG 路径生成

- **格式**: `M x y L x y ... Z` (闭合路径)
- **坐标**: OpenCV 坐标系 (左上原点)
- **多轮廓**: 每个轮廓独立 M...Z

---

## 五、测试策略

### 5.1 单元测试 (8-10 个)

- ✅ 简单图形 (圆、方)
- ✅ 复杂图像 (真实照片)
- ❌ 空白图片
- ❌ 无效 URL
- ✅ 多轮廓处理
- ✅ 轮廓简化效果

### 5.2 视觉验证

- 生成测试图片 → SVG
- 用浏览器渲染 SVG
- 对比原图相似度

---

## 六、依赖管理

### 6.1 本地安装

```bash
pip install opencv-python==4.10.0.84
```

### 6.2 VPS 部署

- ✅ opencv-python 有 wheel (manylinux)
- ⚠️ 可能需要 libGL (已有，VPS 系统库)

---

## 七、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| OpenCV 依赖大 (50MB+) | 部署慢 | 后台安装，不阻塞开发 |
| 彩色图像轮廓不清晰 | 质量差 | 灰度化 + Otsu 自动阈值 |
| 复杂图像轮廓过多 | 点数爆炸 | 简化 + 面积过滤 + max_points 限制 |
| VPS libGL 缺失 | 导入失败 | 使用 opencv-python-headless |

---

## 八、实现顺序

1. **Phase 1**: 核心算法实现
   - 实现新的 `svg_converter.py` (80-100 行)
   - 本地测试（Mock 图片）

2. **Phase 2**: 单元测试
   - 8-10 个测试用例
   - 覆盖正常/异常场景

3. **Phase 3**: VPS 部署
   - 安装 opencv-python-headless
   - 替换旧的占位符实现
   - 端到端验证

4. **Phase 4**: 集成验证
   - device_draw 完整流程测试
   - 真实 DashScope 图片转换

---

## 九、质量目标

| 指标 | 目标 |
|------|------|
| 测试覆盖率 | ≥90% |
| 函数复杂度 | <50 行 |
| 文件规模 | <150 行 |
| Ruff 检查 | Clean |
| 轮廓质量 | 可视化相似度 >80% |

---

## 十、下一步

- [ ] 实现 OpenCV 矢量化
- [ ] 编写单元测试
- [ ] 本地验证
- [ ] VPS 部署
- [ ] 真实图片测试
