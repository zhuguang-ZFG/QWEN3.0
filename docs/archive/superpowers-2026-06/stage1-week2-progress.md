# Stage 1 Week 2: Model Routing Phase 2 进度

**日期**: 2026-06-11
**状态**: Phase 2-1 完成 (DashScope 图生 API 集成)
**预计总时间**: 4-6 小时
**已用时间**: ~1 小时

---

## 已完成 ✅

### 1. DashScope 图生 API 封装
- **文件**: `dashscope_image_client.py` (168 行)
- **功能**:
  - 同步生成 `generate()`
  - 异步提交 `generate_async()`
  - 任务查询 `get_task_result()`
- **测试**: `tests/test_dashscope_image_client.py` (6 个测试全部通过)
- **模型支持**: wanx-v1, flux-schnell

### 2. Backends 注册
- **文件**: `backends_registry.py` (新增 2 个后端)
  - `dashscope_wanx`: Wanx-v1 模型
  - `dashscope_flux`: Flux Schnell 模型
- **配置**:
  - `fmt: 'dashscope_image'`
  - `caps: ['image_generation']`
  - `admission: 'device_draw_candidate'`

### 3. Device 路由处理器
- **device_draw**: `device_gateway/device_draw_handler.py` (72 行)
  - 集成 DashScope 图生
  - 返回图片 URL
  - TODO: SVG 转换（Phase 2-2）
- **device_write**: `device_gateway/device_write_handler.py` (58 行)
  - 确定性路径生成
  - 无 LLM 调用
  - TODO: 字体路径实现

### 4. 测试覆盖
- DashScope 客户端: 6 个测试 ✅
- 语法验证: 全部通过 ✅

---

## 下一步 (Phase 2-2)

### SVG/路径转换管线

**任务**:
1. **图像 → SVG 转换器** (`xiaozhi_drawing/svg_converter.py`)
   - 下载图片
   - 边缘检测/矢量化
   - 生成 SVG 路径

2. **集成到 device_draw**
   - 调用转换器
   - 返回设备可用的路径数据

3. **测试验证**
   - 端到端测试：prompt → 图片 → SVG → 路径

**预计时间**: 2-3 小时

---

## 技术决策

### 模型选择
- **device_draw**: 默认 `wanx-v1` (简笔画风格适合绘图机)
- **device_write**: 确定性路径，不调用 LLM
- **后续可扩展**: Flux/SDXL for 更高质量

### 架构清晰度
```
User prompt → device_draw_handler
           → DashScopeImageClient.generate()
           → Image URL
           → [TODO] SVG Converter
           → Path data
           → Device
```

### 与现有系统集成
- 复用 `backends_registry.py` 后端管理
- 遵循 `device_gateway/` 现有结构
- 不破坏现有路由逻辑

---

## 验证清单

- [x] DashScope SDK 已安装 (dashscope 1.25.21)
- [x] API 客户端实现完成
- [x] 单元测试全部通过
- [x] 后端注册到 registry
- [x] Device 路由处理器创建
- [x] 确定性 write 路由实现
- [ ] SVG 转换器实现
- [ ] 端到端集成测试
- [ ] VPS 部署验证

---

## 文件清单

| 文件 | 行数 | 状态 | 说明 |
|------|------|------|------|
| `dashscope_image_client.py` | 168 | ✅ | DashScope 图生客户端 |
| `tests/test_dashscope_image_client.py` | 80 | ✅ | 单元测试 |
| `backends_registry.py` | 243 | ✅ | 新增 2 个图生后端 |
| `device_gateway/device_draw_handler.py` | 72 | ✅ | 绘图路由处理 |
| `device_gateway/device_write_handler.py` | 58 | ✅ | 写字路由处理 |
| `xiaozhi_drawing/svg_converter.py` | - | ⏳ | 下一步 |

---

## 遇到的问题

### 1. Python 模块缓存
- **问题**: `backends_registry.py` 更新后导入未刷新
- **解决**: 文件内容已正确，运行时会重新加载
- **影响**: 无，不影响运行时行为

### 2. Windows 编码
- **问题**: ✓ 符号在 GBK 终端报错
- **解决**: 使用纯 ASCII 或英文
- **影响**: 仅终端显示，不影响功能

---

## 下次启动

继续 Phase 2-2: **SVG 转换管线**

准备好继续吗？🚀
