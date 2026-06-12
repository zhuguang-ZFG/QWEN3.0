# LiMa Task Prompt Contract v0.1

> 日期: 2026-06-13
> 范围: LiMa 项目任务编写标准
> 状态: 初版

## 概述

本文档定义了 LiMa 项目的任务编写标准，基于 KERNEL 模式。任务是项目执行的基本单元，每个任务都必须遵循此契约以确保可验证性、可追踪性和可执行性。

## 设计原则

1. **简单单一目标**：每个任务只做一件事
2. **可验证成功标准**：成功标准必须具体、可测试
3. **避免时间敏感**：除非有具体日期/来源，否则不使用时间敏感的措辞
4. **窄到一个 worker 循环**：每个任务足够窄，一个 worker 循环即可完成
5. **显式约束和非目标**：明确列出不做什么
6. **固定结构**：使用统一的结构模板

## 任务结构模板

```markdown
## 任务标题

### Context
- 背景信息
- 相关文件/模块
- 前置条件

### Task
- 具体要做什么
- 期望的输出/结果

### Constraints
- 技术限制
- 不做什么（非目标）
- 依赖项

### Verify
- 验证命令
- 预期结果
- 测试覆盖

### Output
- 交付物清单
- 文件变更
- 文档更新
```

## 任务分类

### 1. 实现任务 (Implementation)

**用途**：添加新功能或修改现有功能

**模板**：
```markdown
## 实现 [功能名称]

### Context
- 模块: [模块名]
- 文件: [相关文件]
- 前置: [前置任务]

### Task
- 实现 [具体功能]
- 添加 [具体逻辑]
- 处理 [边界情况]

### Constraints
- 单文件 ≤300 行
- 单函数 ≤50 行
- 不破坏现有测试
- 遵循现有代码风格

### Verify
- `pytest tests/test_[模块].py -v`
- `ruff check [文件]`
- 手动测试 [具体场景]

### Output
- [文件1]: [变更描述]
- [文件2]: [变更描述]
- 测试: [新增/修改的测试]
```

### 2. 重构任务 (Refactoring)

**用途**：改善代码结构而不改变行为

**模板**：
```markdown
## 重构 [模块名称]

### Context
- 当前问题: [问题描述]
- 相关文件: [文件列表]
- 测试覆盖: [现有测试]

### Task
- 提取 [函数/类] 到 [新模块]
- 更新 [导入/引用]
- 保持 [接口/行为] 不变

### Constraints
- 所有现有测试必须通过
- 不改变公共 API
- 保持向后兼容

### Verify
- `pytest tests/ -q`
- `ruff check .`
- 验证 [具体行为] 未改变

### Output
- [新文件]: [提取的内容]
- [原文件]: [更新的导入]
- 测试: [确保覆盖]
```

### 3. 文档任务 (Documentation)

**用途**：创建或更新文档

**模板**：
```markdown
## 文档 [主题]

### Context
- 目标读者: [受众]
- 相关文档: [现有文档]
- 信息来源: [代码/设计文档]

### Task
- 创建 [文档类型]
- 包含 [具体内容]
- 更新 [索引/链接]

### Constraints
- 使用中文
- 保留英文技术术语
- 遵循现有文档风格

### Verify
- 文档完整性和准确性
- 链接有效性
- 格式一致性

### Output
- [文档路径]: [内容描述]
- 索引更新: [如适用]
```

### 4. 测试任务 (Testing)

**用途**：添加或改进测试覆盖

**模板**：
```markdown
## 测试 [功能/模块]

### Context
- 被测模块: [模块名]
- 现有测试: [测试文件]
- 覆盖率目标: [目标]

### Task
- 添加 [测试类型] 测试
- 覆盖 [具体场景]
- 验证 [边界情况]

### Constraints
- 测试必须可重复
- 不依赖外部状态
- 清理测试数据

### Verify
- `pytest tests/test_[模块].py -v`
- 测试通过率
- 覆盖率报告

### Output
- [测试文件]: [测试用例]
- 测试数据: [如需要]
```

## 任务优先级

### P0 - 阻断性 (Blocking)
- 生产环境问题
- 安全漏洞
- 数据丢失风险

### P1 - 高优先级 (High)
- 核心功能缺失
- 性能严重问题
- 用户体验关键问题

### P2 - 中优先级 (Medium)
- 功能增强
- 代码质量改进
- 文档完善

### P3 - 低优先级 (Low)
- 优化建议
- 技术债务
- 锦上添花

## 任务状态流转

```
Open → In Progress → To Review → Done
  ↓         ↓            ↓
Blocked   To Rework   Abandoned
```

### 状态定义

- **Open**: 任务已创建，等待执行
- **In Progress**: 任务正在执行中
- **To Review**: 任务执行完成，等待审查
- **Done**: 任务已完成并通过审查
- **Blocked**: 任务被阻塞，等待外部条件
- **To Rework**: 任务需要返工
- **Abandoned**: 任务被放弃

## 任务分配原则

1. **单人负责**：每个任务只有一个负责人
2. **明确依赖**：任务依赖必须显式声明
3. **时间估算**：提供粗略时间估算（小时/天）
4. **风险识别**：识别潜在风险和缓解措施

## 示例

### 示例 1: 实现任务

```markdown
## 实现设备角色路由偏好查询接口

### Context
- 模块: device_gateway/model_routing.py
- 文件: device_gateway/model_routing.py, tests/test_device_gateway_model_routing.py
- 前置: 优化路线图阶段 2 完成

### Task
- 添加 get_preferred_backend(route_role) 函数
- 添加 get_route_role_alternatives(route_role) 函数
- 更新 DEVICE_ROLE_PREFERENCES 配置

### Constraints
- 单文件 ≤300 行
- 单函数 ≤50 行
- 不破坏现有测试
- 遵循现有代码风格

### Verify
- `pytest tests/test_device_gateway_model_routing.py -v`
- `ruff check device_gateway/model_routing.py`
- 验证查询结果符合预期

### Output
- device_gateway/model_routing.py: 新增查询函数
- tests/test_device_gateway_model_routing.py: 新增测试用例
```

### 示例 2: 重构任务

```markdown
## 重构 ops_metrics 模块

### Context
- 当前问题: ops_metrics.py 365 行，职责过多
- 相关文件: routes/ops_metrics.py, routes/ops_metrics/formatters.py, routes/ops_metrics/collectors.py
- 测试覆盖: tests/test_ops_metrics.py (28 个测试)

### Task
- 提取 formatters.py (51 行) - 格式化辅助函数
- 提取 collectors.py (245 行) - 数据收集逻辑
- 提取 correlator.py (65 行) - 关联追踪逻辑
- 更新主模块导入

### Constraints
- 所有 28 个现有测试必须通过
- 不改变公共 API
- 保持向后兼容

### Verify
- `pytest tests/test_ops_metrics.py -v`
- `ruff check routes/ops_metrics/`
- 验证端点行为未改变

### Output
- routes/ops_metrics/formatters.py: 格式化函数
- routes/ops_metrics/collectors.py: 收集函数
- routes/ops_metrics/correlator.py: 关联函数
- routes/ops_metrics.py: 更新的导入
```

## 维护

- 每个新任务必须遵循此契约
- 任务审查时检查契约遵循情况
- 定期回顾和更新此文档
