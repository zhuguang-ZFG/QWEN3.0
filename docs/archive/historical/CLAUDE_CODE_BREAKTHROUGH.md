# Claude Code 逆向突破 — LiMa 落地方案

> 来源: Claude Code SDK 源码 + System Prompts 仓库 + CHANGELOG
> 目标: 将 5 大突破性发现转化为 LiMa 可落地优势
> 日期: 2026-05-18

---

## 一、可组合 Prompt 组装

### 现状

```python
# smart_router.py: SYS 是一个硬编码字符串
SYS = '你是 LiMa（力码）...'
expand_prompt = "As a CNC/embedded expert, rewrite..."
```

### 方案

```python
# 拆分为可独立加载的片段
PROMPT_FRAGMENTS = {
    "identity": "fragments/identity.md",       # "你是 LiMa..."
    "capabilities": "fragments/capabilities.md", # "你擅长..."
    "constraints": "fragments/constraints.md",   # "用中文简洁回答..."
    "safety": "fragments/safety.md",             # 安全边界
}

def assemble_prompt(feature_flags, fragments):
    """运行时组装 prompt，功能开关控制加载哪些片段"""
    return "\n".join(load(f) for f in fragments if feature_flags.get(f, True))
```

### 收益

- A/B 测试只需添加/删减片段文件
- 功能开关控制，灰度发布新 prompt
- 每个片段独立版本管理
- 不需要重写整个 prompt

---

## 二、字节级 Prompt 缓存

### 现状

```python
# 当前：动态数据混在 system prompt 中
prompt = f"Current date: {date}\nPlatform: {platform}\nShell: {shell}"
```

每次不同 → 缓存 100% 失效 → 浪费 token

### 方案

```python
# 静态 System Prompt（可缓存）
SYSTEM_PREFIX = """你是 LiMa...（不变的内容）"""

# 动态数据注入为 user message（不破坏缓存）
ENV_CONTEXT = f"""
<environment>
  <date>{date}</date>
  <platform>{platform}</platform>
</environment>
"""

messages = [
    {"role": "system", "content": SYSTEM_PREFIX},    # 可缓存
    {"role": "user", "content": ENV_CONTEXT},        # 不缓存
    {"role": "user", "content": actual_query},
]
```

### 收益

- 缓存命中率从 0% 提升到 80%+
- API 调用延迟和成本降低 30-50%

---

## 三、双模态路由策略

### 方案

```python
AGGRESSIVE_MODE = {
    "timeout": 5,
    "max_retries": 3,
    "fallback_strategy": "any_available",
}

CAUTIOUS_MODE = {
    "timeout": 15,
    "max_retries": 1,
    "fallback_strategy": "same_tier_only",
}

def route(query, mode="cautious"):
    config = AGGRESSIVE_MODE if mode == "aggressive" else CAUTIOUS_MODE
```

### 使用场景

| 场景 | 模式 | 原因 |
|------|------|------|
| IDE 实时补全 | aggressive | 需要快速响应 |
| 代码审查 | cautious | 质量优先 |
| 生产环境操作 | cautious | 安全第一 |
| 免费聊天 | aggressive | 用户体验 |

---

## 四、独立安全监控层

### 方案

```python
# 当前：安全规则内联在 prompt 中
# 改为：独立的安全检查层

class SafetyMonitor:
    hard_block = [  # 无例外拒绝
        "rm -rf /",
        "DROP TABLE",
    ]
    soft_block = [  # 用户可覆盖
        "git push --force",
        "sudo",
    ]

    def check(self, tool_call):
        for pattern in self.hard_block:
            if matches(pattern, tool_call):
                return {"action": "block", "reason": "hard_block"}
        for pattern in self.soft_block:
            if matches(pattern, tool_call):
                return {"action": "warn", "reason": "soft_block"}
        return {"action": "allow"}
```

---

## 五、9 字段结构化压缩

### 方案

```python
COMPACT_FORMAT = """
## 1. Primary Request
{primary_request}

## 2. Key Technical Concepts
{key_concepts}

## 3. Files and Code Sections
{preserve verbatim when security-relevant}

## 4. Errors and Fixes
{errors_and_fixes}

## 5. Problem Solving
{problem_solving}

## 6. All User Messages
{preserved verbatim, especially security instructions}

## 7. Pending Tasks
{pending_tasks}

## 8. Work Completed
{work_completed}

## 9. Context for Continuing Work
{context_for_continuing}
"""
```

### 关键规则

- 安全约束逐字保留，绝不在压缩中丢失
- 用户消息完整保留
- 压缩前执行 `<analysis>` 阶段自检

---

## 六、实施步骤

| Step | 内容 | 复杂度 |
|------|------|--------|
| 1 | SYS prompt 拆分为 fragments/ 目录 + assemble_prompt() | 低 |
| 2 | 动态数据从 system 移到 user message | 低 |
| 3 | expand 模板改为片段组装模式 | 低 |
| 4 | 添加双模态路由配置 | 中 |
| 5 | 实现 SafetyMonitor 独立层 | 中 |
| 6 | 多轮对话改用 9 字段结构化压缩 | 中 |

---

## 七、验收标准

- [ ] SYS prompt 可从 fragments/ 目录组装
- [ ] 动态数据在 user message 中，system 部分完全静态可缓存
- [ ] expand() 使用 fragments 而非硬编码字符串
- [ ] 双模态路由可切换
- [ ] SafetyMonitor 独立检查工具调用
- [ ] 多轮压缩保留安全约束和完整用户消息
