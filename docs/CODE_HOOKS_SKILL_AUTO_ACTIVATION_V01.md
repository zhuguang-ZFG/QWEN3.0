# LiMa Code Hooks + Skill Auto-Activation v0.1

> 日期: 2026-06-13
> 范围: 任务执行自动化和技能激活
> 状态: 初版

## 概述

本文档定义了 LiMa 项目的任务执行自动化和技能激活机制。基于 LiMa Task Prompt Contract v0.1，提供任务执行过程中的自动化检查点、技能激活规则和上下文管理。

## 设计原则

1. **基于规则的激活**：技能激活基于明确的规则，而非默认行为
2. **可审计的追踪**：所有激活决策都有可解释的追踪记录
3. **故障隔离**：单个技能失败不影响其他技能
4. **资源感知**：考虑运行时资源限制

## 技能激活规则

### 规则文件格式

```json
{
  "version": "0.1",
  "rules": [
    {
      "id": "rule-001",
      "name": "设备任务技能激活",
      "trigger": {
        "type": "capability",
        "value": "device_draw"
      },
      "skills": ["svg_validator", "path_optimizer", "preset_shapes"],
      "priority": 1,
      "enabled": true
    }
  ]
}
```

### 触发条件类型

| 类型 | 描述 | 示例 |
|------|------|------|
| `capability` | 设备能力 | `device_draw`, `device_write`, `device_control` |
| `file_pattern` | 文件模式 | `*.py`, `device_gateway/*.py` |
| `content_pattern` | 内容模式 | `def.*test_`, `import.*pytest` |
| `route_role` | 路由角色 | `device_control`, `device_write` |
| `scenario` | 场景 | `coding`, `chat`, `device` |

### 技能定义

```json
{
  "skills": {
    "svg_validator": {
      "name": "SVG 验证器",
      "description": "验证 SVG 路径的有效性",
      "module": "xiaozhi_drawing.svg_validator",
      "function": "validate_svg_path",
      "timeout_sec": 5,
      "required": false
    },
    "path_optimizer": {
      "name": "路径优化器",
      "description": "优化 SVG 路径点数",
      "module": "xiaozhi_drawing.path_optimizer",
      "function": "optimize_svg_path",
      "timeout_sec": 10,
      "required": false
    }
  }
}
```

## 执行检查点

### 检查点类型

| 类型 | 触发时机 | 记录内容 |
|------|---------|---------|
| `pre_task` | 任务开始前 | 任务信息、环境状态 |
| `post_task` | 任务完成后 | 完成状态、变更文件 |
| `post_edit` | 文件编辑后 | 变更内容、测试结果 |
| `stop` | 执行停止时 | 停止原因、当前状态 |

### 检查点记录格式

```json
{
  "checkpoint_id": "cp-20260613-001",
  "type": "post_task",
  "task_id": "T1",
  "timestamp": "2026-06-13T10:30:00Z",
  "data": {
    "status": "completed",
    "files_changed": ["device_gateway/model_routing.py"],
    "tests_run": 29,
    "tests_passed": 29,
    "duration_sec": 45
  }
}
```

## 工作器上下文

### 上下文目录结构

```
.dev/active/<task-id>/
├── plan.md          # 任务计划
├── context.md       # 上下文信息
├── tasks.md         # 子任务列表
├── evidence/        # 执行证据
│   ├── test_results.json
│   ├── code_changes.diff
│   └── deployment_log.txt
└── checkpoints/     # 检查点记录
    ├── cp-001.json
    └── cp-002.json
```

### 上下文文件格式

#### plan.md
```markdown
# 任务计划

## 目标
[任务目标描述]

## 步骤
1. [步骤 1]
2. [步骤 2]

## 验证
- [验证命令 1]
- [验证命令 2]
```

#### context.md
```markdown
# 上下文

## 相关文件
- [文件 1]: [用途]
- [文件 2]: [用途]

## 依赖
- [依赖 1]
- [依赖 2]

## 约束
- [约束 1]
- [约束 2]
```

#### tasks.md
```markdown
# 子任务列表

## 待办
- [ ] [子任务 1]
- [ ] [子任务 2]

## 进行中
- [ ] [子任务 3]

## 已完成
- [x] [子任务 4]
```

## 斜杠命令

### /lima docs
**用途**：显示当前任务的开发文档

**输出**：
```
当前任务: [任务标题]
相关文档:
- docs/[文档1].md: [描述]
- docs/[文档2].md: [描述]
```

### /lima docs-update
**用途**：更新当前任务的开发文档

**行为**：
1. 扫描变更文件
2. 更新相关文档
3. 更新文档索引

### /lima status
**用途**：显示当前任务状态

**输出**：
```
任务: [任务标题]
状态: [状态]
进度: [进度百分比]
检查点: [最近检查点]
```

### /lima checkpoint
**用途**：创建检查点

**行为**：
1. 收集当前状态
2. 记录变更文件
3. 运行测试
4. 保存检查点

## 故障隔离

### 错误处理策略

1. **技能失败**：记录错误，继续执行其他技能
2. **检查点失败**：记录失败原因，标记任务为 blocked
3. **超时处理**：强制终止，记录超时原因

### 错误记录格式

```json
{
  "error_id": "err-20260613-001",
  "skill": "svg_validator",
  "error_type": "timeout",
  "message": "SVG validation timed out after 5 seconds",
  "context": {
    "task_id": "T1",
    "file": "test.svg"
  },
  "timestamp": "2026-06-13T10:35:00Z"
}
```

## 安全控制

### 仓库允许列表

```json
{
  "allowed_repos": [
    "D:\\QWEN3.0",
    "D:\\GIT\\*"
  ],
  "blocked_patterns": [
    "*.env",
    "*.key",
    "credentials*"
  ]
}
```

### 运行时预算

| 资源 | 限制 |
|------|------|
| 最大执行时间 | 30 分钟 |
| 最大内存使用 | 512 MB |
| 最大文件变更 | 50 个文件 |
| 最大测试时间 | 10 分钟 |

### 审计追踪

所有技能激活和检查点记录都保存在审计日志中：

```json
{
  "audit_id": "audit-20260613-001",
  "action": "skill_activated",
  "skill": "svg_validator",
  "reason": "capability=device_draw",
  "timestamp": "2026-06-13T10:30:00Z"
}
```

## 实现计划

### Phase 1: 基础设施
- [ ] 定义技能激活规则格式
- [ ] 实现规则解析器
- [ ] 创建检查点记录器

### Phase 2: 技能激活
- [ ] 实现基于规则的技能激活
- [ ] 添加技能执行器
- [ ] 实现故障隔离

### Phase 3: 上下文管理
- [ ] 创建工作器上下文目录
- [ ] 实现上下文文件管理
- [ ] 添加斜杠命令

### Phase 4: 安全控制
- [ ] 实现仓库允许列表
- [ ] 添加运行时预算
- [ ] 创建审计日志

## 验证

```powershell
# 运行测试
python -m pytest tests/test_hooks*.py -v

# 验证技能激活
python -m pytest tests/test_skill_activation.py -v

# 验证检查点
python -m pytest tests/test_checkpoints.py -v
```
