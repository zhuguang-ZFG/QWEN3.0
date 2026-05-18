# xue/esp32S_XYZ — AI 工具后台路由设计方案

> 基于项目对话数据分析 + 四工具逆向特征

---

## 一、项目当前使用模式

| 模型 | 任务数 | 主要用途 |
|------|--------|---------|
| claude-opus-4-7 | 1208 | 全任务主力 |
| deepseek-v4-pro | 482 | 文档/硬件辅助 |
| LongCat-2.0-Preview | 58 | **硬件任务专项 (72%)** |

## 二、任务类型分布

| 类型 | 占比 | 特征关键词 |
|------|------|-----------|
| hardware | 18% | GPIO, 引脚, PCB, 电机, I2C, SPI, UART, 传感器 |
| docs | 16% | 文档, README, 说明, CHANGELOG, 记录 |
| test | 9% | 测试, pytest, 验证, schema, 校验 |
| planning | 4% | 计划, 架构, 里程碑, M0~M6 |
| coding | 2% | 实现, 编码, 重构, 函数, 模块 |
| build | 2% | 构建, 编译, CI, docker |
| bugfix | 1% | bug, 修复, 问题 |
| review | 1% | 审查, review, 审计 |

## 三、推荐路由规则

### 按任务类型路由

```
hardware  → Codex CLI (pragmatic模式, rg搜索电路文档)
docs      → Claude Code (CLAUDE.md项目上下文)
test      → Cursor (run_terminal_cmd + read_lints)
planning  → Claude Code (EnterPlanMode)
coding    → Cursor (ApplyPatch, 视觉diff)
build     → Codex CLI (终端命令)
bugfix    → Cursor (read_lints, 快速迭代)
review    → Claude Code (多文件审查)
```

### 按模型成本路由

```
快速/简单任务 → deepseek-v4-pro (便宜)
中等复杂度   → claude-sonnet-4-6 (平衡)
高复杂度     → claude-opus-4-7 (最强)
硬件专项     → LongCat-2.0-Preview (已验证)
```

### 路由决策矩阵

| 任务特征 | 推荐工具 | 推荐模型 | 理由 |
|---------|---------|---------|------|
| 硬件/GPIO/引脚 | Codex | LongCat | 搜索电路文档, CLI友好 |
| 文档/README | Claude Code | opus-4-7 | CLAUDE.md上下文 |
| 测试/schema | Cursor | sonnet-4-6 | run_terminal_cmd |
| 计划/架构 | Claude Code | opus-4-7 | EnterPlanMode |
| 编码实现 | Cursor | sonnet-4-6 | ApplyPatch |
| CI/构建 | Codex | deepseek | 终端密集 |
| Bug修复 | Cursor | sonnet-4-6 | 快速迭代 |
| 多文件重构 | Claude Code | opus-4-7 | 全局分析 |

## 四、实现架构

```
用户输入 → 任务分类器 → 工具路由器 → 模型路由器 → 执行
              │              │             │
              ▼              ▼             ▼
        关键词匹配     工具特征匹配    成本/能力匹配
        + ML分类器     + 信号字典      + 任务复杂度
```

### 分类器输入特征
- 任务文本前 500 字符
- 涉及的文件路径（docs/ → 文档任务, firmware/ → 编码任务）
- 关键词密度（硬件词: 30+ 个, 文档词: 15+ 个）
- 项目阶段（M0~M6 里程碑进度）

### 路由规则示例
```python
def route_task(task_text, file_paths):
    if detect_hardware(task_text):
        return "codex", "longcat-2.0-preview"
    if detect_docs(task_text) or "docs/" in file_paths:
        return "claude", "claude-opus-4-7"
    if detect_test(task_text):
        return "cursor", "claude-sonnet-4-6"
    if detect_planning(task_text):
        return "claude", "claude-opus-4-7"
    if detect_coding(task_text):
        return "cursor", "claude-sonnet-4-6"
    return "claude", "deepseek-v4-pro"  # 默认
```

## 五、项目现有 AI 工具配置

```
.agents/skills/     — 跨工具技能
.claude/            — Claude Code settings.local.json
.cursor/rules/      — Cursor 规则
.kiro/steering/     — Kiro 导航配置
```

可在此基��上添加路由配置文件 `.router/config.yaml`。

## 六、与通用路由模型的关系

此项目的路由规则可以：
1. 作为通用路由模型的 **fine-tuning 数据**（一个 ESP32 项目的真实使用模式）
2. 验证通用路由模型的 **领域迁移能力**（硬件项目 vs 纯软件项目）
3. 测试**成本优化路由**（claude-opus 用于复杂任务, deepseek 用于简单任务）
